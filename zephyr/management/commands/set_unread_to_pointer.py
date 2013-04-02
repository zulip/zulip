from optparse import make_option
import logging

from django.core.management.base import BaseCommand

from zephyr.lib.actions import do_deactivate
from zephyr.lib import utils
from zephyr.models import UserMessage, UserProfile, \
    get_user_profile_by_email
from django.db import transaction, models


class Command(BaseCommand):
    help = "Updates a user's read messages up to her current pointer location"

    option_list = BaseCommand.option_list + (
        make_option('-f', '--for-real',
                    dest='for_real',
                    action='store_true',
                    default=False,
                    help="Actually change message flags. Default is a dry run."),
        make_option('-a', '--all',
                    dest='all_users',
                    action='store_true',
                    default=False,
                    help="Updates flags for all users at once."),
        make_option('-r', '--realm',
                    dest='one_realm',
                    action='store_true',
                    default=False,
                    help="Updates flags for all users in one realm at once."),
        )

    def handle(self, *args, **options):
        if not args and not options["all_users"] and not options["one_realm"]:
            print "Please specify an e-mail address and/or --realm or --all"
            exit(1)

        if options["all_users"]:
            users = UserProfile.objects.all()
        elif options["one_realm"]:
            if not args:
                print "Please specify which realm to process."
                exit(1)
            users = UserProfile.objects.filter(realm__domain=args[0])
        else:
            users = [get_user_profile_by_email(args[0])]


        for user_profile in users:
            pointer = user_profile.pointer
            msgs = UserMessage.objects.filter(user_profile=user_profile,
                                              flags=~UserMessage.flags.read,
                                              message__id__lte=pointer)
            if not options["for_real"]:
                for msg in msgs:
                    print "Adding read flag to msg: %s - %s/%s (own msg: %s)"   \
                            % (user_profile.user.email,
                               msg.message.id,
                               msg.id,
                               msg.message.sender.user.email == user_profile.user.email)
            else:
                def do_update(batch):
                    with transaction.commit_on_success():
                        UserMessage.objects.filter(id__in=batch).update(flags=models.F('flags').bitor(UserMessage.flags.read))

                mids = [m.id for m in msgs]
                utils.run_in_batches(mids, 250, do_update, 3, logging.info)

        if not options["for_real"]:
            print "Dry run completed. Run with --for-real to change message flags."
            exit(1)

        print "User messages updated."

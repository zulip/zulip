from __future__ import absolute_import
from __future__ import print_function

from typing import Any, Iterable

from optparse import make_option
import logging
import sys

from django.core.management.base import BaseCommand

from zerver.lib import utils
from zerver.models import UserMessage, get_user_profile_by_email
from django.db import models


class Command(BaseCommand):
    help = """Sets user message flags. Used internally by actions.py. Marks all
    Expects a comma-delimited list of user message ids via stdin, and an EOF to terminate."""

    option_list = BaseCommand.option_list + (
        make_option('-r', '--for-real',
                    dest='for_real',
                    action='store_true',
                    default=False,
                    help="Actually change message flags. Default is a dry run."),
        make_option('-f', '--flag',
                    dest='flag',
                    type='string',
                    help="The flag to add of remove"),
        make_option('-o', '--op',
                    dest='op',
                    type='string',
                    help="The operation to do: 'add' or 'remove'"),
        make_option('-u', '--until',
                    dest='all_until',
                    type='string',
                    help="Mark all messages <= specific usermessage id"),
        make_option('-m', '--email',
                    dest='email',
                    type='string',
                    help="Email to set messages for"),
        )

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if not options["flag"] or not options["op"] or not options["email"]:
            print("Please specify an operation, a flag and an email")
            exit(1)

        op = options['op']
        flag = getattr(UserMessage.flags, options['flag'])
        all_until = options['all_until']
        email = options['email']

        user_profile = get_user_profile_by_email(email)

        if all_until:
            filt = models.Q(id__lte=all_until)
        else:
            filt = models.Q(message__id__in=[mid.strip() for mid in sys.stdin.read().split(',')])
        mids = [m.id for m in
                    UserMessage.objects.filter(filt, user_profile=user_profile).order_by('-id')]

        if options["for_real"]:
            sys.stdin.close()
            sys.stdout.close()
            sys.stderr.close()

        def do_update(batch):
            # type: (Iterable[int]) -> None
            msgs = UserMessage.objects.filter(id__in=batch)
            if op == 'add':
                msgs.update(flags=models.F('flags').bitor(flag))
            elif op == 'remove':
                msgs.update(flags=models.F('flags').bitand(~flag))

        if not options["for_real"]:
            logging.info("Updating %s by %s %s" % (mids, op, flag))
            logging.info("Dry run completed. Run with --for-real to change message flags.")
            exit(1)

        utils.run_in_batches(mids, 400, do_update, sleep_time=3)
        exit(0)

from __future__ import absolute_import

from optparse import make_option

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_deactivate_user, user_sessions
from zerver.models import get_user_profile_by_email, UserProfile

class Command(BaseCommand):
    help = "Deactivate a user, including forcibly logging them out."

    option_list = BaseCommand.option_list + (
        make_option('-f', '--for-real',
                    dest='for_real',
                    action='store_true',
                    default=False,
                    help="Actually deactivate the user. Default is a dry run."),
        )

    def handle(self, *args, **options):
        if not args:
            print "Please specify an e-mail address."
            exit(1)

        user_profile = get_user_profile_by_email(args[0])

        print "Deactivating %s (%s) - %s" % (user_profile.full_name,
                                             user_profile.email,
                                             user_profile.realm.domain)
        print "%s has the following active sessions:" % (user_profile.email,)
        for session in user_sessions(user_profile):
            print session.expire_date, session.get_decoded()
        print ""
        print "%s has %s active bots that will also be deactivated." % (
                user_profile.email,
                UserProfile.objects.filter(
                    is_bot=True, is_active=True, bot_owner=user_profile
                ).count()
            )

        if not options["for_real"]:
            print "This was a dry run. Pass -f to actually deactivate."
            exit(1)

        do_deactivate_user(user_profile)
        print "Sessions deleted, user deactivated."

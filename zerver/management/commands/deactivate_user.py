
from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import do_deactivate_user
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.sessions import user_sessions
from zerver.models import UserProfile

class Command(ZulipBaseCommand):
    help = "Deactivate a user, including forcibly logging them out."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('-f', '--for-real',
                            dest='for_real',
                            action='store_true',
                            default=False,
                            help="Actually deactivate the user. Default is a dry run.")
        parser.add_argument('email', metavar='<email>', type=str,
                            help='email of user to deactivate')
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        user_profile = self.get_user(options['email'], realm)

        print("Deactivating %s (%s) - %s" % (user_profile.full_name,
                                             user_profile.email,
                                             user_profile.realm.string_id))
        print("%s has the following active sessions:" % (user_profile.email,))
        for session in user_sessions(user_profile):
            print(session.expire_date, session.get_decoded())
        print("")
        print("%s has %s active bots that will also be deactivated." % (
            user_profile.email,
            UserProfile.objects.filter(
                is_bot=True, is_active=True, bot_owner=user_profile
            ).count()
        ))

        if not options["for_real"]:
            print("This was a dry run. Pass -f to actually deactivate.")
            exit(1)

        do_deactivate_user(user_profile)
        print("Sessions deleted, user deactivated.")

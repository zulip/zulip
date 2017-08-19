from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import CommandParser

from zerver.lib.actions import do_change_notification_settings
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile

class Command(ZulipBaseCommand):
    help = """Turn off digests for a subdomain/string_id or specified set of email addresses."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        self.add_realm_args(parser)

        self.add_user_list_args(parser,
                                help='Turn off digests for this comma-separated '
                                     'list of email addresses.')

        parser.add_argument('-a', '--all-users',
                            dest='all_users',
                            action="store_true",
                            default=False,
                            help="Turn off digests for everyone in a realm. "
                                 "Don't forget to specify the realm.")

    def handle(self, **options):
        # type: (**str) -> None
        realm = self.get_realm(options)
        user_profiles = self.get_users(options, realm)
        all_users = options["all_users"]

        # If all_users flag is passed user list should not be passed and vice versa.
        # If all_users flag is passed it is manadatory to pass the realm.
        if (bool(user_profiles) == all_users) or (all_users and not realm):
            self.print_help("./manage.py", "turn_off_digests")
            exit(1)

        if all_users:
            user_profiles = UserProfile.objects.filter(realm=realm)

        print("Turned off digest emails for:")
        for user_profile in user_profiles:
            already_disabled_prefix = ""
            if user_profile.enable_digest_emails:
                do_change_notification_settings(user_profile, 'enable_digest_emails', False)
            else:
                already_disabled_prefix = "(already off) "
            print("%s%s <%s>" % (already_disabled_prefix, user_profile.full_name,
                                 user_profile.email))


from django.core.management.base import CommandParser

from zerver.lib.actions import do_change_notification_settings
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Turn off digests for a subdomain/string_id or specified set of email addresses."""

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser)

        self.add_user_list_args(parser,
                                help='Turn off digests for this comma-separated '
                                     'list of email addresses.',
                                all_users_help="Turn off digests for everyone in realm.")

    def handle(self, **options: str) -> None:
        realm = self.get_realm(options)
        user_profiles = self.get_users(options, realm)

        print("Turned off digest emails for:")
        for user_profile in user_profiles:
            already_disabled_prefix = ""
            if user_profile.enable_digest_emails:
                do_change_notification_settings(user_profile, 'enable_digest_emails', False)
            else:
                already_disabled_prefix = "(already off) "
            print("%s%s <%s>" % (already_disabled_prefix, user_profile.full_name,
                                 user_profile.email))

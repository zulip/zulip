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
        parser.add_argument('-u', '--users',
                            dest='users',
                            type=str,
                            help='Turn off digests for this comma-separated '
                                 'list of email addresses.')
        self.add_realm_args(parser)

    def handle(self, **options):
        # type: (**str) -> None
        realm = self.get_realm(options)
        if realm is None and options["users"] is None:
            self.print_help("./manage.py", "turn_off_digests")
            exit(1)

        if realm and not options["users"]:
            user_profiles = UserProfile.objects.filter(realm=realm)
        else:
            emails = set([email.strip() for email in options["users"].split(",")])
            user_profiles = []
            for email in emails:
                user_profiles.append(self.get_user(email, realm))

        print("Turned off digest emails for:")
        for user_profile in user_profiles:
            already_disabled_prefix = ""
            if user_profile.enable_digest_emails:
                do_change_notification_settings(user_profile, 'enable_digest_emails', False)
            else:
                already_disabled_prefix = "(already off) "
            print("%s%s <%s>" % (already_disabled_prefix, user_profile.full_name,
                                 user_profile.email))

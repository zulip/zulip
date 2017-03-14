from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from optparse import make_option

from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.actions import do_change_enable_digest_emails
from zerver.models import Realm, UserProfile, get_realm, get_user_profile_by_email

class Command(BaseCommand):
    help = """Turn off digests for a subdomain/string_id or specified set of email addresses."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-r', '--realm',
                            dest='string_id',
                            type=str,
                            help='Turn off digests for all users in this realm.')

        parser.add_argument('-u', '--users',
                            dest='users',
                            type=str,
                            help='Turn off digests for this comma-separated '
                                 'list of email addresses.')

    def handle(self, **options):
        # type: (**str) -> None
        if options["string_id"] is None and options["users"] is None:
            self.print_help("./manage.py", "turn_off_digests")
            exit(1)

        if options["string_id"]:
            realm = get_realm(options["string_id"])
            user_profiles = UserProfile.objects.filter(realm=realm)
        else:
            emails = set([email.strip() for email in options["users"].split(",")])
            user_profiles = []
            for email in emails:
                user_profiles.append(get_user_profile_by_email(email))

        print("Turned off digest emails for:")
        for user_profile in user_profiles:
            already_disabled_prefix = ""
            if user_profile.enable_digest_emails:
                do_change_enable_digest_emails(user_profile, False)
            else:
                already_disabled_prefix = "(already off) "
            print("%s%s <%s>" % (already_disabled_prefix, user_profile.full_name,
                                 user_profile.email))

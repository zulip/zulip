from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from optparse import make_option

from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.actions import do_change_notification_settings
from zerver.models import Realm, UserProfile, get_realm, get_user_for_mgmt

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

        realm = get_realm(options["string_id"])
        if options["string_id"] is not None and realm is None:
            print("The realm %s does not exist. Aborting." % options["string_id"])
            exit(1)

        user_profiles = []
        if options["string_id"] and options["users"]:
            emails = set([email.strip() for email in options["users"].split(",")])
            for email in emails:
                try:
                    user_profiles.append(get_user_for_mgmt(email, realm))
                except UserProfile.DoesNotExist:
                    print("e-mail %s doesn't exist in realm %s, skipping" % (email, realm,))
                    exit(1)
        elif options["string_id"]:
            user_profiles = UserProfile.objects.filter(realm=realm)
        else:
            emails = set([email.strip() for email in options["users"].split(",")])
            for email in emails:
                try:
                    user_profiles.append(get_user_for_mgmt(email))
                except UserProfile.DoesNotExist:
                    print("e-mail %s doesn't exist in the system, skipping" % (email,))
                    exit(1)

        print("Turned off digest emails for:")
        for user_profile in user_profiles:
            already_disabled_prefix = ""
            if user_profile.enable_digest_emails:
                do_change_notification_settings(user_profile, 'enable_digest_emails', False)
            else:
                already_disabled_prefix = "(already off) "
            print("%s%s <%s>" % (already_disabled_prefix, user_profile.full_name,
                                 user_profile.email))

from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from optparse import make_option

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_change_enable_digest_emails
from zerver.models import Realm, UserProfile, get_realm, get_user_profile_by_email

class Command(BaseCommand):
    help = """Turn off digests for a domain or specified set of email addresses."""

    option_list = BaseCommand.option_list + (
        make_option('-d', '--domain',
                    dest='domain',
                    type='str',
                    help='Turn off digests for all users in this domain.'),
        make_option('-u', '--users',
                    dest='users',
                    type='str',
                    help='Turn off digests for this comma-separated list of email addresses.'),
        )

    def handle(self, **options):
        # type: (**str) -> None
        if options["domain"] is None and options["users"] is None:
            self.print_help("python manage.py", "turn_off_digests")
            exit(1)

        if options["domain"]:
            realm = get_realm(options["domain"])
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

from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from confirmation.models import Confirmation
from zerver.models import UserProfile, PreregistrationUser, \
    get_user_for_mgmt, get_realm, email_allowed_for_realm

class Command(BaseCommand):
    help = "Generate activation links for users and print them to stdout."

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('string_id', metavar='<realm>', type=str,
                            help='The realm in which to generate the invites (use for open realms).')
        parser.add_argument('emails', metavar='<email>', type=str, nargs='*',
                            help='email of user to generate an activation link for')
        parser.add_argument('--force',
                            dest='force',
                            action="store_true",
                            default=False,
                            help='Override that the domain is restricted to external users.')

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        duplicates = False
        realm = get_realm(options["string_id"])
        if (options["string_id"] is None) or (not options["emails"]):
            self.print_help("./manage.py", "add_users_to_streams")
            exit(1)

        if realm is None:
            print("The realm %s doesn't exist yet, please create it first." % options["string_id"])
            print("Don't forget default streams!")
            exit(1)

        for email in options['emails']:
            try:
                get_user_for_mgmt(email, realm)
                print(email + ": There is already a user registered with that address.")
                duplicates = True
                continue
            except UserProfile.DoesNotExist:
                pass

        if duplicates:
            return

        for email in options['emails']:
            if not email_allowed_for_realm(email, realm) and not options["force"]:
                print("You've asked to add an external user (%s) to a closed realm (%s)." % (
                    email, options["string_id"]))
                print("Are you sure? To do this, pass --force.")
                exit(1)
            else:
                prereg_user = PreregistrationUser(email=email, realm=realm)
            prereg_user.save()
            print(email + ": " + Confirmation.objects.get_link_for_object(prereg_user, host=realm.host))

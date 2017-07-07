from __future__ import absolute_import
from __future__ import print_function

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from typing import Any

from zerver.lib.actions import do_change_user_email
from zerver.models import UserProfile, get_user_for_mgmt, get_realm

class Command(BaseCommand):
    help = """Change the email address for a user."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument(
            '-r', '--realm', nargs='?', default=None,
            dest='string_id',
            type=str,
            help='The name of the realm in which you are changing user emails.')

        parser.add_argument('old_email', metavar='<old email>', type=str,
                            help='email address to change')
        parser.add_argument('new_email', metavar='<new email>', type=str,
                            help='new email address')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        old_email = options['old_email']
        new_email = options['new_email']
        realm = get_realm(options["string_id"])
        if options["string_id"] is not None and realm is None:
            print("The realm %s does not exist. Aborting." % options["string_id"])
            exit(1)
        try:
            user_profile = get_user_for_mgmt(old_email, realm)
        except UserProfile.DoesNotExist:
            if realm is None:
                print("Old e-mail %s doesn't exist in the system." % (old_email))
            else:
                print("Old e-mail %s doesn't exist in the realm." % (old_email))
            exit(1)

        do_change_user_email(user_profile, new_email)

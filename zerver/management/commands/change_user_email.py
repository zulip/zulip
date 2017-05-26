from __future__ import absolute_import
from __future__ import print_function

import sys

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from typing import Any

from zerver.lib.actions import do_change_user_email
from zerver.models import UserProfile, get_user_for_mgmt

class Command(BaseCommand):
    help = """Change the email address for a user."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('old_email', metavar='<old email>', type=str,
                            help='email address to change')
        parser.add_argument('new_email', metavar='<new email>', type=str,
                            help='new email address')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        old_email = options['old_email']
        new_email = options['new_email']
        try:
            user_profile = get_user_for_mgmt(old_email)
        except UserProfile.DoesNotExist:
            print("Old e-mail doesn't exist in the system.")
            sys.exit(1)

        do_change_user_email(user_profile, new_email)

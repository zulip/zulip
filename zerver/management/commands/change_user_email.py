from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from zerver.lib.actions import do_change_user_email
from zerver.models import UserProfile, get_user_profile_by_email

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
            user_profile = get_user_profile_by_email(old_email)
        except UserProfile.DoesNotExist:
            print("Old e-mail doesn't exist in the system.")
            exit(1)

        do_change_user_email(user_profile, new_email)

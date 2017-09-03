from __future__ import absolute_import
from __future__ import print_function

import logging
import sys

from typing import Any, List, Text

from argparse import ArgumentParser
from django.core.management.base import CommandError
from django.db import connection

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.fix_unreads import fix

from zerver.models import (
    Realm,
    UserProfile
)

logging.getLogger('zulip.fix_unreads').setLevel(logging.INFO)

class Command(ZulipBaseCommand):
    help = """Fix problems related to unread counts."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('emails',
                            metavar='<emails>',
                            type=str,
                            nargs='*',
                            help='email address to spelunk')
        parser.add_argument('--all',
                            action='store_true',
                            dest='all',
                            default=False,
                            help='fix all users in specified realm')
        self.add_realm_args(parser)

    def fix_all_users(self, realm):
        # type: (Realm) -> None
        user_profiles = list(UserProfile.objects.filter(
            realm=realm,
            is_bot=False
        ))
        for user_profile in user_profiles:
            fix(user_profile)
            connection.commit()

    def fix_emails(self, realm, emails):
        # type: (Realm, List[Text]) -> None

        for email in emails:
            try:
                user_profile = self.get_user(email, realm)
            except CommandError:
                print("e-mail %s doesn't exist in the realm %s, skipping" % (email, realm))
                return

            fix(user_profile)
            connection.commit()

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = self.get_realm(options)

        if options['all']:
            if realm is None:
                print('You must specify a realm if you choose the --all option.')
                sys.exit(1)

            self.fix_all_users(realm)
            return

        self.fix_emails(realm, options['emails'])

from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from zerver.lib.initial_password import initial_password
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = "Print the initial password and API key for accounts as created by populate_db"

    fmt = '%-30s %-16s  %-32s'

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('emails', metavar='<email>', type=str, nargs='*',
                            help="email of user to show password and API key for")
        self.add_realm_args(parser)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        print(self.fmt % ('email', 'password', 'API key'))
        for email in options['emails']:
            if '@' not in email:
                print('ERROR: %s does not look like an email address' % (email,))
                continue
            print(self.fmt % (email, initial_password(email), self.get_user(email, realm).api_key))

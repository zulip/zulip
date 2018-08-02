
from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import do_change_user_delivery_email
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Change the delivery email address for a user."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser)
        parser.add_argument('email', metavar='<email>', type=str,
                            help='email of user')
        parser.add_argument('new_delivery_email', metavar='<new delivery_email>', type=str,
                            help='new delivery email address')

    def handle(self, *args: Any, **options: str) -> None:
        email = options['email']
        new_delivery_email = options['new_delivery_email']

        realm = self.get_realm(options)
        user_profile = self.get_user(email, realm)

        do_change_user_delivery_email(user_profile, new_delivery_email)

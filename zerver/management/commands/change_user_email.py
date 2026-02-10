from argparse import ArgumentParser
from typing import Any

from typing_extensions import override

from zerver.actions.user_settings import do_change_user_delivery_email
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Change the email address for a user."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser)
        parser.add_argument("old_email", metavar="<old email>", help="email address to change")
        parser.add_argument("new_email", metavar="<new email>", help="new email address")

    @override
    def handle(self, *args: Any, **options: str) -> None:
        old_email = options["old_email"]
        new_email = options["new_email"]

        realm = self.get_realm(options)
        user_profile = self.get_user(old_email, realm)

        do_change_user_delivery_email(user_profile, new_email, acting_user=None)

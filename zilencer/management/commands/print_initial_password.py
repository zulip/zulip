from argparse import ArgumentParser
from typing import Any

from typing_extensions import override

from zerver.lib.initial_password import initial_password
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = "Print the initial password and API key for accounts as created by populate_db"

    fmt = "%-30s %-16s  %-32s"

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "emails",
            metavar="<email>",
            nargs="*",
            help="email of user to show password and API key for",
        )
        self.add_realm_args(parser)

    @override
    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        print(self.fmt % ("email", "password", "API key"))
        for email in options["emails"]:
            if "@" not in email:
                print(f"ERROR: {email} does not look like an email address")
                continue
            user = self.get_user(email, realm)
            print(self.fmt % (email, initial_password(email), user.api_key))

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from zerver.actions.user_settings import do_change_full_name
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Change the names for many users."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "data_file",
            metavar="<data file>",
            help="file containing rows of the form <email>,<desired name>",
        )
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: str) -> None:
        data_file = options["data_file"]
        realm = self.get_realm(options)
        with open(data_file) as f:
            for line in f:
                email, new_name = line.strip().split(",", 1)

                try:
                    user_profile = self.get_user(email, realm)
                    old_name = user_profile.full_name
                    print(f"{email}: {old_name} -> {new_name}")
                    do_change_full_name(user_profile, new_name, None)
                except CommandError:
                    print(f"e-mail {email} doesn't exist in the realm {realm}, skipping")

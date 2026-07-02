from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from zerver.actions.mcp_tokens import do_create_mcp_api_token
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Create a personal MCP API token for a user and print it.

The token is shown only once, here; only its digest is stored."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument("email", help="Email of the user to create the token for.")
        parser.add_argument(
            "--label",
            default="Command-line MCP token",
            help="Label identifying where the token is used.",
        )

    @override
    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None
        user_profile = self.get_user(options["email"], realm)
        if user_profile.is_bot:
            raise CommandError("Bots cannot have MCP tokens.")

        _token, raw_token = do_create_mcp_api_token(
            user_profile, options["label"], acting_user=None
        )
        self.stdout.write(
            self.style.SUCCESS(f"Created MCP token for {user_profile.delivery_email}:")
        )
        self.stdout.write(raw_token)

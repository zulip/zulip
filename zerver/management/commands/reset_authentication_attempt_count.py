from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.lib.management import ZulipBaseCommand
from zproject.backends import RateLimitedAuthenticationByUsername


class Command(ZulipBaseCommand):
    help = """Reset the rate limit for authentication attempts for username."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("-u", "--username", help="Username to reset the rate limit for.")

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["username"]:
            self.print_help("./manage.py", "reset_authentication_attempt_count")
            raise CommandError("Please enter a username")

        username = options["username"]
        RateLimitedAuthenticationByUsername(username).clear_history()

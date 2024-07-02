from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from analytics.lib.counts import ALL_COUNT_STATS, do_drop_single_stat
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Clear analytics tables."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--force", action="store_true", help="Actually do it.")
        parser.add_argument("--property", help="The property of the stat to be cleared.")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        property = options["property"]
        if property not in ALL_COUNT_STATS:
            raise CommandError(f"Invalid property: {property}")
        if not options["force"]:
            raise CommandError("No action taken. Use --force.")

        do_drop_single_stat(property)

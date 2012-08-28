from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from analytics.lib.counts import do_drop_all_analytics_tables
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Clear analytics tables."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--force", action="store_true", help="Clear analytics tables.")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if options["force"]:
            do_drop_all_analytics_tables()
        else:
            raise CommandError(
                "Would delete all data from analytics tables (!); use --force to do so."
            )

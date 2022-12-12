from argparse import ArgumentParser
from typing import Any, Optional

from django.core.management.base import BaseCommand

from zerver.lib.cache_helpers import cache_fillers, fill_remote_cache


class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--cache", help="Populate one specific cache", choices=cache_fillers.keys()
        )

    def handle(self, *args: Any, **options: Optional[str]) -> None:
        if options["cache"] is not None:
            fill_remote_cache(options["cache"])
            return

        for cache in cache_fillers:
            fill_remote_cache(cache)

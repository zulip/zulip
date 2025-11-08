from argparse import ArgumentParser
from typing import Any

from typing_extensions import override

from zerver.lib.cache_helpers import cache_fillers, fill_remote_cache
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--cache", help="Populate one specific cache", choices=cache_fillers.keys()
        )

    @override
    def handle(self, *args: Any, **options: str | None) -> None:
        if options["cache"] is not None:
            fill_remote_cache(options["cache"])
            return

        for cache in cache_fillers:
            fill_remote_cache(cache)

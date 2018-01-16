
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from zerver.lib.cache_helpers import cache_fillers, fill_remote_cache

class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--cache', dest="cache", default=None,
                            help="Populate the memcached cache of messages.")

    def handle(self, *args: Any, **options: str) -> None:
        if options["cache"] is not None:
            fill_remote_cache(options["cache"])
            return

        for cache in cache_fillers.keys():
            fill_remote_cache(cache)

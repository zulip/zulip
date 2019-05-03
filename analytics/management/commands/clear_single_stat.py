from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from analytics.lib.counts import COUNT_STATS, do_drop_single_stat

class Command(BaseCommand):
    help = """Clear analytics tables."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--force',
                            action='store_true',
                            help="Actually do it.")
        parser.add_argument('--property',
                            type=str,
                            help="The property of the stat to be cleared.")

    def handle(self, *args: Any, **options: Any) -> None:
        property = options['property']
        if property not in COUNT_STATS:
            raise CommandError("Invalid property: %s" % (property,))
        if not options['force']:
            raise CommandError("No action taken. Use --force.")

        do_drop_single_stat(property)

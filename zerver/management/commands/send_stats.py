
from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = """Send some stats to statsd."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('operation', metavar='<operation>', type=str,
                            choices=['incr', 'decr', 'timing', 'timer', 'gauge'],
                            help="incr|decr|timing|timer|gauge")
        parser.add_argument('name', metavar='<name>', type=str)
        parser.add_argument('val', metavar='<val>', type=str)

    def handle(self, *args: Any, **options: str) -> None:
        operation = options['operation']
        name = options['name']
        val = options['val']

        if settings.STATSD_HOST != '':
            from statsd import statsd

            func = getattr(statsd, operation)
            func(name, val)

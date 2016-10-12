from __future__ import absolute_import

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = """Send some stats to statsd."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('operation', metavar='<operation>', type=str,
                            choices=['incr', 'decr', 'timing', 'timer', 'gauge'],
                            help="incr|decr|timing|timer|gauge")
        parser.add_argument('name', metavar='<name>', type=str)
        parser.add_argument('val', metavar='<val>', type=str)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        operation = options['operation']
        name = options['name']
        val = options['val']

        if settings.STATSD_HOST != '':
            from statsd import statsd

            func = getattr(statsd, operation)
            func(name, val)

from __future__ import absolute_import
from __future__ import print_function

import sys

from argparse import ArgumentParser
from django.db import connection
from django.core.management.base import BaseCommand

from analytics.lib.counts import do_drop_all_analytics_tables

from typing import Any

class Command(BaseCommand):
    help = """Clear analytics tables."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--force',
                            action='store_true',
                            help="Clear analytics tables.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if options['force']:
            do_drop_all_analytics_tables()
        else:
            print("Would delete all data from analytics tables (!); use --force to do so.")
            sys.exit(1)

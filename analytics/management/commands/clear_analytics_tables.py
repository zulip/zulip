from __future__ import absolute_import
from __future__ import print_function

import sys

from argparse import ArgumentParser
from django.db import connection
from django.core.management.base import BaseCommand

from typing import Any

CLEAR_QUERY = """
DELETE FROM ONLY analytics_installationcount;
DELETE FROM ONLY analytics_realmcount;
DELETE FROM ONLY analytics_usercount;
DELETE FROM ONLY analytics_streamcount;
DELETE FROM ONLY analytics_fillstate;
"""

class Command(BaseCommand):
    help = """Clear Analytics tables."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--force',
                            action='store_true',
                            help="Clear analytics Tables.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if options['force']:
            cursor = connection.cursor()
            cursor.execute(CLEAR_QUERY)
            cursor.close()
        else:
            print("Would delete all data from analytics tables (!); use --force to do so.")
            sys.exit(1)

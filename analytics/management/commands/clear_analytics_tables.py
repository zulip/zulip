from argparse import ArgumentParser
from django.db import connection
from django.core.management.base import BaseCommand

from typing import Any

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
            cursor.execute(clear_query)
            cursor.close()

clear_query = """
DELETE FROM ONLY analytics_installationcount;
DELETE FROM ONLY analytics_realmcount;
DELETE FROM ONLY analytics_usercount;
DELETE FROM ONLY analytics_streamcount;
DELETE FROM ONLY analytics_huddlecount
"""

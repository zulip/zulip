# -*- coding: utf-8 -*-
import argparse
from typing import Any
from django.core.management.base import BaseCommand

from zerver.lib.test_fixtures import check_if_database_exist


class Command(BaseCommand):
    help = "Checks if database, by given database's name, exists."

    def add_arguments(self, parser):
        # type: (argparse.ArgumentParser) -> None
        parser.add_argument('database_name', nargs='?',
                            help="Database name that existence we'd like to check")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if check_if_database_exist(**options):
            output = "0"
        else:
            output = "1"
        self.stdout.write(output)

# -*- coding: utf-8 -*-
import argparse
from typing import Any
from django.db import DEFAULT_DB_ALIAS
from django.core.management.base import BaseCommand

from zerver.lib.test_fixtures import get_migration_status


class Command(BaseCommand):
    help = "Get status of migrations."

    def add_arguments(self, parser):
        # type: (argparse.ArgumentParser) -> None
        parser.add_argument('app_label', nargs='?',
                            help='App label of an application to synchronize the state.')

        parser.add_argument('--database', action='store', dest='database',
                            default=DEFAULT_DB_ALIAS, help='Nominates a database to synchronize. '
                            'Defaults to the "default" database.')

        parser.add_argument('--output', action='store',
                            help='Path to store the status to (default to stdout).')

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        result = get_migration_status(**options)
        if options['output'] is not None:
            with open(options['output'], 'w') as f:
                f.write(result)
        else:
            self.stdout.write(result)

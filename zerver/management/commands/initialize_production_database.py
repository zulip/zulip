from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.server_initialization import create_internal_realm, server_initialized

settings.TORNADO_SERVER = None

class Command(BaseCommand):
    help = "Populate system realm and bots for a Zulip production server"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--extra-users',
                            dest='extra_users',
                            type=int,
                            default=0,
                            help='The number of extra users to create')

    def handle(self, *args: Any, **options: Any) -> None:
        if server_initialized():
            print("Database already initialized; doing nothing.")
            return
        create_internal_realm()

        self.stdout.write("Successfully populated database with initial data.\n")
        self.stdout.write("Please run ./manage.py generate_realm_creation_link "
                          "to generate link for creating organization")

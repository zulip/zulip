
import argparse
import os
import subprocess
import tarfile
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.import_realm import do_import_realm, do_import_system_bots
from zerver.forms import check_subdomain_available
from zerver.models import Client, DefaultStream, Huddle, \
    Message, Realm, RealmDomain, RealmFilter, Recipient, \
    Stream, Subscription, UserMessage, UserProfile

Model = Any  # TODO: make this mypy type more specific

class Command(BaseCommand):
    help = """Import Zulip database dump files into a fresh Zulip instance.

This command should be used only on a newly created, empty Zulip instance to
import a database dump from one or more JSON files."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--destroy-rebuild-database',
                            dest='destroy_rebuild_database',
                            default=False,
                            action="store_true",
                            help='Destroys and rebuilds the databases prior to import.')

        parser.add_argument('--import-into-nonempty',
                            dest='import_into_nonempty',
                            default=False,
                            action="store_true",
                            help='Import into an existing nonempty database.')

        parser.add_argument('subdomain', metavar='<subdomain>',
                            type=str, help="Subdomain")

        parser.add_argument('export_files', nargs='+',
                            metavar='<export file>',
                            help="list of JSON exports to import")
        parser.formatter_class = argparse.RawTextHelpFormatter

    def do_destroy_and_rebuild_database(self, db_name: str) -> None:
        call_command('flush', verbosity=0, interactive=False)
        subprocess.check_call([os.path.join(settings.DEPLOY_ROOT, "scripts/setup/flush-memcached")])

    def handle(self, *args: Any, **options: Any) -> None:
        subdomain = options['subdomain']
        export_file = options['export_files']

        if export_file is None:
            print("Add the export file path!")
            exit(1)
        if subdomain is None:
            print("Enter subdomain!")
            exit(1)

        if options["destroy_rebuild_database"]:
            print("Rebuilding the database!")
            db_name = settings.DATABASES['default']['NAME']
            self.do_destroy_and_rebuild_database(db_name)
        elif options["import_into_nonempty"]:
            print("WARNING: The argument 'import_into_nonempty' is depreciated.")
        else:
            print("Importing into the existing database!")

        check_subdomain_available(subdomain, from_management_command=True)

        for path in options['export_files']:
            if not os.path.exists(path):
                print("Directory not found: '%s'" % (path,))
                exit(1)

            try:
                tarfile.is_tarfile(path)
                print("Export file should be folder, not a tarfile!")
                exit(1)
            except IsADirectoryError:
                pass

            print("Processing dump: %s ..." % (path,))
            realm = do_import_realm(path, subdomain)
            print("Checking the system bots.")
            do_import_system_bots(realm)

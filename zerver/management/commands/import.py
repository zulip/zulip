
import argparse
import os
import subprocess
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser, CommandError

from zerver.lib.import_realm import do_import_realm, do_import_system_bots
from zerver.forms import check_subdomain_available

class Command(BaseCommand):
    help = """Import extracted Zulip database dump directories into a fresh Zulip instance.

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

        parser.add_argument('export_paths', nargs='+',
                            metavar='<export path>',
                            help="list of export directories to import")
        parser.add_argument('--processes',
                            dest='processes',
                            action="store",
                            default=6,
                            help='Number of processes to use for uploading Avatars to S3 in parallel')
        parser.formatter_class = argparse.RawTextHelpFormatter

    def do_destroy_and_rebuild_database(self, db_name: str) -> None:
        call_command('flush', verbosity=0, interactive=False)
        subprocess.check_call([os.path.join(settings.DEPLOY_ROOT, "scripts/setup/flush-memcached")])

    def handle(self, *args: Any, **options: Any) -> None:
        num_processes = int(options['processes'])
        if num_processes < 1:
            raise CommandError('You must have at least one process.')

        subdomain = options['subdomain']

        if options["destroy_rebuild_database"]:
            print("Rebuilding the database!")
            db_name = settings.DATABASES['default']['NAME']
            self.do_destroy_and_rebuild_database(db_name)
        elif options["import_into_nonempty"]:
            print("NOTE: The argument 'import_into_nonempty' is now the default behavior.")

        check_subdomain_available(subdomain, from_management_command=True)

        paths = []
        for path in options['export_paths']:
            path = os.path.realpath(os.path.expanduser(path))
            if not os.path.exists(path):
                print("Directory not found: '%s'" % (path,))
                exit(1)
            if not os.path.isdir(path):
                print("Export file should be folder; if it's a tarball, please unpack it first.")
                exit(1)
            paths.append(path)

        for path in paths:
            print("Processing dump: %s ..." % (path,))
            realm = do_import_realm(path, subdomain, num_processes)
            print("Checking the system bots.")
            do_import_system_bots(realm)


import argparse
import os
import subprocess
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

    def new_instance_check(self, model: Model) -> None:
        count = model.objects.count()
        if count:
            print("Zulip instance is not empty, found %d rows in %s table. "
                  % (count, model._meta.db_table))
            print("You may use --destroy-rebuild-database to destroy and "
                  "rebuild the database prior to import.")
            exit(1)

    def do_destroy_and_rebuild_database(self, db_name: str) -> None:
        call_command('flush', verbosity=0, interactive=False)
        subprocess.check_call([os.path.join(settings.DEPLOY_ROOT, "scripts/setup/flush-memcached")])

    def handle(self, *args: Any, **options: Any) -> None:
        models_to_import = [Realm, Stream, UserProfile, Recipient, Subscription,
                            Client, Message, UserMessage, Huddle, DefaultStream, RealmDomain,
                            RealmFilter]

        subdomain = options['subdomain']
        if subdomain is None:
            print("Enter subdomain!")
            exit(1)

        if options["destroy_rebuild_database"]:
            print("Rebuilding the database!")
            db_name = settings.DATABASES['default']['NAME']
            self.do_destroy_and_rebuild_database(db_name)
        elif not options["import_into_nonempty"]:
            for model in models_to_import:
                self.new_instance_check(model)

        check_subdomain_available(subdomain, from_management_command=True)

        for path in options['export_files']:
            if not os.path.exists(path):
                print("Directory not found: '%s'" % (path,))
                exit(1)

            print("Processing dump: %s ..." % (path,))
            realm = do_import_realm(path, subdomain)
            print("Checking the system bots.")
            do_import_system_bots(realm)

from __future__ import absolute_import
from __future__ import print_function

from optparse import make_option

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings

from zerver.lib.actions import do_create_stream
from zerver.models import Realm, Stream, UserProfile, Recipient, Subscription, \
    Message, UserMessage, Huddle, DefaultStream, RealmAlias, RealmFilter, Client

import sys
import json

class Command(BaseCommand):
    DEFAULT_CHUNK_SIZE = 5000

    help = """Import Zulip database dump files into a fresh Zulip instance.

This command should be used only on a newly created, empty Zulip instance to
import a database dump from one or more JSON files.

Usage: python2.7 manage.py import_dump [--destroy-rebuild-database] [--chunk-size=%s] <json file name> [<json file name>...]""" % DEFAULT_CHUNK_SIZE

    option_list = BaseCommand.option_list + (
        make_option('--destroy-rebuild-database',
                    dest='destroy_rebuild_database',
                    default=False,
                    action="store_true",
                    help='Destroys and rebuilds the databases prior to import.'),
        make_option('--chunk-size',
                    dest='chunk_size',
                    type='int',
                    default=DEFAULT_CHUNK_SIZE,
                    help='Number of objects that are added to the table in one roundtrip to the database.')
    )


    def new_instance_check(self, model):
        count = model.objects.count()
        if count:
            print("Zulip instance is not empty, found %d rows in %s table. " \
                % (count, model._meta.db_table))
            print("You may use --destroy-rebuild-database to destroy and rebuild the database prior to import.")
            exit(1)


    def do_destroy_and_rebuild_database(self, db_name):
        call_command('flush', verbosity=0, interactive=False)

    def increment_row_counter(self, row_counter, database_dump, model):
        table_name = model._meta.db_table
        row_counter[table_name] = (row_counter.get(table_name) or 0) + \
            len(database_dump.get(table_name) or [ ])


    def test_table_row_count(self, row_counter, model):
        table_name = model._meta.db_table
        sys.stdout.write("%s: " % (table_name,))
        expected_count = row_counter.get(table_name) or 0
        actual_count = model.objects.count()
        status = "PASSED" if expected_count == actual_count else "FAILED"
        sys.stdout.write("expected %d rows, got %d. %s\n" %
                         (expected_count, actual_count, status))


    def import_table(self, database_dump, realm_notification_map, model):
        table_name = model._meta.db_table
        if table_name in database_dump:
            cursor = connection.cursor()
            sys.stdout.write("Importing %s: " % (table_name,))
            accumulator = [ ]
            for row in database_dump[table_name]:
                # hack to filter out notifications_stream_id circular reference
                # out of zerver_realm table prior to insert of corresponding
                # streams.
                # removes notifications_stream_id from row dict
                if table_name == "zerver_realm":
                    realm_notification_map[row["id"]] = row.get("notifications_stream_id")
                    row = { field_name: value \
                        for field_name, value in row.items() \
                            if field_name != "notifications_stream_id" }

                accumulator.append(model(**row))
                if len(accumulator) % self.chunk_size == 0:
                    model.objects.bulk_create(accumulator)
                    sys.stdout.write(".")
                    accumulator = [ ]

            # create any remaining objects that haven't been flushed yet
            if len(accumulator):
                model.objects.bulk_create(accumulator)

            # set the next id sequence value to avoid a collision with the
            # imported ids
            cursor.execute("SELECT setval(%s, MAX(id)+1) FROM " + table_name,
                [table_name + "_id_seq"])

            sys.stdout.write(" [Done]\n")


    def handle(self, *args, **options):
        models_to_import = [Realm, Stream, UserProfile, Recipient, Subscription,
            Client, Message, UserMessage, Huddle, DefaultStream, RealmAlias,
            RealmFilter]

        self.chunk_size = options["chunk_size"]
        encoding = sys.getfilesystemencoding()

        if len(args) == 0:
            print("Please provide at least one database dump file name.")
            exit(1)

        if not options["destroy_rebuild_database"]:
            for model in models_to_import:
                self.new_instance_check(model)
        else:
            db_name = settings.DATABASES['default']['NAME']
            self.do_destroy_and_rebuild_database(db_name)

        # maps relationship between realm id and notifications_stream_id
        # generally, there should be only one realm per dump, but the code
        # doesn't make that assumption
        realm_notification_map = dict()

        # maping between table name and a total expected number of rows across
        # all input json files
        row_counter = dict()

        for file_name in args:
            try:
                fp = open(file_name, 'r')
            except IOError:
                print("File not found: '%s'" % (file_name,))
                exit(1)

            print("Processing file: %s ..." % (file_name,))

            # parse the database dump and load in memory
            # TODO: change this to a streaming parser to support loads > RAM size
            database_dump = json.load(fp, encoding)

            for model in models_to_import:
                self.increment_row_counter(row_counter, database_dump, model)
                self.import_table(database_dump, realm_notification_map, model)

            print("")

        # set notifications_stream_id on realm objects to correct value now
        # that foreign keys are in streams table
        if len(realm_notification_map):
            print("Setting realm notification stream...")
            for id, notifications_stream_id in realm_notification_map.items():
                Realm.objects \
                    .filter(id=id) \
                    .update(notifications_stream = notifications_stream_id)

        print("")
        print("Testing data import: ")

        # test that everything from all json dumps made it into the database
        for model in models_to_import:
            self.test_table_row_count(row_counter, model)

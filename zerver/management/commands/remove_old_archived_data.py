from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from zerver.lib.retention import delete_expired_archived_data


class Command(BaseCommand):
    help = """Remove old archived data
            Usage: ./manage.py [--dry-run|-d] remove_old_archived_data."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-d', '--dry-run',
                            dest='dry_run',
                            default=False,
                            action='store_true',
                            help="Just get removing info.")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        dry_run = options['dry_run']
        deliting_info = delete_expired_archived_data()
        if dry_run:
            for info in deliting_info:
                print("Realm ID: {}".format(info['realm_id']))
                print("Deleting archived messages qty: {}".format(info['del_arc_user_messages']))
                print("Deleting archived user messages qty: {}".format(info['del_arc_messages']))
                print("Deleting archived attachemnts qty: {}".format(info['del_arc_attachments']))

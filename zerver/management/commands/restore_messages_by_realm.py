from __future__ import absolute_import
from __future__ import print_function

from typing import Any
from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from zerver.lib.retention import restore_realm_archived_data
from zerver.models import get_realm


class Command(BaseCommand):
    help = """Restore archived data by realm
                Usage: ./manage.py [--dry-run|-d] restore_messages_by_realm."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('domain', metavar='<domain>', type=str,
                            help='The domain of the realm to restore messages data to.')
        parser.add_argument('-d', '--dry-run',
                            dest='dry_run',
                            default=False,
                            action='store_true',
                            help="Just get restore info.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = get_realm(options["domain"])
        dry_run = options['dry_run']
        restore_info = restore_realm_archived_data(realm_id=realm.id, dry_run=dry_run)
        if dry_run:
            print("Restoring messages qty: {}".format(restore_info['restoring_arc_messages']))
            print("Restoring user messages qty: {}".format(
                restore_info['restoring_arc_user_messages']))
            print("Restoring attachemnts qty: {}".format(restore_info['restoring_arc_attachemnts']))
            print("Restoring attachemnts messages qty: {}".format(
                restore_info['rest_arc_attachments_messages']))

from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from zerver.lib.retention import archive_messages


class Command(BaseCommand):
    help = """Archive messages after retention period
        Usage: ./manage.py [--dry-run|-d] archive_messages."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-d', '--dry-run',
                            dest='dry_run',
                            default=False,
                            action='store_true',
                            help="Just get archiving info.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        dry_run = options['dry_run']
        archive_info = archive_messages(dry_run)
        if dry_run:
            for info in archive_info:
                print("Realm ID: {}".format(info['realm_id']))
                print("Expired messages qty: {}".format(info['exp_messages']))
                print("Expired user messages qty: {}".format(info['exp_user_messages']))
                print("Expired attachemnts qty: {}".format(info['exp_attachments']))
                print("Expired attachemnts messages qty: {}".format(
                    info['exp_attachments_messages']))

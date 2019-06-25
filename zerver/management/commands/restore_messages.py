from django.core.management.base import CommandParser

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.retention import restore_all_data_from_archive, \
    restore_data_from_archive_by_realm, restore_data_from_archive
from zerver.models import ArchiveTransaction

from typing import Any

class Command(ZulipBaseCommand):
    help = """
Restore recently deleted messages from the archive, that
have not been vacuumed (because the time limit of
ARCHIVED_DATA_VACUUMING_DELAY_DAYS has not passed).

Intended primarily for use after against potential bugs in
Zulip's message retention and deletion features.

Examples:
To restore all recently deleted messages:
  ./manage.py restore_messages
To restore a specfic ArchiveTransaction:
  ./manage.py restore_messages --transaction-id=1
"""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('-d', '--restore-deleted',
                            dest='restore_deleted',
                            action='store_true',
                            help='Restore manually deleted messages.')
        parser.add_argument('-t', '--transaction-id',
                            dest='transaction_id',
                            type=int,
                            help='Restore a specific ArchiveTransaction.')

        self.add_realm_args(parser, help='Restore archived messages from the specified realm. '
                                         '(Does not restore manually deleted messages.)')

    def handle(self, **options: Any) -> None:
        realm = self.get_realm(options)
        if realm:
            restore_data_from_archive_by_realm(realm)
        elif options['transaction_id']:
            restore_data_from_archive(ArchiveTransaction.objects.get(id=options['transaction_id']))
        else:
            restore_all_data_from_archive(restore_manual_transactions=options['restore_deleted'])

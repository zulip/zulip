from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import BaseCommand

from argparse import ArgumentParser
import sys

from zerver.lib.migrate import (
    migrate_all_messages,
    create_topics_for_message_range,
)


class Command(BaseCommand):
    help = """Backfill Topic froms Message (run with care!)."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('batch_size', type=int,
                            help='size of range of Message.id')
        parser.add_argument('max_num_batches', type=int,
                            help='size of range of Message.id')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        batch_size = int(options['batch_size'])
        max_num_batches = int(options['max_num_batches'])
        assert batch_size >= 1
        assert max_num_batches >= 1
        assert max_num_batches <= 100000

        migrate_all_messages(
            range_method=create_topics_for_message_range,
            batch_size=batch_size,
            max_num_batches=max_num_batches,
            verbose=True,
        )

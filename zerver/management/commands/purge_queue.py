from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from django.core.management import CommandError
from zerver.lib.queue import SimpleQueueClient

class Command(BaseCommand):
    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('queue_name', metavar='<queue name>', type=str,
                            help="queue to purge")

    help = "Discards all messages from the given queue"
    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        queue_name = options['queue_name']
        queue = SimpleQueueClient()
        queue.ensure_queue(queue_name, lambda: None)
        queue.channel.queue_purge(queue_name)
        print("Done")

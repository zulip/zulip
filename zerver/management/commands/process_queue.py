from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.core.management import CommandError
from django.conf import settings
from zerver.worker.queue_processors import get_worker
import sys
import signal
import logging

class Command(BaseCommand):
    args = "<queue name>"
    help = "Runs a queue processing worker"
    def handle(self, *args, **options):
        logging.basicConfig()
        logger = logging.getLogger('process_queue')

        if len(args) != 1:
            raise CommandError("Wrong number of arguments")

        def signal_handler(signal, frame):
            logger.info("Disconnecting from queue")
            worker.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        logger.info("Connecting to queue")
        worker = get_worker(args[0])
        worker.start()


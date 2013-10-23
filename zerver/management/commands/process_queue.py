from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.core.management import CommandError
from django.conf import settings
from zerver.worker.queue_processors import get_worker
import sys
import signal
import logging

class Command(BaseCommand):
    args = "<queue name> [<worker number>]"
    help = "Runs a queue processing worker"
    def handle(self, *args, **options):
        logging.basicConfig()
        logger = logging.getLogger('process_queue')

        if len(args) not in (1, 2):
            raise CommandError("Wrong number of arguments")

        queue_name = args[0]
        if len(args) > 1:
            worker_num = int(args[1])
        else:
            worker_num = 0

        def signal_handler(signal, frame):
            logger.info("Worker %d disconnecting from queue %s" % (worker_num, queue_name))
            worker.stop()
            sys.exit(0)

        if not settings.USING_RABBITMQ:
            logger.error("Cannot run a queue processor when USING_RABBITMQ is False!")
            sys.exit(1)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        logger.info("Worker %d connecting to queue %s" % (worker_num, queue_name))
        worker = get_worker(queue_name)
        worker.start()


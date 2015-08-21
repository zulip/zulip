from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.core.management import CommandError
from django.conf import settings
from zerver.worker.queue_processors import get_worker
import sys
import signal
import logging

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('queue_name', metavar='<queue name>', type=str,
                            help="queue to process")
        parser.add_argument('worker_num', metavar='<worker number>', type=int, nargs='?', default=0,
                            help="worker label")

    help = "Runs a queue processing worker"
    def handle(self, *args, **options):
        logging.basicConfig()
        logger = logging.getLogger('process_queue')

        queue_name = options['queue_name']
        worker_num = options['worker_num']

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


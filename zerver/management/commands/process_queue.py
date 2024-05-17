import logging
import os
import signal
import sys
import threading
from argparse import ArgumentParser
from contextlib import contextmanager
from types import FrameType
from typing import Any, Iterator, List, Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import autoreload
from sentry_sdk import configure_scope
from typing_extensions import override

from zerver.worker.queue_processors import get_active_worker_queues, get_worker


@contextmanager
def log_and_exit_if_exception(
    logger: logging.Logger, queue_name: str, threaded: bool
) -> Iterator[None]:
    try:
        yield
    except Exception:
        logger.exception("Unhandled exception from queue: %s", queue_name, stack_info=True)
        if threaded:
            # Sending SIGUSR1 is the right way to exit - triggering the
            # exit_with_three signal handler, causing exit and reload.
            os.kill(os.getpid(), signal.SIGUSR1)
        else:
            sys.exit(1)


class Command(BaseCommand):
    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--queue_name", metavar="<queue name>", help="queue to process")
        parser.add_argument(
            "--worker_num", metavar="<worker number>", type=int, default=0, help="worker label"
        )
        parser.add_argument("--all", action="store_true", help="run all queues")
        parser.add_argument(
            "--multi_threaded",
            nargs="+",
            metavar="<list of queue name>",
            required=False,
            help="list of queue to process",
        )

    help = "Runs a queue processing worker"

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        logging.basicConfig()
        logger = logging.getLogger("process_queue")

        def exit_with_three(signal: int, frame: Optional[FrameType]) -> None:
            """
            This process is watched by Django's autoreload, so exiting
            with status code 3 will cause this process to restart.
            """
            logger.warning("SIGUSR1 received. Restarting this queue processor.")
            sys.exit(3)

        if not settings.USING_RABBITMQ:
            # Make the warning silent when running the tests
            if settings.TEST_SUITE:
                logger.info("Not using RabbitMQ queue workers in the test suite.")
            else:
                logger.error("Cannot run a queue processor when USING_RABBITMQ is False!")
            raise CommandError

        def run_threaded_workers(queues: List[str], logger: logging.Logger) -> None:
            cnt = 0
            for queue_name in queues:
                if not settings.DEVELOPMENT:
                    logger.info("launching queue worker thread %s", queue_name)
                cnt += 1
                td = ThreadedWorker(queue_name, logger)
                td.start()
            assert len(queues) == cnt
            logger.info("%d queue worker threads were launched", cnt)

        if options["all"]:
            signal.signal(signal.SIGUSR1, exit_with_three)
            autoreload.run_with_reloader(run_threaded_workers, get_active_worker_queues(), logger)
        elif options["multi_threaded"]:
            signal.signal(signal.SIGUSR1, exit_with_three)
            queues = options["multi_threaded"]
            autoreload.run_with_reloader(run_threaded_workers, queues, logger)
        else:
            queue_name = options["queue_name"]
            worker_num = options["worker_num"]

            def signal_handler(signal: int, frame: Optional[FrameType]) -> None:
                logger.info("Worker %d disconnecting from queue %s", worker_num, queue_name)
                worker.stop()
                sys.exit(0)

            logger.info("Worker %d connecting to queue %s", worker_num, queue_name)
            with log_and_exit_if_exception(logger, queue_name, threaded=False):
                worker = get_worker(queue_name, worker_num=worker_num)
                with configure_scope() as scope:
                    scope.set_tag("queue_worker", queue_name)
                    scope.set_tag("worker_num", worker_num)

                    worker.setup()
                    signal.signal(signal.SIGTERM, signal_handler)
                    signal.signal(signal.SIGINT, signal_handler)
                    signal.signal(signal.SIGUSR1, signal_handler)
                    worker.start()


class ThreadedWorker(threading.Thread):
    def __init__(self, queue_name: str, logger: logging.Logger) -> None:
        threading.Thread.__init__(self)
        self.logger = logger
        self.queue_name = queue_name

    @override
    def run(self) -> None:
        with configure_scope() as scope, log_and_exit_if_exception(
            self.logger, self.queue_name, threaded=True
        ):
            scope.set_tag("queue_worker", self.queue_name)
            worker = get_worker(self.queue_name, threaded=True)
            worker.setup()
            logging.debug("starting consuming %s", self.queue_name)
            worker.start()

import logging
import os
import signal
import sys
import threading
from argparse import ArgumentParser
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any

import sentry_sdk
from django.conf import settings
from django.core.management.base import CommandError
from django.utils import autoreload
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.worker.base import QueueProcessingWorker
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


class Command(ZulipBaseCommand):
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

        def exit_with_three(signal: int, frame: FrameType | None) -> None:
            """
            With --all, this process is watched by Django's autoreload,
            so exiting with status code 3 will cause this process to
            restart.  With --multi_threaded, supervisor restarts it.
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

        def run_threaded_workers(threads: list[ThreadedWorker], logger: logging.Logger) -> None:
            for td in threads:
                if not settings.DEVELOPMENT:
                    logger.info("launching queue worker thread %s", td.queue_name)
                td.start()
            logger.info("%d queue worker threads were launched", len(threads))

        if options["all"]:
            signal.signal(signal.SIGUSR1, exit_with_three)
            threads = [
                ThreadedWorker(queue_name, logger) for queue_name in get_active_worker_queues()
            ]
            autoreload.run_with_reloader(run_threaded_workers, threads, logger)
        elif options["multi_threaded"]:
            # Unlike with --all, which is used in development, we do
            # not run under Django's autoreload: its SIGTERM handling
            # kills the worker threads immediately, interrupting the
            # events they are processing.
            threads = [
                ThreadedWorker(queue_name, logger) for queue_name in options["multi_threaded"]
            ]

            def stop_threads(signal: int, frame: FrameType | None) -> None:
                logger.info("Stopping queue worker threads")
                for td in threads:
                    td.stop_after_current_events()

            signal.signal(signal.SIGTERM, stop_threads)
            signal.signal(signal.SIGINT, stop_threads)
            signal.signal(signal.SIGUSR1, exit_with_three)
            run_threaded_workers(threads, logger)
            for td in threads:
                td.join()
        else:
            queue_name = options["queue_name"]
            worker_num = options["worker_num"]

            def disconnect() -> None:
                logger.info("Worker %d disconnecting from queue %s", worker_num, queue_name)
                worker.stop()

            def signal_handler(signal: int, frame: FrameType | None) -> None:
                disconnect()
                sys.exit(0)

            def stop_after_current_events_handler(signal: int, frame: FrameType | None) -> None:
                worker.stop_after_current_events()

            logger.info("Worker %d connecting to queue %s", worker_num, queue_name)
            with log_and_exit_if_exception(logger, queue_name, threaded=False):
                worker = get_worker(queue_name, worker_num=worker_num)
                with sentry_sdk.isolation_scope() as scope:
                    scope.set_tag("queue_worker", queue_name)
                    scope.set_tag("worker_num", worker_num)

                    worker.setup()
                    # SIGTERM and SIGINT are requests to stop, so we let
                    # the worker finish the events it is in the middle
                    # of.  SIGUSR1 is sent by check_and_send_restart_signal
                    # when consuming failed, so we exit immediately, and
                    # RabbitMQ redelivers those events after the restart.
                    signal.signal(signal.SIGTERM, stop_after_current_events_handler)
                    signal.signal(signal.SIGINT, stop_after_current_events_handler)
                    signal.signal(signal.SIGUSR1, signal_handler)
                    worker.start()
                    disconnect()


class ThreadedWorker(threading.Thread):
    def __init__(self, queue_name: str, logger: logging.Logger) -> None:
        # Daemon threads, so that exiting the main thread on SIGUSR1
        # does not wait for them to finish.
        threading.Thread.__init__(self, daemon=True)
        self.logger = logger
        self.queue_name = queue_name
        self.worker: QueueProcessingWorker | None = None
        self.stop_requested = False

    def stop_after_current_events(self) -> None:
        self.stop_requested = True
        if self.worker is not None:
            self.worker.stop_after_current_events()

    @override
    def run(self) -> None:
        with (
            sentry_sdk.isolation_scope() as scope,
            log_and_exit_if_exception(self.logger, self.queue_name, threaded=True),
        ):
            scope.set_tag("queue_worker", self.queue_name)
            worker = get_worker(self.queue_name, threaded=True)
            worker.setup()
            # stop_after_current_events is called from the main thread,
            # so it may have run before self.worker was set; it sets
            # stop_requested before checking self.worker, and we check
            # stop_requested after setting it.
            self.worker = worker
            if self.stop_requested:
                return
            logging.debug("starting consuming %s", self.queue_name)
            worker.start()
            worker.stop()

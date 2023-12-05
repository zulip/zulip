# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
import os
import signal
import time
from abc import ABC, abstractmethod
from collections import deque
from types import FrameType
from typing import Any, Callable, Dict, List, MutableSequence, Optional, Set, Tuple, Type, TypeVar

import orjson
import sentry_sdk
from django.conf import settings
from django.db import connection
from typing_extensions import override

from zerver.lib.context_managers import lockfile
from zerver.lib.db_connections import reset_queries
from zerver.lib.partial import partial
from zerver.lib.per_request_cache import flush_per_request_caches
from zerver.lib.pysa import mark_sanitized
from zerver.lib.queue import SimpleQueueClient

logger = logging.getLogger(__name__)


class WorkerTimeoutError(Exception):
    def __init__(self, queue_name: str, limit: int, event_count: int) -> None:
        self.queue_name = queue_name
        self.limit = limit
        self.event_count = event_count

    @override
    def __str__(self) -> str:
        return f"Timed out in {self.queue_name} after {self.limit * self.event_count} seconds processing {self.event_count} events"


class InterruptConsumeError(Exception):
    """
    This exception is to be thrown inside event consume function
    if the intention is to simply interrupt the processing
    of the current event and normally continue the work of the queue.
    """


class WorkerDeclarationError(Exception):
    pass


ConcreteQueueWorker = TypeVar("ConcreteQueueWorker", bound="QueueProcessingWorker")


def assign_queue(
    queue_name: str,
    enabled: bool = True,
    is_test_queue: bool = False,
) -> Callable[[Type[ConcreteQueueWorker]], Type[ConcreteQueueWorker]]:
    def decorate(clazz: Type[ConcreteQueueWorker]) -> Type[ConcreteQueueWorker]:
        clazz.queue_name = queue_name
        if enabled:
            register_worker(queue_name, clazz, is_test_queue)
        return clazz

    return decorate


worker_classes: Dict[str, Type["QueueProcessingWorker"]] = {}
test_queues: Set[str] = set()


def register_worker(
    queue_name: str, clazz: Type["QueueProcessingWorker"], is_test_queue: bool = False
) -> None:
    worker_classes[queue_name] = clazz
    if is_test_queue:
        test_queues.add(queue_name)


def check_and_send_restart_signal() -> None:
    try:
        if not connection.is_usable():
            logging.warning("*** Sending self SIGUSR1 to trigger a restart.")
            os.kill(os.getpid(), signal.SIGUSR1)
    except Exception:
        pass


class QueueProcessingWorker(ABC):
    queue_name: str
    MAX_CONSUME_SECONDS: Optional[int] = 30
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 50
    MAX_SECONDS_BEFORE_UPDATE_STATS = 30

    # How many un-acknowledged events the worker should have on hand,
    # fetched from the rabbitmq server.  Larger values may be more
    # performant, but if queues are large, cause more network IO at
    # startup and steady-state memory.
    PREFETCH = 100

    def __init__(
        self,
        threaded: bool = False,
        disable_timeout: bool = False,
        worker_num: Optional[int] = None,
    ) -> None:
        self.q: Optional[SimpleQueueClient] = None
        self.threaded = threaded
        self.disable_timeout = disable_timeout
        self.worker_num = worker_num
        if not hasattr(self, "queue_name"):
            raise WorkerDeclarationError("Queue worker declared without queue_name")

        self.initialize_statistics()

    def initialize_statistics(self) -> None:
        self.queue_last_emptied_timestamp = time.time()
        self.consumed_since_last_emptied = 0
        self.recent_consume_times: MutableSequence[Tuple[int, float]] = deque(maxlen=50)
        self.consume_iteration_counter = 0
        self.idle = True
        self.last_statistics_update_time = 0.0

        self.update_statistics()

    @sentry_sdk.trace
    def update_statistics(self) -> None:
        total_seconds = sum(seconds for _, seconds in self.recent_consume_times)
        total_events = sum(events_number for events_number, _ in self.recent_consume_times)
        if total_events == 0:
            recent_average_consume_time = None
        else:
            recent_average_consume_time = total_seconds / total_events
        stats_dict = dict(
            update_time=time.time(),
            recent_average_consume_time=recent_average_consume_time,
            queue_last_emptied_timestamp=self.queue_last_emptied_timestamp,
            consumed_since_last_emptied=self.consumed_since_last_emptied,
        )

        os.makedirs(settings.QUEUE_STATS_DIR, exist_ok=True)

        fname = f"{self.queue_name}.stats"
        fn = os.path.join(settings.QUEUE_STATS_DIR, fname)
        with lockfile(fn + ".lock"):
            tmp_fn = fn + ".tmp"
            with open(tmp_fn, "wb") as f:
                f.write(
                    orjson.dumps(stats_dict, option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2)
                )
            os.rename(tmp_fn, fn)
        self.last_statistics_update_time = time.time()

    def get_remaining_local_queue_size(self) -> int:
        if self.q is not None:
            return self.q.local_queue_size()
        else:
            # This is a special case that will happen if we're operating without
            # using RabbitMQ (e.g. in tests). In that case there's no queuing to speak of
            # and the only reasonable size to return is 0.
            return 0

    @abstractmethod
    def consume(self, data: Dict[str, Any]) -> None:
        pass

    def do_consume(
        self, consume_func: Callable[[List[Dict[str, Any]]], None], events: List[Dict[str, Any]]
    ) -> None:
        consume_time_seconds: Optional[float] = None
        with sentry_sdk.start_transaction(
            op="task",
            name=f"consume {self.queue_name}",
            custom_sampling_context={"queue": self.queue_name},
        ):
            sentry_sdk.add_breadcrumb(
                type="debug",
                category="queue_processor",
                message=f"Consuming {self.queue_name}",
                data={"events": events, "local_queue_size": self.get_remaining_local_queue_size()},
            )
            try:
                if self.idle:
                    # We're reactivating after having gone idle due to emptying the queue.
                    # We should update the stats file to keep it fresh and to make it clear
                    # that the queue started processing, in case the event we're about to process
                    # makes us freeze.
                    self.idle = False
                    self.update_statistics()

                time_start = time.time()
                if self.MAX_CONSUME_SECONDS and not self.threaded and not self.disable_timeout:
                    try:
                        signal.signal(
                            signal.SIGALRM,
                            partial(self.timer_expired, self.MAX_CONSUME_SECONDS, events),
                        )
                        try:
                            signal.alarm(self.MAX_CONSUME_SECONDS * len(events))
                            consume_func(events)
                        finally:
                            signal.alarm(0)
                    finally:
                        signal.signal(signal.SIGALRM, signal.SIG_DFL)
                else:
                    consume_func(events)
                consume_time_seconds = time.time() - time_start
                self.consumed_since_last_emptied += len(events)
            except Exception as e:
                self._handle_consume_exception(events, e)
            finally:
                flush_per_request_caches()
                reset_queries()

                with sentry_sdk.start_span(description="statistics"):
                    if consume_time_seconds is not None:
                        self.recent_consume_times.append((len(events), consume_time_seconds))

                    remaining_local_queue_size = self.get_remaining_local_queue_size()
                    if remaining_local_queue_size == 0:
                        self.queue_last_emptied_timestamp = time.time()
                        self.consumed_since_last_emptied = 0
                        # We've cleared all the events from the queue, so we don't
                        # need to worry about the small overhead of doing a disk write.
                        # We take advantage of this to update the stats file to keep it fresh,
                        # especially since the queue might go idle until new events come in.
                        self.update_statistics()
                        self.idle = True
                    else:
                        self.consume_iteration_counter += 1
                        if (
                            self.consume_iteration_counter
                            >= self.CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM
                            or time.time() - self.last_statistics_update_time
                            >= self.MAX_SECONDS_BEFORE_UPDATE_STATS
                        ):
                            self.consume_iteration_counter = 0
                            self.update_statistics()

    def consume_single_event(self, event: Dict[str, Any]) -> None:
        consume_func = lambda events: self.consume(events[0])
        self.do_consume(consume_func, [event])

    def timer_expired(
        self, limit: int, events: List[Dict[str, Any]], signal: int, frame: Optional[FrameType]
    ) -> None:
        raise WorkerTimeoutError(self.queue_name, limit, len(events))

    def _handle_consume_exception(self, events: List[Dict[str, Any]], exception: Exception) -> None:
        if isinstance(exception, InterruptConsumeError):
            # The exception signals that no further error handling
            # is needed and the worker can proceed.
            return

        with sentry_sdk.configure_scope() as scope:
            scope.set_context(
                "events",
                {
                    "data": events,
                    "queue_name": self.queue_name,
                },
            )
            if isinstance(exception, WorkerTimeoutError):
                with sentry_sdk.push_scope() as scope:
                    scope.fingerprint = ["worker-timeout", self.queue_name]
                    logging.exception(exception, stack_info=True)
            else:
                logging.exception(
                    "Problem handling data on queue %s", self.queue_name, stack_info=True
                )
        if not os.path.exists(settings.QUEUE_ERROR_DIR):
            os.mkdir(settings.QUEUE_ERROR_DIR)  # nocoverage
        # Use 'mark_sanitized' to prevent Pysa from detecting this false positive
        # flow. 'queue_name' is always a constant string.
        fname = mark_sanitized(f"{self.queue_name}.errors")
        fn = os.path.join(settings.QUEUE_ERROR_DIR, fname)
        line = f"{time.asctime()}\t{orjson.dumps(events).decode()}\n"
        lock_fn = fn + ".lock"
        with lockfile(lock_fn):
            with open(fn, "a") as f:
                f.write(line)
        check_and_send_restart_signal()

    def setup(self) -> None:
        self.q = SimpleQueueClient(prefetch=self.PREFETCH)

    def start(self) -> None:
        assert self.q is not None
        self.initialize_statistics()
        self.q.start_json_consumer(
            self.queue_name,
            lambda events: self.consume_single_event(events[0]),
        )

    def stop(self) -> None:  # nocoverage
        assert self.q is not None
        self.q.stop_consuming()


class LoopQueueProcessingWorker(QueueProcessingWorker):
    sleep_delay = 1
    batch_size = 100

    @override
    def setup(self) -> None:
        self.q = SimpleQueueClient(prefetch=max(self.PREFETCH, self.batch_size))

    @override
    def start(self) -> None:  # nocoverage
        assert self.q is not None
        self.initialize_statistics()
        self.q.start_json_consumer(
            self.queue_name,
            lambda events: self.do_consume(self.consume_batch, events),
            batch_size=self.batch_size,
            timeout=self.sleep_delay,
        )

    @abstractmethod
    def consume_batch(self, events: List[Dict[str, Any]]) -> None:
        pass

    @override
    def consume(self, event: Dict[str, Any]) -> None:
        """In LoopQueueProcessingWorker, consume is used just for automated tests"""
        self.consume_batch([event])

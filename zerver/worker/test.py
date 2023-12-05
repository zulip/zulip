# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

import orjson
from django.conf import settings
from typing_extensions import override

from zerver.worker.base import LoopQueueProcessingWorker, QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("test", is_test_queue=True)
class TestWorker(QueueProcessingWorker):
    # This worker allows you to test the queue worker infrastructure without
    # creating significant side effects.  It can be useful in development or
    # for troubleshooting prod/staging.  It pulls a message off the test queue
    # and appends it to a file in /var/log/zulip.
    @override
    def consume(self, event: Mapping[str, Any]) -> None:  # nocoverage
        fn = settings.ZULIP_WORKER_TEST_FILE
        message = orjson.dumps(event)
        logging.info("TestWorker should append this message to %s: %s", fn, message.decode())
        with open(fn, "ab") as f:
            f.write(message + b"\n")


@assign_queue("noop", is_test_queue=True)
class NoopWorker(QueueProcessingWorker):
    """Used to profile the queue processing framework, in zilencer's queue_rate."""

    def __init__(
        self,
        threaded: bool = False,
        disable_timeout: bool = False,
        worker_num: Optional[int] = None,
        max_consume: int = 1000,
        slow_queries: Sequence[int] = [],
    ) -> None:
        super().__init__(threaded, disable_timeout, worker_num)
        self.consumed = 0
        self.max_consume = max_consume
        self.slow_queries: Set[int] = set(slow_queries)

    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        self.consumed += 1
        if self.consumed in self.slow_queries:
            logging.info("Slow request...")
            time.sleep(60)
            logging.info("Done!")
        if self.consumed >= self.max_consume:
            self.stop()


@assign_queue("noop_batch", is_test_queue=True)
class BatchNoopWorker(LoopQueueProcessingWorker):
    """Used to profile the queue processing framework, in zilencer's queue_rate."""

    batch_size = 100

    def __init__(
        self,
        threaded: bool = False,
        disable_timeout: bool = False,
        max_consume: int = 1000,
        slow_queries: Sequence[int] = [],
    ) -> None:
        super().__init__(threaded, disable_timeout)
        self.consumed = 0
        self.max_consume = max_consume
        self.slow_queries: Set[int] = set(slow_queries)

    @override
    def consume_batch(self, events: List[Dict[str, Any]]) -> None:
        event_numbers = set(range(self.consumed + 1, self.consumed + 1 + len(events)))
        found_slow = self.slow_queries & event_numbers
        if found_slow:
            logging.info("%d slow requests...", len(found_slow))
            time.sleep(60 * len(found_slow))
            logging.info("Done!")
        self.consumed += len(events)
        if self.consumed >= self.max_consume:
            self.stop()

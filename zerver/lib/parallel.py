import logging
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ProcessPoolExecutor
from contextlib import contextmanager
from typing import Any, TypeVar

import bmemcached
from django.conf import settings
from django.core.cache import cache
from django.db import connection

from zerver.lib.partial import partial
from zerver.lib.queue import get_queue_client

ParallelRecordType = TypeVar("ParallelRecordType")


def _disconnect() -> None:
    # Close our database, cache, and RabbitMQ connections, so our
    # forked children do not share them.  Django will transparently
    # re-open them as needed.
    connection.close()
    _cache = cache._cache  # type: ignore[attr-defined] # not in stubs
    assert isinstance(_cache, bmemcached.Client)
    _cache.disconnect_all()

    rabbitmq_client = get_queue_client()
    if rabbitmq_client.connection and rabbitmq_client.connection.is_open:
        rabbitmq_client.close()


def func_with_catch(func: Callable[[ParallelRecordType], None], item: ParallelRecordType) -> None:
    try:
        return func(item)
    except Exception:
        logging.exception("Error processing item: %s", item, stack_info=True)


def run_parallel(
    func: Callable[[ParallelRecordType], None],
    records: Iterable[ParallelRecordType],
    processes: int,
    *,
    initializer: Callable[..., None] | None = None,
    initargs: tuple[Any, ...] = tuple(),
    catch: bool = False,
    report_every: int = 1000,
    report: Callable[[int], None] | None = None,
) -> None:  # nocoverage
    with run_parallel_queue(
        func,
        processes,
        initializer=initializer,
        initargs=initargs,
        catch=catch,
        report_every=report_every,
        report=report,
    ) as submit:
        for record in records:
            submit(record)


@contextmanager
def run_parallel_queue(
    func: Callable[[ParallelRecordType], None],
    processes: int,
    *,
    initializer: Callable[..., None] | None = None,
    initargs: tuple[Any, ...] = tuple(),
    catch: bool = False,
    report_every: int = 1000,
    report: Callable[[int], None] | None = None,
) -> Iterator[Callable[[ParallelRecordType], None]]:  # nocoverage
    assert processes > 0
    if settings.TEST_SUITE:
        assert processes == 1

    wrapped_func = partial(func_with_catch, func) if catch else func

    completed = 0
    if processes == 1:

        def func_with_notify(item: ParallelRecordType) -> None:
            wrapped_func(item)
            nonlocal completed
            completed += 1
            if report is not None and completed % report_every == 0:
                report(completed)

        if initializer is not None:
            initializer(*initargs)
        yield func_with_notify
        return

    _disconnect()

    with ProcessPoolExecutor(
        max_workers=processes, initializer=initializer, initargs=initargs
    ) as executor:

        def report_callback(future: Future[None]) -> None:
            future.result()
            nonlocal completed
            completed += 1
            if report is not None and completed % report_every == 0:
                report(completed)

        def future_with_notify(item: ParallelRecordType) -> None:
            future = executor.submit(wrapped_func, item)
            future.add_done_callback(report_callback)

        try:
            yield future_with_notify
        finally:
            executor.shutdown()

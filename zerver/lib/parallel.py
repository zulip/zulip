import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import current_process
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
    if isinstance(_cache, bmemcached.Client):  # nocoverage
        # In tests, this is an OrderedDict
        _cache.disconnect_all()

    if settings.USING_RABBITMQ:  # nocoverage
        rabbitmq_client = get_queue_client()
        if rabbitmq_client.connection and rabbitmq_client.connection.is_open:
            rabbitmq_client.close()


def func_with_catch(func: Callable[[ParallelRecordType], None], item: ParallelRecordType) -> None:
    try:
        return func(item)
    except Exception:
        logging.exception("Error processing item: %s", item)


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
    assert processes > 0
    if settings.TEST_SUITE and current_process().daemon:
        assert processes == 1, "Only one process possible under parallel tests"

    wrapped_func = partial(func_with_catch, func) if catch else func

    if processes == 1:
        if initializer is not None:
            initializer(*initargs)
        for count, record in enumerate(records, 1):
            wrapped_func(record)
            if report is not None and count % report_every == 0:
                report(count)
        return

    _disconnect()

    with ProcessPoolExecutor(
        max_workers=processes, initializer=initializer, initargs=initargs
    ) as executor:
        for count, future in enumerate(
            as_completed(executor.submit(wrapped_func, record) for record in records), 1
        ):
            future.result()
            if report is not None and count % report_every == 0:
                report(count)

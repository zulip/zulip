import logging
import os
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import BrokenExecutor, Future, ProcessPoolExecutor
from contextlib import contextmanager
from multiprocessing import current_process, forkserver, get_context
from typing import Any, TypeVar

import bmemcached
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.db import connection

from zerver.lib.partial import partial
from zerver.lib.queue import get_queue_client

ParallelRecordType = TypeVar("ParallelRecordType")


def _disconnect() -> None:
    # Close the database, cache, and RabbitMQ connections, so that
    # processes forked from this one do not share them.  Django will
    # transparently re-open them as needed.
    connection.close()
    _cache = cache._cache  # type: ignore[attr-defined] # not in stubs
    if isinstance(_cache, bmemcached.Client):  # nocoverage
        # In tests, this is an OrderedDict
        _cache.disconnect_all()

    if settings.USING_RABBITMQ:  # nocoverage
        rabbitmq_client = get_queue_client()
        if rabbitmq_client.connection and rabbitmq_client.connection.is_open:
            rabbitmq_client.close()


def _worker_has_django_loaded() -> bool:  # nocoverage
    return apps.ready


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
) -> None:
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
) -> Iterator[Callable[[ParallelRecordType], None]]:
    assert processes > 0
    if settings.TEST_SUITE and current_process().daemon:  # nocoverage
        assert processes == 1, "Only one process possible under parallel tests"

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

    else:  # nocoverage
        # Workers are forked from the multiprocessing "forkserver,"
        # not from this process, so they do not inherit -- and thus
        # share -- this process's database, cache, and RabbitMQ
        # connections; concurrent use of a shared connection corrupts
        # its wire protocol.  The preload module sets up Django in
        # the forkserver, and then drops any connections that doing
        # so opened.
        forkserver.set_forkserver_preload(["zerver.lib.parallel_preload"])

        # Python 3.10's forkserver does not inherit sys.path from
        # this process, so it would (silently!) fail to import the
        # preload module when run from outside the deployment root;
        # see https://github.com/python/cpython/issues/90876, fixed
        # in Python 3.11.  Provide the path via PYTHONPATH while
        # starting the forkserver.
        old_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = os.pathsep.join(
            [settings.DEPLOY_ROOT] + ([old_pythonpath] if old_pythonpath is not None else [])
        )
        try:
            forkserver.ensure_running()
        finally:
            if old_pythonpath is None:
                del os.environ["PYTHONPATH"]
            else:
                os.environ["PYTHONPATH"] = old_pythonpath

        exceptions = []
        try:
            with ProcessPoolExecutor(
                max_workers=processes,
                mp_context=get_context("forkserver"),
                initializer=initializer,
                initargs=initargs,
            ) as executor:
                # The forkserver ignores failures to import the
                # preload module, so verify, before starting on any
                # real work, that Django is set up in the workers --
                # most work items cannot even be unpickled without
                # their Django models.
                if not executor.submit(_worker_has_django_loaded).result():
                    raise Exception(
                        "forkserver failed to preload zerver.lib.parallel_preload, "
                        "so workers cannot load Django"
                    )

                def report_callback(future: Future[None]) -> None:
                    if exc := future.exception():
                        exceptions.append(exc)
                        return

                    nonlocal completed
                    completed += 1
                    if report is not None and completed % report_every == 0:
                        report(completed)

                def future_with_notify(item: ParallelRecordType) -> None:
                    if exceptions:
                        executor.shutdown(cancel_futures=True)
                        raise BrokenExecutor
                    future = executor.submit(wrapped_func, item)
                    future.add_done_callback(report_callback)

                yield future_with_notify
        finally:
            if exceptions:
                raise exceptions[0]

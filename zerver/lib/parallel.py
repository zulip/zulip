import logging
import multiprocessing
from functools import partial
from typing import Callable, List, TypeVar

from django.core.cache import caches
from django.core.cache.backends.memcached import BaseMemcachedCache
from django.db import connections as db_connections

ListJobData = TypeVar('ListJobData')
def wrapping_function(f: Callable[[ListJobData], None], item: ListJobData) -> None:
    try:
        f(item)
    except Exception:
        logging.exception("Error processing item: %s", item, stack_info=True)

def parallel_process_unordered(func: Callable[[ListJobData], None], items: List[ListJobData], processes: int) -> None:
    logging.info("Distributing %s items across %s threads", len(items), processes)
    if processes == 1:
        for item in items:
            func(item)
    else:  # nocoverage
        for db in db_connections.all():
            # We're about to close and re-open the database; validate this
            # isn't inside an atomic change.
            db.validate_no_atomic_block()
            db.close()

        for cache in caches.all():
            if isinstance(cache, BaseMemcachedCache):
                # cache.close() is called at the end of every request;
                # some memcached backends (e.g. BMemcached) override
                # it to not actually close the connection on every
                # request, which would be wasteful.
                cache._cache.close()
            else:
                cache.close()

        count = 0
        with multiprocessing.Pool(processes) as p:
            for out in p.imap_unordered(partial(wrapping_function, func), items):
                count += 1
                if count % 1000 == 0:
                    logging.info("Finished %s items", count)

        for db in db_connections.all():
            db.connect()

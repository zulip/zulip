import pickle
from functools import lru_cache
from typing import Any, Dict

from django_bmemcached.memcached import BMemcached


@lru_cache(None)
def _get_bmemcached(location: str, params: bytes) -> BMemcached:
    return BMemcached(location, pickle.loads(params))


def SingletonBMemcached(location: str, params: Dict[str, Any]) -> BMemcached:
    # Django instantiates the cache backend per-task to guard against
    # thread safety issues, but BMemcached is already thread-safe and
    # does its own per-thread pooling, so make sure we instantiate only
    # one to avoid extra connections.

    return _get_bmemcached(location, pickle.dumps(params))

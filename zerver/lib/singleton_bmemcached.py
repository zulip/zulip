import pickle
from functools import lru_cache
from typing import Any

from django_bmemcached.memcached import BMemcached

from zerver.lib import zstd_level9


@lru_cache(None)
def _get_bmemcached(location: str, param_bytes: bytes) -> BMemcached:
    params = pickle.loads(param_bytes)  # noqa: S301
    params["OPTIONS"]["compression"] = zstd_level9
    return BMemcached(location, params)


def SingletonBMemcached(location: str, params: dict[str, Any]) -> BMemcached:
    # Django instantiates the cache backend per-task to guard against
    # thread safety issues, but BMemcached is already thread-safe and
    # does its own per-thread pooling, so make sure we instantiate only
    # one to avoid extra connections.

    return _get_bmemcached(location, pickle.dumps(params))

import functools
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

ReturnT = TypeVar("ReturnT")

FUNCTION_NAME_TO_PER_REQUEST_RESULT: dict[str, dict[Any, Any]] = {}


def cache_for_current_request(f: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
    """Cache the return value for each distinct set of arguments
    during the current request.  Unlike
    @cache_for_current_request, this supports functions
    with any hashable arguments, not just a single int key."""
    cache_key = f.__name__

    assert cache_key not in FUNCTION_NAME_TO_PER_REQUEST_RESULT
    FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key] = {}

    @functools.wraps(f)
    def wrapper(*args: Hashable, **kwargs: Hashable) -> ReturnT:
        cache = FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key]
        key = (args, frozenset(kwargs.items()))
        if key in cache:
            return cache[key]
        result = f(*args, **kwargs)
        cache[key] = result
        return result

    return wrapper


def flush_per_request_cache(cache_key: str) -> None:
    if cache_key in FUNCTION_NAME_TO_PER_REQUEST_RESULT:
        FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key] = {}


def flush_per_request_caches() -> None:
    for cache_key in FUNCTION_NAME_TO_PER_REQUEST_RESULT:
        FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key] = {}

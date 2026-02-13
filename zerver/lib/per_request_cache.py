import functools
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

ReturnT = TypeVar("ReturnT")

FUNCTION_NAME_TO_PER_REQUEST_RESULT: dict[str, dict[Any, Any]] = {}


def return_same_value_during_entire_request(f: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
    cache_key = f.__name__

    assert cache_key not in FUNCTION_NAME_TO_PER_REQUEST_RESULT
    FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key] = {}

    def wrapper(key: int, *args: Any) -> ReturnT:
        if key in FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key]:
            return FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key][key]

        result = f(key, *args)
        FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key][key] = result
        return result

    return wrapper


def cache_for_current_request(f: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
    """Cache the return value for each distinct set of arguments
    during the current request.  Unlike
    @return_same_value_during_entire_request, this supports functions
    with any hashable arguments, not just a single int key."""
    cache_key = f.__name__

    assert cache_key not in FUNCTION_NAME_TO_PER_REQUEST_RESULT
    FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key] = {}

    @functools.wraps(f)
    def wrapper(*args: Hashable) -> ReturnT:
        cache = FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key]
        if args in cache:
            return cache[args]
        result = f(*args)
        cache[args] = result
        return result

    return wrapper


def flush_per_request_cache(cache_key: str) -> None:
    if cache_key in FUNCTION_NAME_TO_PER_REQUEST_RESULT:
        FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key] = {}


def flush_per_request_caches() -> None:
    for cache_key in FUNCTION_NAME_TO_PER_REQUEST_RESULT:
        FUNCTION_NAME_TO_PER_REQUEST_RESULT[cache_key] = {}

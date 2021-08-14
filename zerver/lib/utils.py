import hashlib
import re
import secrets
from typing import Any, Callable, List, Optional, TypeVar

from django.conf import settings

T = TypeVar("T")


def statsd_key(val: str, clean_periods: bool = False) -> str:
    if ":" in val:
        val = val.split(":")[0]
    val = val.replace("-", "_")
    if clean_periods:
        val = val.replace(".", "_")

    return val


class StatsDWrapper:
    """Transparently either submit metrics to statsd
    or do nothing without erroring out"""

    # Backported support for gauge deltas
    # as our statsd server supports them but supporting
    # pystatsd is not released yet
    def _our_gauge(self, stat: str, value: float, rate: float = 1, delta: bool = False) -> None:
        """Set a gauge value."""
        from django_statsd.clients import statsd

        if delta:
            value_str = f"{value:+g}|g"
        else:
            value_str = f"{value:g}|g"
        statsd._send(stat, value_str, rate)

    def __getattr__(self, name: str) -> Any:
        # Hand off to statsd if we have it enabled
        # otherwise do nothing
        if name in ["timer", "timing", "incr", "decr", "gauge"]:
            if settings.STATSD_HOST != "":
                from django_statsd.clients import statsd

                if name == "gauge":
                    return self._our_gauge
                else:
                    return getattr(statsd, name)
            else:
                return lambda *args, **kwargs: None

        raise AttributeError


statsd = StatsDWrapper()


def make_safe_digest(string: str, hash_func: Callable[[bytes], Any] = hashlib.sha1) -> str:
    """
    return a hex digest of `string`.
    """
    # hashlib.sha1, md5, etc. expect bytes, so non-ASCII strings must
    # be encoded.
    return hash_func(string.encode()).hexdigest()


def log_statsd_event(name: str) -> None:
    """
    Sends a single event to statsd with the desired name and the current timestamp

    This can be used to provide vertical lines in generated graphs,
    for example when doing a prod deploy, bankruptcy request, or
    other one-off events

    Note that to draw this event as a vertical line in graphite
    you can use the drawAsInfinite() command
    """
    event_name = f"events.{name}"
    statsd.incr(event_name)


def generate_api_key() -> str:
    api_key = ""
    while len(api_key) < 32:
        # One iteration suffices 99.4992% of the time.
        api_key += secrets.token_urlsafe(3 * 9).replace("_", "").replace("-", "")
    return api_key[:32]


def has_api_key_format(key: str) -> bool:
    return bool(re.fullmatch(r"([A-Za-z0-9]){32}", key))


def assert_is_not_none(value: Optional[T]) -> T:
    assert value is not None
    return value


def process_list_in_batches(
    lst: List[Any], chunk_size: int, process_batch: Callable[[List[Any]], None]
) -> None:
    offset = 0

    while True:
        items = lst[offset : offset + chunk_size]
        if not items:
            break
        process_batch(items)
        offset += chunk_size

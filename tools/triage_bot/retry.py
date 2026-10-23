"""Retries for transient failures of the HTTP APIs the bot calls."""

import http.client
import random
import sys
import time
import urllib.error
import urllib.request

# 529 is the Anthropic API's "overloaded" status.
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}


class RequestFailedError(Exception):
    pass


def backoff_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Exponential backoff with jitter, so retries from parallel runs spread out."""
    delay = min(max_delay, base_delay * 2**attempt)
    return delay / 2 + random.uniform(0, delay / 2)


def retry_after_seconds(value: str | None) -> float | None:
    """The Retry-After header, in seconds."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def urlopen_with_retries(
    request: urllib.request.Request,
    *,
    what: str,
    attempts: int,
    base_delay: float,
    max_delay: float,
    timeout: float,
    retry_statuses: set[int] = RETRY_STATUSES,
    retry_network_errors: bool = True,
) -> bytes:
    """The response body; raises RequestFailedError once retrying won't help.

    A request that isn't safe to repeat can pass retry_statuses={429}
    and retry_network_errors=False: a 429 means it wasn't processed.
    """
    for attempt in range(attempts):
        retry_after = None
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            reason = f"HTTP {e.code}: {e.read()[:500]!r}"
            if e.code not in retry_statuses:
                raise RequestFailedError(f"{what} failed with {reason}") from e
            retry_after = retry_after_seconds(e.headers.get("Retry-After") if e.headers else None)
        # http.client.HTTPException covers a connection that drops while
        # the response is being read.
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.HTTPException,
        ) as e:
            reason = f"{type(e).__name__}: {e}"
            if not retry_network_errors:
                raise RequestFailedError(f"{what} failed with {reason}") from e
        if attempt == attempts - 1:
            raise RequestFailedError(
                f"{what} failed after {attempts} attempts; last error: {reason}"
            )
        delay = (
            retry_after
            if retry_after is not None
            else backoff_delay(attempt, base_delay, max_delay)
        )
        print(
            f"{what}: {reason}; retrying in {delay:.0f}s (attempt {attempt + 2} of {attempts})",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(delay)
    raise AssertionError("unreachable")

import asyncio
from asyncio import SelectorEventLoop
from asyncio.base_events import _format_handle  # type: ignore # No library stub file for standard library module 'asyncio.base_events'
from asyncio.events import Handle
import logging
import select
from selectors import DefaultSelector
import time
from typing import Any, List, Tuple

from django.conf import settings
from tornado.platform.asyncio import AnyThreadEventLoopPolicy, AsyncIOLoop

if settings.DEBUG:
    # Patch the _run call that executes a coroutine. Our patch times how long
    # every coroutine takes to run and logs a warning if it is greater than
    # the specified amount of time. This is similar to tornado's
    # set_blocking_log_threshold except less sophisticated because no signals
    # are used. Asyncio has a similar functionality if you turn on debugging,
    # but that turns on many other debug options which are not desired.
    unpatched_run = Handle._run

    def _patched_run(self: Handle) -> None:
        start = time.time()

        unpatched_run(self)

        diff = time.time() - start
        if diff > 5:
            logging.warning('Executing %s took %.3f seconds', _format_handle(self), diff)

    Handle._run = _patched_run  # type: ignore # https://github.com/python/mypy/issues/2427


class _ProxyEPoll:
    """It's not possible to subclass the select.epoll object as it's written
    in C, so this just acts as a proxy to that object except when poll() is
    called."""
    def __init__(self) -> None:
        self._underlying = select.epoll()
        self._times = []  # type: List[Tuple[float, float]]
        self._last_print = 0.0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._underlying, name)

    def poll(self, timeout: float, maxevents: Any) -> Any:
        # Avoid accumulating a bunch of insignificant data points
        # from short timeouts.
        if timeout < 1e-3:
            return self._underlying.poll(timeout, maxevents)

        # Record start and end times for the underlying poll
        t0 = time.time()
        result = self._underlying.poll(timeout, maxevents)
        t1 = time.time()

        # Log this datapoint and restrict our log to the past minute
        self._times.append((t0, t1))
        while self._times and self._times[0][0] < t1 - 60:
            self._times.pop(0)

        # Report (at most once every 5s) the percentage of time spent
        # outside poll
        if self._times and t1 - self._last_print >= 5:
            total = t1 - self._times[0][0]
            in_poll = sum(b-a for a, b in self._times)
            if total > 0:
                percent_busy = 100 * (1 - in_poll / total)
                if settings.PRODUCTION or True:
                    logging.info('Tornado %5.1f%% busy over the past %4.1f seconds'
                                 % (percent_busy, total))
                    self._last_print = t1
        return result


class _InstrumentedSelector(DefaultSelector):
    """A standard asyncio selector that uses our epoll proxy"""
    def __init__(self) -> None:
        super().__init__()
        self._epoll = _ProxyEPoll()


class _InstrumentedEventLoop(SelectorEventLoop):  # type: ignore # https://github.com/python/mypy/issues/2477
    """A standard asyncio event loop that uses our selector"""
    def __init__(self) -> None:
        super().__init__(_InstrumentedSelector())


class Policy(AnyThreadEventLoopPolicy):
    """A custom loop policy that will ensure that the _InstrumentedEventLoop
    is returned when asyncio.get_event_loop() is called
    """
    def _loop_factory(self) -> _InstrumentedEventLoop:
        return _InstrumentedEventLoop()


# We must call set_event_loop_policy before we import anything else from our
# project in order for our Tornado load logging to work; otherwise we might
# accidentally import zerver.lib.queue (which will instantiate the Tornado
# ioloop) before this.

# Even if we don'nt use the load logging, at a minimum the
# AnyThreadEventLoopPolicy needs to be set because the normal asyncio policy
# won't return you a loop if you aren't in the main thread.

asyncio.set_event_loop_policy(Policy())

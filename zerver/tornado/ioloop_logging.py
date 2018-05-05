import logging
import time
from typing import Any, List, Tuple

from django.conf import settings
from tornado.ioloop import IOLoop, PollIOLoop
from tornado.platform.asyncio import AsyncIOLoop

# A hack to keep track of how much time we spend working, versus sleeping in
# the event loop.
#
# Creating a new event loop instance with a custom impl object fails (events
# don't get processed), so instead we modify the ioloop module variable holding
# the default poll implementation.  We need to do this before any Tornado code
# runs that might instantiate the default event loop.

class InstrumentedAsyncIOLoop(AsyncIOLoop):
    def __init__(self) -> None:
        self._times = []  # type: List[Tuple[float, float]]
        self._last_print = 0.0

    def _handle_events(self, fd, events):
        t0 = time.time()
        fileobj, handler_func = self.handlers[fd]
        handler_func(fileobj, events)
        t1 = time.time()

        # Log this datapoint and restrict our log to the past minute
        self._times.append((t0, t1))
        while self._times and self._times[0][0] < t1 - 60:
            self._times.pop(0)

        # Report (at most once every 5s) the percentage of time spent
        # outside poll
        if self._times and t1 - self._last_print >= 5:
            total = t1 - self._times[0][0]
            doing_work = sum(b-a for a, b in self._times)
            if total > 0:
                percent_busy = 100 * (doing_work / total)
                if settings.PRODUCTION or True:
                    logging.info('Tornado %5.1f%% busy over the past %4.1f seconds'
                                 % (percent_busy, total))
                    self._last_print = t1

def instrument_tornado_ioloop() -> None:
    InstrumentedAsyncIOLoop.configure(InstrumentedAsyncIOLoop)


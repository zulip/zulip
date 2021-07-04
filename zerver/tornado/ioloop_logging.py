import asyncio
import time
from selectors import EpollSelector
from typing import Dict

# This is used for a somewhat hacky way of passing the port number
# into this early-initialized module.
logging_data: Dict[str, str] = {}


class CustomEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self) -> asyncio.SelectorEventLoop:
        return self._loop_factory(selector=CustomPollSelector())


class CustomPollSelector(EpollSelector):
    def __init__(self) -> None:
        super().__init__()
        self._times = []
        self._last_print = 0.0

    def select(self, timeout=None):
        t0 = time.time()
        event_list = super().select(timeout)
        t1 = time.time()

        self._times.append((t0, t1))
        while self._times and self._times[0][0] < t1 - 60:
            self._times.pop(0)

        if self._times and t1 - self._last_print >= 5:
            total = t1 - self._times[0][0]
            in_poll = sum(b - a for a, b in self._times)
            if total > 0:
                percent_busy = 100 * (1 - in_poll / total)
                print(
                    f"Tornado 9993 {percent_busy:.2f}% busy over the past {total:.2f} seconds",
                )
                self._last_print = t1

        return event_list

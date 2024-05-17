import ctypes
import logging
import sys
import threading
import time
from types import TracebackType
from typing import Callable, Optional, Tuple, Type, TypeVar

from typing_extensions import override

# Based on https://code.activestate.com/recipes/483752/


class TimeoutExpiredError(Exception):
    """Exception raised when a function times out."""

    @override
    def __str__(self) -> str:
        return "Function call timed out."


ResultT = TypeVar("ResultT")


def unsafe_timeout(timeout: float, func: Callable[[], ResultT]) -> ResultT:
    """Call the function in a separate thread.
    Return its return value, or raise an exception,
    within approximately 'timeout' seconds.

    The function may receive a TimeoutExpiredError exception
    anywhere in its code, which could have arbitrary
    unsafe effects (resources not released, etc.).
    It might also fail to receive the exception and
    keep running in the background even though
    timeout() has returned.

    This may also fail to interrupt functions which are
    stuck in a long-running primitive interpreter
    operation."""

    class TimeoutThread(threading.Thread):
        def __init__(self) -> None:
            threading.Thread.__init__(self)
            self.result: Optional[ResultT] = None
            self.exc_info: Tuple[
                Optional[Type[BaseException]],
                Optional[BaseException],
                Optional[TracebackType],
            ] = (None, None, None)

            # Don't block the whole program from exiting
            # if this is the only thread left.
            self.daemon = True

        @override
        def run(self) -> None:
            try:
                self.result = func()
            except BaseException:
                self.exc_info = sys.exc_info()

        def raise_async_timeout(self) -> None:
            # This function is called from another thread; we attempt
            # to raise a TimeoutExpiredError in _this_ thread.
            assert self.ident is not None
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(self.ident),
                ctypes.py_object(TimeoutExpiredError),
            )

    thread = TimeoutThread()
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # We need to retry, because an async exception received while
        # the thread is in a system call is simply ignored.
        for i in range(10):
            thread.raise_async_timeout()
            time.sleep(0.1)
            if not thread.is_alive():
                break
        if thread.exc_info[1] is not None:
            # Re-raise the exception we sent, if possible, so the
            # stacktrace originates in the slow code
            raise thread.exc_info[1].with_traceback(thread.exc_info[2])
        # If we don't have that for some reason (e.g. we failed to
        # kill it), just raise from here; the thread _may still be
        # running_ because it failed to see any of our exceptions, and
        # we just ignore it.
        if thread.is_alive():  # nocoverage
            logging.warning("Failed to time out backend thread")
        raise TimeoutExpiredError  # nocoverage

    if thread.exc_info[1] is not None:
        # Died with some other exception; re-raise it
        raise thread.exc_info[1].with_traceback(thread.exc_info[2])

    assert thread.result is not None
    return thread.result

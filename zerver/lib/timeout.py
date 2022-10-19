import ctypes
import logging
from threading import Semaphore, Thread
from typing import Callable, Optional, TypeVar, Union


class TimeoutExpired(Exception):
    """Exception raised when a function times out."""

    def __str__(self) -> str:
        return "Function call timed out."


class NoResult:
    pass


ResultT = TypeVar("ResultT")


def timeout(timeout: float, func: Callable[[], ResultT]) -> ResultT:
    """Call the function in a separate thread.
    Return its return value, or raise an exception,
    within approximately 'timeout' seconds.

    The function may receive a TimeoutExpired exception
    anywhere in its code, which could have arbitrary
    unsafe effects (resources not released, etc.).
    It might also fail to receive the exception and
    keep running in the background even though
    timeout() has returned.

    This may also fail to interrupt functions which are
    stuck in a long-running primitive interpreter
    operation."""

    result: Union[ResultT, NoResult] = NoResult()
    exception: Optional[BaseException] = None

    # This semaphore prevents calling PyThreadState_SetAsyncExc after
    # the function is done and the thread is stopping.
    semaphore = Semaphore()

    def run() -> None:
        nonlocal result, exception
        try:
            result = func()
        except BaseException as e:
            exception = e
        semaphore.acquire()

    thread = Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout)

    # We need a retry loop, because an async exception received while
    # the thread is in a system call is simply ignored.
    for i in range(10):
        if not thread.is_alive() or not semaphore.acquire(blocking=False):
            break
        assert thread.ident is not None
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread.ident),
            ctypes.py_object(TimeoutExpired),
        )
        # Give the thread another chance to exit, so we can get a
        # stack trace for the TimeoutExpired exception originating
        # with the slow code.
        semaphore.release()
        thread.join(0.1)
    else:
        if thread.is_alive() and semaphore.acquire(blocking=False):
            # If we we failed to kill the thread for some reason, just
            # raise from here; the thread _may still be running_
            # because it failed to see any of our exceptions, and we
            # just ignore it.
            semaphore.release()
            logging.warning("Failed to time out backend thread")
            raise TimeoutExpired

    if exception is not None:
        raise exception

    assert not isinstance(result, NoResult)
    return result

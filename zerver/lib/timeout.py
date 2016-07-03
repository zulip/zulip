from __future__ import absolute_import
from types import TracebackType
from typing import Any, Callable, Optional, Tuple, TypeVar

import sys
import time
import ctypes
import threading
import six
from six.moves import range

# Based on http://code.activestate.com/recipes/483752/

class TimeoutExpired(Exception):
    '''Exception raised when a function times out.'''
    def __str__(self):
        # type: () -> str
        return 'Function call timed out.'

ResultT = TypeVar('ResultT')

def timeout(timeout, func, *args, **kwargs):
    # type: (float, Callable[..., ResultT], *Any, **Any) -> ResultT
    '''Call the function in a separate thread.
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
       operation.'''

    class TimeoutThread(threading.Thread):
        def __init__(self):
            # type: () -> None
            threading.Thread.__init__(self)
            self.result = None # type: Optional[ResultT]
            self.exc_info = None # type: Optional[Tuple[type, BaseException, TracebackType]]

            # Don't block the whole program from exiting
            # if this is the only thread left.
            self.daemon = True

        def run(self):
            # type: () -> None
            try:
                self.result = func(*args, **kwargs)
            except BaseException:
                self.exc_info = sys.exc_info()

        def raise_async_timeout(self):
            # type: () -> None
            # Called from another thread.
            # Attempt to raise a TimeoutExpired in the thread represented by 'self'.
            tid = ctypes.c_long(self.ident)
            result = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                tid, ctypes.py_object(TimeoutExpired))
            if result > 1:
                # "if it returns a number greater than one, you're in trouble,
                # and you should call it again with exc=NULL to revert the effect"
                #
                # I was unable to find the actual source of this quote, but it
                # appears in the many projects across the Internet that have
                # copy-pasted this recipe.
                ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)

    thread = TimeoutThread()
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # Gamely try to kill the thread, following the dodgy approach from
        # http://stackoverflow.com/a/325528/90777
        #
        # We need to retry, because an async exception received while the
        # thread is in a system call is simply ignored.
        for i in range(10):
            thread.raise_async_timeout()
            time.sleep(0.1)
            if not thread.is_alive():
                break
        raise TimeoutExpired

    if thread.exc_info:
        # Raise the original stack trace so our error messages are more useful.
        # from http://stackoverflow.com/a/4785766/90777
        six.reraise(thread.exc_info[0], thread.exc_info[1], thread.exc_info[2])
    return thread.result

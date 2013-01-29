import threading

# Based on http://code.activestate.com/recipes/483752/

class TimeoutExpired(Exception):
    '''Exception raised when a function times out.'''
    def __str__(self):
        return 'Function call timed out.'

def timeout(timeout, func, *args, **kwargs):
    '''Call the function in a separate thread.
       Return its return value, or raise an exception,
       within 'timeout' seconds.

       The function may still be running in the background!

       This may also fail to interrupt functions which are
       stuck in a long-running primitive interpreter
       operation.'''

    class TimeoutThread(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
            self.result = None
            self.exn    = None

            # Don't block the whole program from exiting
            # if this is the only thread left.
            self.daemon = True

        def run(self):
            try:
                self.result = func(*args, **kwargs)
            except BaseException, e:
                self.exn = e

    thread = TimeoutThread()
    thread.start()
    thread.join(timeout)

    if thread.isAlive():
        raise TimeoutExpired
    if thread.exn:
        raise thread.exn
    return thread.result

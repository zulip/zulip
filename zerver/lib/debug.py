from __future__ import absolute_import

import code
import traceback
import signal

from types import FrameType

from typing import Optional

# Interactive debugging code from
# http://stackoverflow.com/questions/132058/showing-the-stack-trace-from-a-running-python-application
# (that link also points to code for an interactive remote debugger
# setup, which we might want if we move Tornado to run in a daemon
# rather than via screen).
def interactive_debug(sig, frame):
    # type: (int, Optional[FrameType]) -> None
    """Interrupt running process, and provide a python prompt for
    interactive debugging."""
    d = {'_frame': frame}      # Allow access to frame object.
    d.update(frame.f_globals)  # Unless shadowed by global
    d.update(frame.f_locals)

    message  = "Signal recieved : entering python shell.\nTraceback:\n"
    message += ''.join(traceback.format_stack(frame))
    i = code.InteractiveConsole(d)
    i.interact(message)

# SIGUSR1 => Just print the stack
# SIGUSR2 => Print stack + open interactive debugging shell
def interactive_debug_listen():
    # type: () -> None
    signal.signal(signal.SIGUSR1, lambda sig, stack: traceback.print_stack(stack)) # type: ignore # https://github.com/python/typeshed/issues/294
    signal.signal(signal.SIGUSR2, interactive_debug)

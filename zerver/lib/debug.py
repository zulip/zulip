import code
import gc
import logging
import os
import signal
import socket
import threading
import traceback
import tracemalloc
from types import FrameType
from typing import Optional

from django.conf import settings
from django.utils.timezone import now as timezone_now

logger = logging.getLogger("zulip.debug")


# Interactive debugging code from
# https://stackoverflow.com/questions/132058/showing-the-stack-trace-from-a-running-python-application
# (that link also points to code for an interactive remote debugger
# setup, which we might want if we move Tornado to run in a daemon
# rather than via screen).
def interactive_debug(sig: int, frame: Optional[FrameType]) -> None:
    """Interrupt running process, and provide a python prompt for
    interactive debugging."""
    d = {"_frame": frame}  # Allow access to frame object.
    if frame is not None:
        d.update(frame.f_globals)  # Unless shadowed by global
        d.update(frame.f_locals)

    message = "Signal received : entering python shell.\nTraceback:\n"
    message += "".join(traceback.format_stack(frame))
    i = code.InteractiveConsole(d)
    i.interact(message)


# SIGUSR1 => Just print the stack
# SIGUSR2 => Print stack + open interactive debugging shell
def interactive_debug_listen() -> None:
    signal.signal(signal.SIGUSR1, lambda sig, stack: traceback.print_stack(stack))
    signal.signal(signal.SIGUSR2, interactive_debug)


def tracemalloc_dump() -> None:
    if not tracemalloc.is_tracing():
        logger.warning("pid %s: tracemalloc off, nothing to dump", os.getpid())
        return
    # Despite our name for it, `timezone_now` always deals in UTC.
    basename = "snap.{}.{}".format(os.getpid(), timezone_now().strftime("%F-%T"))
    path = os.path.join(settings.TRACEMALLOC_DUMP_DIR, basename)
    os.makedirs(settings.TRACEMALLOC_DUMP_DIR, exist_ok=True)

    gc.collect()
    tracemalloc.take_snapshot().dump(path)

    with open(f"/proc/{os.getpid()}/stat", "rb") as f:
        procstat = f.read().split()
    rss_pages = int(procstat[23])
    logger.info(
        "tracemalloc dump: tracing %s MiB (%s MiB peak), using %s MiB; rss %s MiB; dumped %s",
        tracemalloc.get_traced_memory()[0] // 1048576,
        tracemalloc.get_traced_memory()[1] // 1048576,
        tracemalloc.get_tracemalloc_memory() // 1048576,
        rss_pages // 256,
        basename,
    )


def tracemalloc_listen_sock(sock: socket.socket) -> None:
    logger.debug("pid %s: tracemalloc_listen_sock started!", os.getpid())
    while True:
        sock.recv(1)
        tracemalloc_dump()


listener_pid: Optional[int] = None


def tracemalloc_listen() -> None:
    global listener_pid
    if listener_pid == os.getpid():
        # Already set up -- and in this process, not just its parent.
        return
    logger.debug("pid %s: tracemalloc_listen working...", os.getpid())
    listener_pid = os.getpid()

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    path = f"/tmp/tracemalloc.{os.getpid()}"
    sock.bind(path)
    thread = threading.Thread(target=lambda: tracemalloc_listen_sock(sock), daemon=True)
    thread.start()
    logger.debug("pid %s: tracemalloc_listen done: %s", os.getpid(), path)


def maybe_tracemalloc_listen() -> None:
    """If tracemalloc tracing enabled, listen for requests to dump a snapshot.

    To trigger once this is listening:
      echo | socat -u stdin unix-sendto:/tmp/tracemalloc.$pid

    To enable in the Zulip web server: edit /etc/zulip/uwsgi.ini ,
    and add e.g. ` PYTHONTRACEMALLOC=5` to the `env=` line.
    This function is called in middleware, so the process will
    automatically start listening.

    To enable in other contexts: see upstream docs
    https://docs.python.org/3/library/tracemalloc .
    You may also have to add a call to this function somewhere.

    """
    if os.environ.get("PYTHONTRACEMALLOC"):
        # If the server was started with `tracemalloc` tracing on, then
        # listen for a signal to dump `tracemalloc` snapshots.
        tracemalloc_listen()

"""
Context managers, i.e. things you can use with the 'with' statement.
"""

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, Any


@contextmanager
def flock(lockfile: int | IO[Any], shared: bool = False) -> Iterator[None]:
    """Lock a file object using flock(2) for the duration of a 'with' statement.

    If shared is True, use a LOCK_SH lock, otherwise LOCK_EX."""

    fcntl.flock(lockfile, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(lockfile, fcntl.LOCK_UN)


@contextmanager
def lockfile(filename: str, shared: bool = False) -> Iterator[None]:
    """Lock a file using flock(2) for the duration of a 'with' statement.

    If shared is True, use a LOCK_SH lock, otherwise LOCK_EX.

    The file is given by name and will be created if it does not exist."""
    with open(filename, "w") as lock, flock(lock, shared=shared):
        yield


@contextmanager
def lockfile_nonblocking(filename: str) -> Iterator[bool]:  # nocoverage
    """Lock a file using flock(2) for the duration of a 'with' statement.

    Doesn't block, yields False immediately if the lock can't be acquired."""
    with open(filename, "w") as f:
        lock_acquired = False
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_acquired = True
            yield lock_acquired
        except BlockingIOError:
            yield False
        finally:
            if lock_acquired:
                fcntl.flock(f, fcntl.LOCK_UN)

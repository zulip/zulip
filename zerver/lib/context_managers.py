"""
Context managers, i.e. things you can use with the 'with' statement.
"""


import fcntl
from contextlib import contextmanager
from typing import Iterator, IO, Any, Union

@contextmanager
def flock(lockfile: Union[int, IO[Any]], shared: bool=False) -> Iterator[None]:
    """Lock a file object using flock(2) for the duration of a 'with' statement.

       If shared is True, use a LOCK_SH lock, otherwise LOCK_EX."""

    fcntl.flock(lockfile, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(lockfile, fcntl.LOCK_UN)

@contextmanager
def lockfile(filename: str, shared: bool=False) -> Iterator[None]:
    """Lock a file using flock(2) for the duration of a 'with' statement.

       If shared is True, use a LOCK_SH lock, otherwise LOCK_EX.

       The file is given by name and will be created if it does not exist."""
    with open(filename, 'w') as lock:
        with flock(lock, shared=shared):
            yield

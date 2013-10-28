"""
Context managers, i.e. things you can use with the 'with' statement.
"""

from __future__ import absolute_import

import fcntl
import os
from contextlib import contextmanager

@contextmanager
def flock(lockfile, shared=False):
    """Lock a file object using flock(2) for the duration of a 'with' statement.

       If shared is True, use a LOCK_SH lock, otherwise LOCK_EX."""

    fcntl.flock(lockfile, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(lockfile, fcntl.LOCK_UN)

@contextmanager
def lockfile(filename, shared=False):
    """Lock a file using flock(2) for the duration of a 'with' statement.

       If shared is True, use a LOCK_SH lock, otherwise LOCK_EX.

       The file is given by name and will be created if it does not exist."""

    if not os.path.exists(filename):
        with open(filename, 'w') as lock:
            lock.write('0')

    # TODO: Can we just open the file for writing, and skip the above check?
    with open(filename, 'r') as lock:
        with flock(lock, shared=shared):
            yield

"""Marker for code paths running inside a REPEATABLE READ transaction.

A REPEATABLE READ snapshot is taken at the transaction's first DB
read and held until commit.  A read-through cache fill from inside
that snapshot can return data that predates a concurrent writer's
commit; writing it back into memcached *undoes* the writer's
invalidation and leaves a stale entry that survives until the next
write or TTL.  Mark-then-fill doesn't catch this on its own -- the
writer's commit may have landed before our transaction even
started, so the reader's snapshot is older than memcached itself.

The threadlocal marker set by `repeatable_read_atomic` (the only
sanctioned way to enter REPEATABLE READ; a lint rule pins this)
lets the cache layer recognize the at-risk context and require a
snapshot-safe shape on the fill.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection, transaction


class SnapshotIsolationError(AssertionError):
    """Raised by the cache layer when reached from inside
    repeatable_read_atomic without a snapshot-safe shape declared on
    the cache."""


_local = threading.local()


def in_repeatable_read_transaction() -> bool:
    return getattr(_local, "active", False)


@contextmanager
def repeatable_read_atomic() -> Iterator[None]:
    """Open a read-only REPEATABLE READ transaction with the cache-layer
    marker set.

    durable=True only succeeds at the real outermost atomic, but inside
    Django TestCase our atomic is degraded to a savepoint nested in the
    test wrapper -- and SET TRANSACTION fails on a savepoint, so we
    skip it when savepoint_ids is non-empty.  The marker still fires,
    so TestCase tests exercise the same fill-path enforcement
    production does; zerver/transaction_tests covers the SET
    TRANSACTION branch.
    """
    with transaction.atomic(durable=True):
        if not connection.savepoint_ids:
            connection.cursor().execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        was_active = getattr(_local, "active", False)
        _local.active = True
        try:
            yield
        finally:
            _local.active = was_active

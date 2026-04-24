"""Routing helpers for the optional "replica" DB alias.

Shifts eligible historical-scroll queries from ``GET /messages`` onto
the replica; everything else keeps using ``default``. A threadlocal
plus a Django ``DATABASE_ROUTERS`` entry gives us per-request opt-in
without annotating every queryset with ``using=``.
"""

import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

from django.conf import settings
from django.db import DatabaseError, connections

REPLICA_DB_ALIAS = "replica"
DEFAULT_DB_ALIAS = "default"

logger = logging.getLogger(__name__)


_state = threading.local()


def active_replica_alias() -> str | None:
    """The alias ``use_replica()`` has activated on this thread, or None."""
    return getattr(_state, "alias", None)


@contextmanager
def use_replica() -> Iterator[None]:
    """Route ORM reads and writes made inside this block to the replica alias.

    This context manager is intended for wrapping read-only flows.
    Writes are deliberately sent to the replica connection, which is
    configured with ``default_transaction_read_only=on`` (see
    ``zproject/computed_settings.py``), so any stray write inside the
    block fails loudly with ``cannot execute <stmt> in a read-only
    transaction`` instead of silently committing against the primary.

    The previous alias (if any) is restored on exit so nested uses
    are safe.
    """
    previous = getattr(_state, "alias", None)
    _state.alias = REPLICA_DB_ALIAS
    try:
        yield
    finally:
        if previous is None:
            del _state.alias
        else:
            _state.alias = previous


class ReadReplicaRouter:
    """Send reads AND writes to the alias set by ``use_replica()`` (if any).

    Outside a ``use_replica()`` block, both ``db_for_read`` and
    ``db_for_write`` return ``None`` (meaning "no opinion"), so Django
    falls through to ``default``.

    Inside a ``use_replica()`` block, writes are sent to the replica
    alias — whose connection has ``default_transaction_read_only=on``
    — so Postgres rejects them. This turns accidental writes inside a
    supposedly-read-only flow into loud errors rather than silent
    cross-alias writes.

    Migrations only run on ``default``; the replica is expected to
    catch up via streaming replication.
    """

    def db_for_read(self, model: object, **hints: object) -> str | None:
        return active_replica_alias()

    def db_for_write(self, model: object, **hints: object) -> str | None:
        return active_replica_alias()

    def allow_relation(self, obj1: object, obj2: object, **hints: object) -> bool:
        return True

    def allow_migrate(
        self, db: str, app_label: str, model_name: str | None = None, **hints: object
    ) -> bool:
        return db == DEFAULT_DB_ALIAS


_watermark_cache: dict[str, tuple[float, int]] = {}
_watermark_lock = threading.Lock()


def _reset_watermark_cache_for_tests() -> None:
    """Clear the watermark cache. Only for use by tests."""
    _watermark_cache.clear()


def get_replica_message_id_watermark() -> int | None:
    """Return the max message id the replica has actually replayed, or None.

    ``SELECT MAX(id) FROM zerver_message`` is a single index-only lookup
    on the PK, and critically reflects rows that have been committed
    and replayed — unlike ``zerver_message_id_seq.last_value``, which
    tracks sequence state that WAL-streams ahead of the corresponding
    INSERT commits in batches and can therefore claim a higher id than
    any visible row.

    Cached per-process for ``REPLICA_WATERMARK_CACHE_SECONDS``. Returns
    ``None`` if the replica isn't reachable or the table is empty;
    callers should treat that as "not eligible" and fall through to
    the primary.
    """
    ttl = settings.REPLICA_WATERMARK_CACHE_SECONDS
    now = time.monotonic()
    cached = _watermark_cache.get(REPLICA_DB_ALIAS)
    if cached is not None and now - cached[0] < ttl:
        return cached[1]

    with _watermark_lock:
        # Re-check after acquiring the lock to avoid a stampede.
        cached = _watermark_cache.get(REPLICA_DB_ALIAS)
        if cached is not None and time.monotonic() - cached[0] < ttl:
            return cached[1]
        try:
            with connections[REPLICA_DB_ALIAS].cursor() as cursor:
                cursor.execute("SELECT MAX(id) FROM zerver_message")
                row = cursor.fetchone()
        except DatabaseError:
            # The TTL keeps this from spamming; at most one warning
            # per REPLICA_WATERMARK_CACHE_SECONDS window per process.
            logger.warning("Could not read watermark from replica", exc_info=True)
            return None
        if row is None or row[0] is None:
            return None
        value = int(row[0])
        _watermark_cache[REPLICA_DB_ALIAS] = (time.monotonic(), value)
        return value

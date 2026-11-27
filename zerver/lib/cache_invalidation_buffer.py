"""Per-transaction buffer of pending cache mutations.

Cache mutations made inside an `atomic()` block are recorded here, and
applied to memcached only when the outermost transaction commits.  They
thus take effect, or not, together with the database writes that
prompted them:

  * The transaction sees its own mutations at once.  Later reads
    return a buffered set, and miss on a buffered delete.
  * Other connections see the mutations only once the outermost
    `atomic()` has committed.
  * A rollback discards the mutations of the block that rolled back,
    and leaves memcached untouched.  In particular, nothing read from
    uncommitted database state ends up cached.

Writes and invalidations (cache_set, cache_set_many, cache_delete and
cache_delete_many) are recorded without a cas id, and the flush
applies them unconditionally.

Read-through fills (cache_add followed by cache_cas) have to cooperate
with other processes doing mark-then-fill on the same key:

  * cache_add writes its sentinel to memcached at once, so that other
    readers see the claim, and records the cas id that memcached
    returns for it.
  * cache_add refuses a key that the transaction has already written
    or invalidated.  A buffered delete therefore wins at commit, and
    no fill computed before the commit outlives it.
  * cache_cas only updates the buffer.
  * The flush stores the value conditionally on that cas id.  If
    another process invalidated the key during the transaction, the
    store fails and the invalidation stands.
  * If the transaction rolls back, the sentinel stays in memcached
    until it expires, and other readers bypass the cache for that key
    in the meantime.  No value from the rolled-back transaction is
    ever stored.

A buffered read-through fill is only provisional, since another
process may still change and invalidate it before we commit.  Because
of this, we return read-through fills from the in-process buffer only
while memcached still holds the sentinel that we wrote to claim the
slot.  If another process invalidates the key, the fill is dropped and
the next read fetches from the database afresh.

The buffer is per-thread.  It is a stack with one frame per open
atomic block, and each frame maps a key to its pending op:

  * ('delete', None, None, 0)            -- delete
  * ('set', value, timeout, 0)           -- write-through set
  * ('set', value, timeout, mc_cas_id)   -- fill, stored at commit
                                            only if the key's cas id
                                            is still mc_cas_id

Within a frame, a later op on a key replaces an earlier one, so the
last intended state wins.  When a savepoint commits, its frame is
merged into its parent, again with later ops winning.  When it rolls
back, its frame is discarded.

The flush is registered as `transaction.on_commit(drain_buffer)` when
the outermost atomic block is entered.  Django runs on_commit hooks
only after a real commit.  It clears them on every rollback, including
those that raise nothing out of the block:

  * `connection.needs_rollback`, set by an inner `savepoint=False`
    block whose exception was caught;
  * a DatabaseError from the COMMIT itself;
  * `connection.closed_in_transaction`.

Registering on entry also puts the flush ahead of any on_commit
callback that the block itself registers.  Code that invalidates with
`transaction.on_commit(lambda: cache_delete(...))` thus still runs
after the flush, and its delete still wins.

Django's TestCase wraps each test in an atomic block, and rolls that
block back at tearDown, so on_commit hooks registered against it never
run.  Two things compensate:

  * Atomic blocks with `_from_testcase` set are ignored, so that the
    outermost block opened by the code under test is the buffer's
    outermost.
  * When the buffer's outermost frame commits and on_commit has not
    run the flush, the patched __exit__ runs it directly.  In
    production on_commit has always run it by then, and this does
    nothing.
"""

import logging
import pickle
import threading
from typing import Any

from django.db import connection, transaction

logger = logging.getLogger()

# Op tuple: (kind, value, timeout, mc_cas_id).  Kind is 'set' or 'delete'.
# For 'delete' value and timeout are None.  For 'set' value is the
# pickle of the original Python value -- we store bytes so the buffer's
# snapshot is independent of caller references (matching memcached's
# pickle-round-trip semantics) without paying for a deepcopy on every
# record_set / lookup.  See record_set / lookup.  mc_cas_id is the
# memcached cas_id captured by cache_add for read-through fill entries;
# 0 for any other entry (deletes, write-through cache_set).  The flush
# uses mc_cas_id != 0 to decide between cas-conditional and unconditional
# memcached writes -- see _flush_buffered_ops.
PendingOp = tuple[str, Any, int | None, int]


class CacheInvalidationBuffer:
    """Thread-local stack of buffered cache mutations.

    One frame per open atomic() block; the stack mirrors Django's
    savepoint nesting.  See module docstring.
    """

    def __init__(self) -> None:
        self._stack: list[dict[str, PendingOp]] = []
        # Set by exit_atomic at outermost commit; consumed by
        # drain_buffer (the on_commit callback) or, in tests where
        # on_commit doesn't fire, by the patched __exit__'s safety net.
        self._pending_flush_ops: dict[str, PendingOp] | None = None

    def in_transaction(self) -> bool:
        return bool(self._stack)

    def enter_atomic(self) -> None:
        self._stack.append({})

    def exit_atomic(self, *, committed: bool) -> None:
        """Pop the innermost frame.

        On rollback the frame is discarded.  On savepoint commit it is
        merged into the parent.  On outermost commit the merged frame
        is stashed in `_pending_flush_ops` for the on_commit callback
        (or the patched __exit__'s safety net, in tests) to apply.
        """
        frame = self._stack.pop()
        if not committed:
            return
        if self._stack:
            self._stack[-1].update(frame)
            return
        self._pending_flush_ops = frame

    def take_pending_flush_ops(self) -> dict[str, PendingOp] | None:
        ops = self._pending_flush_ops
        self._pending_flush_ops = None
        return ops

    def record_delete(self, key: str) -> None:
        assert self._stack, "record_delete called outside an atomic block"
        self._stack[-1][key] = ("delete", None, None, 0)

    def record_set(self, key: str, value: Any, timeout: int | None, mc_cas_id: int = 0) -> None:
        """Record a buffered set.

        mc_cas_id is the memcached cas_id captured by cache_add when this
        entry originates from a read-through fill (cache_add + cache_cas);
        0 for write-through cache_set entries and for follow-up cache_set
        calls that overwrite a prior fill entry.  The flush uses it to
        decide between cas-conditional and unconditional memcached writes.

        The value is pickled and stored as bytes so the buffer holds an
        independent snapshot at write time, and lookup unpickles on
        read -- matching memcached's pickle-round-trip semantics.
        """
        assert self._stack, "record_set called outside an atomic block"
        self._stack[-1][key] = ("set", pickle.dumps(value), timeout, mc_cas_id)

    def discard(self, key: str) -> None:
        """Forget the most recent op on `key`, as if it had never been
        recorded."""
        for frame in reversed(self._stack):
            if key in frame:
                del frame[key]
                return

    def lookup(self, key: str) -> PendingOp | None:
        """Most recent op on `key` across all open frames, or None.  For
        'set' ops the stored bytes are unpickled to a fresh value (see
        record_set)."""
        for frame in reversed(self._stack):
            if key in frame:
                kind, val, timeout, mc_cas_id = frame[key]
                if kind == "set":
                    val = pickle.loads(val)  # noqa: S301
                return (kind, val, timeout, mc_cas_id)
        return None


_buffer_local = threading.local()


def get_buffer() -> CacheInvalidationBuffer:
    buf = getattr(_buffer_local, "buffer", None)
    if buf is None:
        buf = CacheInvalidationBuffer()
        _buffer_local.buffer = buf
    return buf


def drain_buffer() -> None:
    """on_commit callback (and patched __exit__ safety net) that applies
    the stashed ops to memcached."""
    ops = get_buffer().take_pending_flush_ops()
    if ops:
        # Lazy import to avoid a circular dependency: cache.py imports
        # this module, and we need its low-level memcached helpers here.
        from zerver.lib.cache import _flush_buffered_ops

        try:
            _flush_buffered_ops(ops)
        except Exception:
            # The transaction has already committed, and raising out of
            # an on_commit hook would abort the hooks queued behind it.
            logger.exception("Error while flushing buffered cache operations")


# Hook into Django's atomic() lifecycle.  Importing this module from
# zerver/lib/cache.py at module load installs the patch before any
# cache call that depends on the buffer.

_original_atomic_enter = transaction.Atomic.__enter__
_original_atomic_exit = transaction.Atomic.__exit__


def _patched_atomic_enter(self: transaction.Atomic) -> None:
    if getattr(self, "_from_testcase", False):
        # Django's TestCase wraps each test class and each test method
        # in atomic() blocks that get rolled back at teardown; ignore
        # them so the buffer's "outermost" mirrors user-level atomics.
        _original_atomic_enter(self)
        return
    _original_atomic_enter(self)
    buffer = get_buffer()
    is_outermost = not buffer.in_transaction()
    buffer.enter_atomic()
    if is_outermost:
        # If a previous outermost atomic exited commit-style but Django
        # silently rolled it back (needs_rollback / closed_in_transaction
        # / a DatabaseError out of COMMIT), the on_commit hooks were
        # cleared and our drain never ran.  Drop the stash so it can't
        # leak into the new transaction.
        buffer.take_pending_flush_ops()
        # Register the flush at the head of the on_commit queue so it
        # fires after the DB commit but before any user on_commit
        # callbacks registered later.
        transaction.on_commit(drain_buffer)


def _patched_atomic_exit(
    self: transaction.Atomic,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    traceback: Any,
) -> bool | None:
    if getattr(self, "_from_testcase", False):
        return _original_atomic_exit(self, exc_type, exc_value, traceback)

    buffer = get_buffer()
    is_outermost_buffer_frame = len(buffer._stack) == 1

    # Decide commit vs rollback the same way Django will: an exception
    # is one trigger; `connection.needs_rollback` (set by an inner
    # `savepoint=False` whose body raised and was caught between the
    # two `with` blocks) and `closed_in_transaction` are the others.
    # Zulip is single-DB; if a second DB is ever added, this needs to
    # consult connections[self.using] instead.
    committed = (
        exc_type is None and not connection.needs_rollback and not connection.closed_in_transaction
    )
    buffer.exit_atomic(committed=committed)

    try:
        return _original_atomic_exit(self, exc_type, exc_value, traceback)
    except Exception:  # nocoverage
        # COMMIT itself raised (e.g. a DatabaseError); Django ran a
        # rollback internally and cleared on_commit hooks.  Discard the
        # stash so it can't leak into the next transaction.
        buffer.take_pending_flush_ops()
        raise
    finally:
        # Safety net for environments where on_commit hooks don't fire
        # -- chiefly Django's TestCase, whose wrapping atomic rolls
        # back at tearDown, dropping every on_commit registered against
        # it.  In production with a real outermost atomic, on_commit
        # has already drained the stash and this is a no-op.  Peek at
        # the stash without consuming it; drain_buffer takes ownership.
        if is_outermost_buffer_frame and buffer._pending_flush_ops is not None:
            drain_buffer()


transaction.Atomic.__enter__ = _patched_atomic_enter  # type: ignore[method-assign] # monkey-patch hook into Django
transaction.Atomic.__exit__ = _patched_atomic_exit  # type: ignore[method-assign,assignment] # monkey-patch hook into Django

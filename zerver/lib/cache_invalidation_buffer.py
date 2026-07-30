"""Per-transaction buffer of pending cache mutations.

Cache mutations issued inside an `atomic()` block are recorded here and
applied to memcached only when the outermost transaction commits.  This
gives them the same all-or-nothing semantics as the DB writes that
triggered them:

  * The writer's own transaction sees its own mutations immediately --
    a buffered set returns the new value on subsequent reads, a buffered
    delete forces a miss.
  * Other connections see the mutations only after the outermost
    `atomic()` exits successfully.
  * On rollback, the rolled-back frame's buffered mutations are
    discarded and (for the rolled-back portion) memcached is untouched
    -- in particular, no value the writer fetched from its own
    pre-commit DB snapshot ends up cached.

Two kinds of mutation flow through the buffer:

  * Write-through writes (cache_set / cache_set_many) and
    writer-side invalidations (cache_delete / cache_delete_many).
    These are recorded with no memcached cas_id; the commit-time
    flush issues them as unconditional set_many / delete_many.
  * Read-through fills (the cache_add + cache_cas pair).  These have
    to coexist with cross-connection mark-then-fill: cache_add writes
    the sentinel directly into memcached and captures memcached's
    own cas_id, then records that cas_id in the buffer entry.  cache_cas
    *only* updates the buffer (no memcached write).  At commit, the
    flush issues cas-conditional set_many for those entries, keyed on
    the captured cas_id; if a concurrent invalidation landed on the
    slot during our transaction, our flush correctly fails and we
    don't overwrite that other writer's invalidation.  The sentinel
    itself has a 30s TTL, so a writer that rolls back leaves a brief
    "fill in progress" marker on the slot that other readers see and
    bypass; no committed-but-rolled-back value ever lands in memcached.

The buffer is per-thread, modeled as a stack of frames with one frame
per open atomic block.  Each frame is a dict mapping key -> pending
op, where the op is one of:

  * ('delete', None, None, 0)            -- pending delete
  * ('set', value, timeout, 0)           -- pending write-through set
  * ('set', value, timeout, mc_cas_id)   -- pending fill set, cas
                                            commits against mc_cas_id

Within a frame, later ops on the same key overwrite earlier ones (the
final intended state wins, e.g. set-then-delete collapses to delete
and delete-then-set collapses to set).  Savepoint commit merges the
inner frame into its parent (later wins again); savepoint rollback
discards the inner frame.

Flush ordering: at the moment the outermost atomic begins, we register
a `transaction.on_commit(_drain_buffer)` callback.  on_commit hooks
fire only on actual successful commit (Django clears them on rollback,
including the silent rollback paths -- `connection.needs_rollback`
having been set by an inner `savepoint=False` block, a DatabaseError
out of COMMIT, or `connection.closed_in_transaction`).  Registering at
__enter__ also puts our flush at the head of the on_commit queue so
user `transaction.on_commit(lambda: cache_delete(...))` callbacks --
the existing pre-buffer idiom -- run *after* our flush, preserving
their delete-wins semantics.

Django's TestCase wraps each test in an atomic block and rolls that
wrapper back at tearDown, so on_commit hooks queued against it never
fire.  Two pieces handle this: (a) atomics with `_from_testcase` set
are skipped entirely by the buffer, so user atomics inside a test
become the buffer's outermost; (b) the patched __exit__ runs a direct
flush as a safety net when the outermost buffer frame exited
commit-style but on_commit didn't fire.  In production, on_commit
always fires and the safety net is a no-op.
"""

import pickle
import threading
from typing import Any

from django.db import connection, transaction

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
        # _drain_buffer (the on_commit callback) or, in tests where
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


def _drain_buffer() -> None:
    """on_commit callback (and patched __exit__ safety net) that applies
    the stashed ops to memcached."""
    ops = get_buffer().take_pending_flush_ops()
    if ops:
        # Lazy import to avoid a circular dependency: cache.py imports
        # this module, and we need its low-level memcached helpers here.
        from zerver.lib.cache import _flush_buffered_ops

        _flush_buffered_ops(ops)


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
        transaction.on_commit(_drain_buffer)


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
        # the stash without consuming it; _drain_buffer takes ownership.
        if is_outermost_buffer_frame and buffer._pending_flush_ops is not None:
            _drain_buffer()


transaction.Atomic.__enter__ = _patched_atomic_enter  # type: ignore[method-assign] # monkey-patch hook into Django
transaction.Atomic.__exit__ = _patched_atomic_exit  # type: ignore[method-assign,assignment] # monkey-patch hook into Django

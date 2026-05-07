"""Cross-transaction tests of repeatable_read_atomic and the cache
layer's snapshot-staleness checks.

ZulipTestCase wraps each test in an atomic block that holds every
write as 'in progress' until tearDown rollback, which makes some
behaviors of REPEATABLE READ untestable inside it -- the SET
TRANSACTION SQL fails on a savepoint, and `pg_xact_status(xmax)`
considers test writes 'in progress' rather than 'committed'.
ZulipTransactionTestCase has no outer atomic, so we can exercise the
real outermost-transaction code paths here.
"""

from django.db import connection

from zerver.lib.snapshot_isolation import repeatable_read_atomic
from zerver.lib.test_classes import ZulipTransactionTestCase


class SnapshotIsolationIntegrationTest(ZulipTransactionTestCase):
    def test_set_transaction_runs_at_real_outermost_atomic(self) -> None:
        """When repeatable_read_atomic is the real outermost atomic
        (no test-wrapper savepoint above it), the SET TRANSACTION SQL
        actually runs and the connection's isolation level becomes
        REPEATABLE READ."""
        with repeatable_read_atomic(), connection.cursor() as cur:
            cur.execute("SHOW transaction_isolation")
            (level,) = cur.fetchone()
            self.assertEqual(level, "repeatable read")

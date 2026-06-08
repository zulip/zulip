"""Cross-transaction tests of repeatable_read_atomic and the cache
layer's snapshot-staleness checks.

ZulipTestCase wraps each test in an atomic block that holds every
write as 'in progress' until tearDown rollback, which makes some
behaviors of REPEATABLE READ untestable inside it -- the SET
TRANSACTION SQL fails on a savepoint, and `pg_xact_status(xmax)`
considers test writes 'in progress' rather than 'committed'.
ZulipTransactionTestCase has no outer atomic, so we can exercise the
real outermost-transaction code paths here, and commit a writer's
update on a separate connection while the main thread holds a
REPEATABLE READ snapshot.
"""

import threading

from django.db import connection, connections, transaction
from typing_extensions import override

from zerver.lib.cache import (
    cache_delete,
    cache_get,
    single_user_display_recipient_cache_key,
    user_profile_by_id_cache_key,
)
from zerver.lib.display_recipient import bulk_fetch_single_user_display_recipients
from zerver.lib.snapshot_isolation import repeatable_read_atomic
from zerver.lib.test_classes import ZulipTransactionTestCase
from zerver.models import UserProfile
from zerver.models.users import get_user_profile_by_id


def _commit_full_name_update_on_other_connection(user_id: int, new_full_name: str) -> None:
    """Run an UPDATE in a separate transaction on a fresh connection so
    the main thread's REPEATABLE READ snapshot does not see it -- and
    commit, so pg_xact_status reports the writer's xid as committed
    when the cache layer's xmax check runs in the main thread."""
    exc: list[BaseException] = []

    def writer() -> None:
        try:
            with transaction.atomic(durable=True):
                UserProfile.objects.filter(id=user_id).update(full_name=new_full_name)
        except BaseException as e:  # nocoverage
            exc.append(e)
        finally:
            connections["default"].close()

    thread = threading.Thread(target=writer)
    thread.start()
    thread.join(timeout=10)
    if exc:  # nocoverage
        raise exc[0]


class SnapshotIsolationIntegrationTest(ZulipTransactionTestCase):
    # Hardcoded so a previous test that left an unrestored value
    # doesn't propagate into this one.  Matches the dev/test fixtures.
    _HAMLET_ORIGINAL_FULL_NAME = "King Hamlet"

    @override
    def setUp(self) -> None:
        super().setUp()
        self._hamlet = UserProfile.objects.get(delivery_email="hamlet@zulip.com")

    @override
    def tearDown(self) -> None:
        # TransactionTestCase commits, so undo the writer's UPDATE
        # before the next test (or test suite teardown) sees it.
        UserProfile.objects.filter(id=self._hamlet.id).update(
            full_name=self._HAMLET_ORIGINAL_FULL_NAME
        )
        cache_delete(user_profile_by_id_cache_key(self._hamlet.id))
        cache_delete(single_user_display_recipient_cache_key(self._hamlet.id))
        super().tearDown()

    def test_set_transaction_runs_at_real_outermost_atomic(self) -> None:
        """When repeatable_read_atomic is the real outermost atomic
        (no test-wrapper savepoint above it), the SET TRANSACTION SQL
        actually runs and the connection's isolation level becomes
        REPEATABLE READ."""
        with repeatable_read_atomic(), connection.cursor() as cur:
            cur.execute("SHOW transaction_isolation")
            (level,) = cur.fetchone()
            self.assertEqual(level, "repeatable read")

    def test_bulk_path_drops_fill_for_concurrently_updated_row(self) -> None:
        """generic_bulk_cached_fetch's xmax check should detect the
        writer's committed-since-our-snapshot update and exclude that
        row from the cache write."""
        cache_delete(single_user_display_recipient_cache_key(self._hamlet.id))

        with repeatable_read_atomic():
            # Force the snapshot to be taken now (PostgreSQL takes the
            # snapshot at the first read, not at BEGIN).
            UserProfile.objects.get(id=self._hamlet.id)

            _commit_full_name_update_on_other_connection(
                self._hamlet.id, "Updated mid-snapshot (bulk)"
            )

            bulk_fetch_single_user_display_recipients([self._hamlet.id])

        self.assertIsNone(cache_get(single_user_display_recipient_cache_key(self._hamlet.id)))

    def test_per_row_staleness_filter_drops_fill_for_concurrent_update(self) -> None:
        """cache_with_key with model+staleness_filter should drop the
        cache write when the underlying row was updated by a
        transaction that committed since our snapshot started."""
        cache_delete(user_profile_by_id_cache_key(self._hamlet.id))

        with repeatable_read_atomic():
            UserProfile.objects.get(id=self._hamlet.id)

            _commit_full_name_update_on_other_connection(
                self._hamlet.id, "Updated mid-snapshot (per-row)"
            )

            get_user_profile_by_id(self._hamlet.id)

        self.assertIsNone(cache_get(user_profile_by_id_cache_key(self._hamlet.id)))

    def test_no_concurrent_update_fills_cache_normally(self) -> None:
        """Sanity check: with no writer racing, the fill goes through
        and the cache holds the value -- otherwise the staleness-drop
        tests above would pass even with the xmax check broken."""
        cache_delete(user_profile_by_id_cache_key(self._hamlet.id))

        with repeatable_read_atomic():
            get_user_profile_by_id(self._hamlet.id)

        self.assertIsNotNone(cache_get(user_profile_by_id_cache_key(self._hamlet.id)))

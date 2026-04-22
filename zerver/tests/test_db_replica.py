from unittest import mock

from django.db import DatabaseError, connections
from django.test import override_settings
from typing_extensions import override

from zerver.lib import db_replica
from zerver.lib.db_replica import (
    DEFAULT_DB_ALIAS,
    REPLICA_DB_ALIAS,
    ReadReplicaRouter,
    active_replica_alias,
    get_replica_message_id_watermark,
    use_replica,
)
from zerver.lib.test_classes import ZulipTestCase


class UseReplicaTest(ZulipTestCase):
    def test_alias_set_and_cleared(self) -> None:
        self.assertIsNone(active_replica_alias())
        with use_replica():
            self.assertEqual(active_replica_alias(), REPLICA_DB_ALIAS)
        self.assertIsNone(active_replica_alias())

    def test_nested_restores_previous(self) -> None:
        with use_replica():
            self.assertEqual(active_replica_alias(), REPLICA_DB_ALIAS)
            with use_replica():
                self.assertEqual(active_replica_alias(), REPLICA_DB_ALIAS)
            self.assertEqual(active_replica_alias(), REPLICA_DB_ALIAS)
        self.assertIsNone(active_replica_alias())

    def test_alias_cleared_after_exception(self) -> None:
        with self.assertRaises(RuntimeError), use_replica():
            self.assertEqual(active_replica_alias(), REPLICA_DB_ALIAS)
            raise RuntimeError("boom")
        self.assertIsNone(active_replica_alias())


class ReadReplicaRouterTest(ZulipTestCase):
    def test_db_for_read_follows_active_alias(self) -> None:
        router = ReadReplicaRouter()
        self.assertIsNone(router.db_for_read(object()))
        with use_replica():
            self.assertEqual(router.db_for_read(object()), REPLICA_DB_ALIAS)

    def test_db_for_write_routes_to_active_alias(self) -> None:
        router = ReadReplicaRouter()
        # Outside use_replica(): "no opinion", so Django uses default.
        self.assertIsNone(router.db_for_write(object()))
        # Inside use_replica(): writes go to the replica alias, whose
        # connection rejects them. We prefer a loud error over a
        # silent cross-alias write.
        with use_replica():
            self.assertEqual(router.db_for_write(object()), REPLICA_DB_ALIAS)

    def test_allow_migrate_only_default(self) -> None:
        router = ReadReplicaRouter()
        self.assertTrue(router.allow_migrate(DEFAULT_DB_ALIAS, "zerver"))
        self.assertFalse(router.allow_migrate(REPLICA_DB_ALIAS, "zerver"))

    def test_allow_relation_is_always_true(self) -> None:
        router = ReadReplicaRouter()
        self.assertTrue(router.allow_relation(object(), object()))


class WriteInsideUseReplicaIsRejectedTest(ZulipTestCase):
    """End-to-end: verify that a real INSERT inside use_replica() fails.

    This combines the router (writes route to "replica") and the
    replica connection's libpq ``default_transaction_read_only=on``
    setting. In test mode, "replica" mirrors the default DB, so the
    rejection comes purely from the connection-level read-only flag,
    not from the replica being a physical standby.
    """

    databases = {"default", "replica"}

    def test_orm_write_raises_read_only_error(self) -> None:
        from zerver.models import UserProfile

        with use_replica(), self.assertRaisesRegex(DatabaseError, "read-only"):
            UserProfile.objects.filter(id=-1).update(full_name="nope")


@override_settings(REPLICA_WATERMARK_CACHE_SECONDS=2)
class WatermarkTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        db_replica._reset_watermark_cache_for_tests()

    def _patch_cursor(self, fetchone_result: object) -> "mock._patch[mock.MagicMock]":
        cursor_cm = mock.MagicMock()
        cursor_cm.__enter__.return_value.fetchone.return_value = fetchone_result
        cursor_cm.__exit__.return_value = False
        return mock.patch.object(
            connections[REPLICA_DB_ALIAS],
            "cursor",
            return_value=cursor_cm,
        )

    def test_returns_max_id(self) -> None:
        with self._patch_cursor((12345,)) as cursor_mock:
            self.assertEqual(get_replica_message_id_watermark(), 12345)
            self.assertEqual(cursor_mock.call_count, 1)

    def test_cached_within_ttl(self) -> None:
        with (
            mock.patch("zerver.lib.db_replica.time.monotonic", side_effect=[100.0, 100.0, 101.0]),
            self._patch_cursor((42,)) as cursor_mock,
        ):
            self.assertEqual(get_replica_message_id_watermark(), 42)
            self.assertEqual(get_replica_message_id_watermark(), 42)
            self.assertEqual(cursor_mock.call_count, 1)

    def test_refreshes_after_ttl(self) -> None:
        fetchone_results = [(10,), (20,)]
        cursor_cm = mock.MagicMock()
        cursor_cm.__enter__.return_value.fetchone.side_effect = fetchone_results
        cursor_cm.__exit__.return_value = False
        # First invocation: 2 monotonic() calls (outer read + cache write).
        # Second invocation past TTL: 3 calls (outer read + lock re-check + cache write).
        with (
            mock.patch(
                "zerver.lib.db_replica.time.monotonic",
                side_effect=[100.0, 100.0, 105.0, 105.0, 105.0],
            ),
            mock.patch.object(
                connections[REPLICA_DB_ALIAS],
                "cursor",
                return_value=cursor_cm,
            ) as cursor_mock,
        ):
            self.assertEqual(get_replica_message_id_watermark(), 10)
            self.assertEqual(get_replica_message_id_watermark(), 20)
            self.assertEqual(cursor_mock.call_count, 2)

    def test_returns_none_on_empty_table(self) -> None:
        with self._patch_cursor((None,)):
            self.assertIsNone(get_replica_message_id_watermark())

    def test_returns_none_on_database_error(self) -> None:
        with (
            mock.patch.object(
                connections[REPLICA_DB_ALIAS],
                "cursor",
                side_effect=DatabaseError("replica down"),
            ),
            self.assertLogs("zerver.lib.db_replica", level="WARNING"),
        ):
            self.assertIsNone(get_replica_message_id_watermark())

    def test_cache_hit_during_double_check(self) -> None:
        """A concurrent caller can populate the cache while we wait on
        the lock; the inner re-check short-circuits the DB query."""
        import time
        from types import TracebackType

        real_lock = db_replica._watermark_lock

        class PopulatingLock:
            def __enter__(self) -> None:
                db_replica._watermark_cache[REPLICA_DB_ALIAS] = (
                    time.monotonic(),
                    777,
                )
                real_lock.__enter__()

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                real_lock.__exit__(exc_type, exc, tb)

        with mock.patch.object(db_replica, "_watermark_lock", PopulatingLock()):
            self.assertEqual(get_replica_message_id_watermark(), 777)

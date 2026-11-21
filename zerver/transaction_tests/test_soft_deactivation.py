import threading
import time
from collections.abc import Mapping
from unittest import mock

from django.db import connection, connections
from typing_extensions import override

from zerver.lib.test_classes import ZulipTransactionTestCase
from zerver.models import RealmAuditLog, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.worker.deferred_work import DeferredWorker


class SoftReactivationRaceConditionTest(ZulipTransactionTestCase):
    @override
    def tearDown(self) -> None:
        # Undo the committed reactivation, even if the test failed partway.
        user = self.example_user("hamlet")
        user.long_term_idle = False
        user.save(update_fields=["long_term_idle"])
        RealmAuditLog.objects.filter(
            modified_user=user, event_type=AuditLogEventType.USER_SOFT_ACTIVATED
        ).delete()
        super().tearDown()

    def test_concurrent_soft_reactivations_backfill_once(self) -> None:
        # A user who opens a second tab, or reloads, while the first tab is
        # still waiting for their account to be ready queues a second
        # soft_reactivate job, which a server running several deferred_work
        # workers can process at the same time as the first.
        user = self.example_user("hamlet")
        user.long_term_idle = True
        user.save(update_fields=["long_term_idle"])

        backfilled_user_ids: list[int] = []
        first_backfill_started = threading.Event()
        first_backfill_released = threading.Event()

        def hold_first_backfill(user_profile: UserProfile) -> None:
            backfilled_user_ids.append(user_profile.id)
            if len(backfilled_user_ids) == 1:
                first_backfill_started.set()
                first_backfill_released.wait(timeout=10)

        def run_soft_reactivate_job() -> None:
            try:
                DeferredWorker().consume(
                    {"type": "soft_reactivate", "user_profile_id": user.id, "notify_client": True}
                )
            finally:
                # Close all thread-local database connections
                connections.close_all()

        def query_is_waiting_on_lock() -> bool:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_stat_activity
                        WHERE datname = current_database() AND wait_event_type = 'Lock'
                    )
                    """
                )
                row = cursor.fetchone()
            assert row is not None
            return row[0]

        notices: list[Mapping[str, object]] = []
        first_job = threading.Thread(target=run_soft_reactivate_job)
        second_job = threading.Thread(target=run_soft_reactivate_job)
        with (
            mock.patch(
                "zerver.lib.soft_deactivation.add_missing_messages",
                side_effect=hold_first_backfill,
            ),
            mock.patch("zerver.tornado.event_queue.process_notification", notices.append),
            self.assertLogs("zulip.soft_deactivation", level="INFO") as soft_deactivation_logs,
            self.assertLogs("zerver.worker.deferred_work", level="INFO"),
        ):
            first_job.start()
            self.assertTrue(first_backfill_started.wait(timeout=10))

            second_job.start()
            # Keep the first job mid-backfill until the second job is either
            # waiting for the first to commit, or running a backfill of its own.
            for _ in range(100):
                if query_is_waiting_on_lock() or len(backfilled_user_ids) > 1:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("The second job never reached the row lock")

            first_backfill_released.set()
            first_job.join()
            second_job.join()

        self.assertEqual(backfilled_user_ids, [user.id])
        self.assertEqual(
            soft_deactivation_logs.output,
            [f"INFO:zulip.soft_deactivation:Soft reactivated user {user.id}"],
        )
        user.refresh_from_db()
        self.assertFalse(user.long_term_idle)

        # The job that did no backfill still notifies the user's clients,
        # since its tab may have registered after the first job's event.
        self.assertEqual(
            notices,
            [{"event": {"type": "long_term_idle", "value": False}, "users": [user.id]}] * 2,
        )

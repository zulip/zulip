import base64
import os
import signal
import time
from collections import defaultdict
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional
from unittest.mock import MagicMock, patch

import orjson
import time_machine
from django.conf import settings
from django.db.utils import IntegrityError
from django.test import override_settings
from typing_extensions import TypeAlias, override

from zerver.lib.email_mirror import RateLimitedRealmMirror
from zerver.lib.email_mirror_helpers import encode_email_address
from zerver.lib.queue import MAX_REQUEST_RETRIES
from zerver.lib.rate_limiter import RateLimiterLockingError
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.lib.send_email import EmailNotDeliveredError, FromAddress
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.models import ScheduledMessageNotificationEmail, UserActivity, UserProfile
from zerver.models.clients import get_client
from zerver.models.realms import get_realm
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.streams import get_stream
from zerver.tornado.event_queue import build_offline_notification
from zerver.worker import base as base_worker
from zerver.worker.email_mirror import MirrorWorker
from zerver.worker.email_senders import EmailSendingWorker
from zerver.worker.embed_links import FetchLinksEmbedData
from zerver.worker.missedmessage_emails import MissedMessageWorker
from zerver.worker.missedmessage_mobile_notifications import PushNotificationsWorker
from zerver.worker.user_activity import UserActivityWorker

Event: TypeAlias = Dict[str, Any]


class FakeClient:
    def __init__(self, prefetch: int = 0) -> None:
        self.queues: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def enqueue(self, queue_name: str, data: Dict[str, Any]) -> None:
        self.queues[queue_name].append(data)

    def start_json_consumer(
        self,
        queue_name: str,
        callback: Callable[[List[Dict[str, Any]]], None],
        batch_size: int = 1,
        timeout: Optional[int] = None,
    ) -> None:
        chunk: List[Dict[str, Any]] = []
        queue = self.queues[queue_name]
        while queue:
            chunk.append(queue.pop(0))
            if len(chunk) >= batch_size or not len(queue):
                callback(chunk)
                chunk = []

    def local_queue_size(self) -> int:
        return sum(len(q) for q in self.queues.values())


@contextmanager
def simulated_queue_client(client: FakeClient) -> Iterator[None]:
    with patch.object(base_worker, "SimpleQueueClient", lambda *args, **kwargs: client):
        yield


class WorkerTest(ZulipTestCase):
    def test_useractivity_worker(self) -> None:
        fake_client = FakeClient()

        user = self.example_user("hamlet")
        other_user = self.example_user("iago")
        UserActivity.objects.filter(
            user_profile__in=[user.id, other_user.id],
        ).delete()

        # Enqueue two events for the same user/client/query
        now = datetime(year=2024, month=1, day=1, tzinfo=timezone.utc).timestamp()
        for event_time in [now, now + 10]:
            fake_client.enqueue(
                "user_activity",
                dict(
                    user_profile_id=user.id,
                    client_id=get_client("ios").id,
                    time=event_time,
                    query="send_message",
                ),
            )
        # And a third event for a different query
        fake_client.enqueue(
            "user_activity",
            dict(
                user_profile_id=user.id,
                client_id=get_client("ios").id,
                time=now + 15,
                query="get_events",
            ),
        )
        # One for a different client
        fake_client.enqueue(
            "user_activity",
            dict(
                user_profile_id=user.id,
                client_id=get_client("website").id,
                time=now + 20,
                query="get_events",
            ),
        )

        # And one for a different user
        fake_client.enqueue(
            "user_activity",
            dict(
                user_profile_id=other_user.id,
                client_id=get_client("ios").id,
                time=now + 25,
                query="get_events",
            ),
        )

        # Run the worker; this will produce a single upsert statement
        with simulated_queue_client(fake_client):
            worker = UserActivityWorker()
            worker.setup()
            with self.assert_database_query_count(1):
                worker.start()

        activity_records = UserActivity.objects.filter(
            user_profile__in=[user.id, other_user.id],
        ).order_by("last_visit")
        self.assert_length(activity_records, 4)

        self.assertEqual(activity_records[0].query, "send_message")
        self.assertEqual(activity_records[0].client.name, "ios")
        self.assertEqual(activity_records[0].count, 2)
        self.assertEqual(
            activity_records[0].last_visit, datetime.fromtimestamp(now + 10, tz=timezone.utc)
        )

        self.assertEqual(activity_records[1].query, "get_events")
        self.assertEqual(activity_records[1].client.name, "ios")
        self.assertEqual(activity_records[1].count, 1)
        self.assertEqual(
            activity_records[1].last_visit, datetime.fromtimestamp(now + 15, tz=timezone.utc)
        )

        self.assertEqual(activity_records[2].query, "get_events")
        self.assertEqual(activity_records[2].client.name, "website")
        self.assertEqual(activity_records[2].count, 1)
        self.assertEqual(
            activity_records[2].last_visit, datetime.fromtimestamp(now + 20, tz=timezone.utc)
        )

        self.assertEqual(activity_records[3].query, "get_events")
        self.assertEqual(activity_records[3].user_profile, other_user)
        self.assertEqual(activity_records[3].count, 1)
        self.assertEqual(
            activity_records[3].last_visit, datetime.fromtimestamp(now + 25, tz=timezone.utc)
        )

        # Add 3 more events which stack atop the existing send_message
        # to test the update part, and a new "home_real" event to show
        # the insert part of the upsert.
        for event_time in [now + 30, now + 35, now + 40]:
            fake_client.enqueue(
                "user_activity",
                dict(
                    user_profile_id=user.id,
                    client_id=get_client("ios").id,
                    time=event_time,
                    query="send_message",
                ),
            )
        fake_client.enqueue(
            "user_activity",
            dict(
                user_profile_id=user.id,
                client_id=get_client("ios").id,
                time=now + 45,
                query="home_real",
            ),
        )
        # Run the worker again; this will insert one row and update the other
        with simulated_queue_client(fake_client):
            worker = UserActivityWorker()
            worker.setup()
            with self.assert_database_query_count(1):
                worker.start()
        activity_records = UserActivity.objects.filter(
            user_profile__in=[user.id, other_user.id],
        ).order_by("last_visit")
        self.assert_length(activity_records, 5)
        self.assertEqual(activity_records[3].query, "send_message")
        self.assertEqual(activity_records[3].client.name, "ios")
        self.assertEqual(activity_records[3].count, 5)
        self.assertEqual(
            activity_records[3].last_visit, datetime.fromtimestamp(now + 40, tz=timezone.utc)
        )
        self.assertEqual(activity_records[4].query, "home_real")
        self.assertEqual(activity_records[4].client.name, "ios")
        self.assertEqual(activity_records[4].count, 1)
        self.assertEqual(
            activity_records[4].last_visit, datetime.fromtimestamp(now + 45, tz=timezone.utc)
        )

    def test_missed_message_worker(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        hamlet1_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=hamlet,
            content="hi hamlet",
        )

        hamlet2_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=hamlet,
            content="goodbye hamlet",
        )

        hamlet3_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=hamlet,
            content="hello again hamlet",
        )

        othello_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=othello,
            content="where art thou, othello?",
        )

        hamlet_event1 = dict(
            user_profile_id=hamlet.id,
            message_id=hamlet1_msg_id,
            trigger=NotificationTriggers.DIRECT_MESSAGE,
        )
        hamlet_event2 = dict(
            user_profile_id=hamlet.id,
            message_id=hamlet2_msg_id,
            trigger=NotificationTriggers.DIRECT_MESSAGE,
            mentioned_user_group_id=4,
        )
        othello_event = dict(
            user_profile_id=othello.id,
            message_id=othello_msg_id,
            trigger=NotificationTriggers.DIRECT_MESSAGE,
        )

        events = [hamlet_event1, hamlet_event2, othello_event]

        mmw = MissedMessageWorker()
        batch_duration = timedelta(seconds=hamlet.email_notifications_batching_period_seconds)
        assert (
            hamlet.email_notifications_batching_period_seconds
            == othello.email_notifications_batching_period_seconds
        )

        send_mock = patch(
            "zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip",
        )

        bonus_event_hamlet = dict(
            user_profile_id=hamlet.id,
            message_id=hamlet3_msg_id,
            trigger=NotificationTriggers.DIRECT_MESSAGE,
        )

        def check_row(
            row: ScheduledMessageNotificationEmail,
            scheduled_timestamp: datetime,
            mentioned_user_group_id: Optional[int],
        ) -> None:
            self.assertEqual(row.trigger, NotificationTriggers.DIRECT_MESSAGE)
            self.assertEqual(row.scheduled_timestamp, scheduled_timestamp)
            self.assertEqual(row.mentioned_user_group_id, mentioned_user_group_id)

        def advance() -> Optional[float]:
            mmw.stopping = False

            def inner(check: Callable[[], bool], timeout: Optional[float]) -> bool:
                # The check should never pass, since we've just (with
                # the lock) ascertained above the cv.wait that its
                # conditions are not met.
                self.assertFalse(check())

                # Set ourself to stop at the top of the next loop, but
                # pretend we didn't get an event
                mmw.stopping = True
                return False

            with patch.object(mmw.cv, "wait_for", side_effect=inner):
                mmw.work()
            return mmw.has_timeout

        # With nothing enqueued, the condition variable is pending
        # forever.  We double-check that the condition is false in
        # steady-state.
        has_timeout = advance()
        self.assertFalse(has_timeout)

        # Enqueues the events to the internal queue, as if from RabbitMQ
        time_zero = datetime(2021, 1, 1, tzinfo=timezone.utc)
        with time_machine.travel(time_zero, tick=False), patch.object(
            mmw.cv, "notify"
        ) as notify_mock:
            for event in events:
                mmw.consume_single_event(event)
        # All of these notify, because has_timeout is still false in
        # each case.  This represents multiple consume() calls getting
        # the lock before the worker escapes the wait_for, and is
        # unlikely in real life but does not lead to incorrect
        # behaviour.
        self.assertEqual(notify_mock.call_count, 3)

        # This leaves a timeout set, since there are objects pending
        with time_machine.travel(time_zero, tick=False):
            has_timeout = advance()
        self.assertTrue(has_timeout)

        expected_scheduled_timestamp = time_zero + batch_duration

        # The events should be saved in the database
        hamlet_row1 = ScheduledMessageNotificationEmail.objects.get(
            user_profile_id=hamlet.id, message_id=hamlet1_msg_id
        )
        check_row(hamlet_row1, expected_scheduled_timestamp, None)

        hamlet_row2 = ScheduledMessageNotificationEmail.objects.get(
            user_profile_id=hamlet.id, message_id=hamlet2_msg_id
        )
        check_row(hamlet_row2, expected_scheduled_timestamp, 4)

        othello_row1 = ScheduledMessageNotificationEmail.objects.get(
            user_profile_id=othello.id, message_id=othello_msg_id
        )
        check_row(othello_row1, expected_scheduled_timestamp, None)

        # If another event is received, test that it gets saved with the same
        # `expected_scheduled_timestamp` as the earlier events.

        few_moments_later = time_zero + timedelta(seconds=3)
        with time_machine.travel(few_moments_later, tick=False), patch.object(
            mmw.cv, "notify"
        ) as notify_mock:
            mmw.consume_single_event(bonus_event_hamlet)
        self.assertEqual(notify_mock.call_count, 0)

        with time_machine.travel(few_moments_later, tick=False):
            has_timeout = advance()
        self.assertTrue(has_timeout)
        hamlet_row3 = ScheduledMessageNotificationEmail.objects.get(
            user_profile_id=hamlet.id, message_id=hamlet3_msg_id
        )
        check_row(hamlet_row3, expected_scheduled_timestamp, None)

        # Now let us test `maybe_send_batched_emails`
        # If called too early, it shouldn't process the emails.
        one_minute_premature = expected_scheduled_timestamp - timedelta(seconds=60)
        with time_machine.travel(one_minute_premature, tick=False):
            has_timeout = advance()
        self.assertTrue(has_timeout)
        self.assertEqual(ScheduledMessageNotificationEmail.objects.count(), 4)

        # If called after `expected_scheduled_timestamp`, it should process all emails.
        one_minute_overdue = expected_scheduled_timestamp + timedelta(seconds=60)
        with time_machine.travel(one_minute_overdue, tick=True):
            with send_mock as sm, self.assertLogs(level="INFO") as info_logs:
                has_timeout = advance()
                self.assertTrue(has_timeout)
                self.assertEqual(ScheduledMessageNotificationEmail.objects.count(), 0)
                has_timeout = advance()
                self.assertFalse(has_timeout)

        self.assertEqual(
            [
                f"INFO:root:Batch-processing 3 missedmessage_emails events for user {hamlet.id}",
                f"INFO:root:Batch-processing 1 missedmessage_emails events for user {othello.id}",
            ],
            info_logs.output,
        )

        # Verify the payloads now
        args = [c[0] for c in sm.call_args_list]
        arg_dict = {
            arg[0].id: dict(
                missed_messages=arg[1],
                count=arg[2],
            )
            for arg in args
        }

        hamlet_info = arg_dict[hamlet.id]
        self.assertEqual(hamlet_info["count"], 3)
        self.assertEqual(
            {m["message"].content for m in hamlet_info["missed_messages"]},
            {"hi hamlet", "goodbye hamlet", "hello again hamlet"},
        )

        othello_info = arg_dict[othello.id]
        self.assertEqual(othello_info["count"], 1)
        self.assertEqual(
            {m["message"].content for m in othello_info["missed_messages"]},
            {"where art thou, othello?"},
        )

        # Hacky test coming up! We want to test the try-except block in the consumer which handles
        # IntegrityErrors raised when the message was deleted before it processed the notification
        # event.
        # However, Postgres defers checking ForeignKey constraints to when the current transaction
        # commits. This poses some difficulties in testing because of Django running tests inside a
        # transaction which never commits. See https://code.djangoproject.com/ticket/22431 for more
        # details, but the summary is that IntegrityErrors due to database constraints are raised at
        # the end of the test, not inside the `try` block. So, we have the code inside the `try` block
        # raise `IntegrityError` by mocking.
        with patch(
            "zerver.models.ScheduledMessageNotificationEmail.objects.create",
            side_effect=IntegrityError,
        ), self.assertLogs(level="DEBUG") as debug_logs, patch.object(
            mmw.cv, "notify"
        ) as notify_mock:
            mmw.consume_single_event(hamlet_event1)
            self.assertEqual(notify_mock.call_count, 0)
            self.assertIn(
                "DEBUG:root:ScheduledMessageNotificationEmail row could not be created. The message may have been deleted. Skipping event.",
                debug_logs.output,
            )

        # Verify that we make forward progress if one of the messages
        # throws an exception.  First, enqueue the messages, and get
        # them to create database rows:
        time_zero = datetime(2021, 1, 1, tzinfo=timezone.utc)
        with time_machine.travel(time_zero, tick=False), patch.object(
            mmw.cv, "notify"
        ) as notify_mock:
            mmw.consume_single_event(hamlet_event1)
            mmw.consume_single_event(hamlet_event2)
            mmw.consume_single_event(othello_event)
            # See above note about multiple notifies
            self.assertEqual(notify_mock.call_count, 3)
            has_timeout = advance()
            self.assertTrue(has_timeout)

        # Next, set up a fail-y consumer:
        def fail_some(user: UserProfile, *args: Any) -> None:
            if user.id == hamlet.id:
                raise RuntimeError

        one_minute_overdue = expected_scheduled_timestamp + timedelta(seconds=60)
        with time_machine.travel(one_minute_overdue, tick=False), self.assertLogs(
            level="ERROR"
        ) as error_logs, send_mock as sm:
            sm.side_effect = fail_some
            has_timeout = advance()
            self.assertTrue(has_timeout)
            self.assertEqual(ScheduledMessageNotificationEmail.objects.count(), 0)
            has_timeout = advance()
            self.assertFalse(has_timeout)
        self.assertIn(
            "ERROR:root:Failed to process 2 missedmessage_emails for user 10",
            error_logs.output[0],
        )

    def test_push_notifications_worker(self) -> None:
        """
        The push notifications system has its own comprehensive test suite,
        so we can limit ourselves to simple unit testing the queue processor,
        without going deeper into the system - by mocking the handle_push_notification
        functions to immediately produce the effect we want, to test its handling by the queue
        processor.
        """
        fake_client = FakeClient()

        def fake_publish(
            queue_name: str, event: Dict[str, Any], processor: Callable[[Any], None]
        ) -> None:
            fake_client.enqueue(queue_name, event)

        def generate_new_message_notification() -> Dict[str, Any]:
            return build_offline_notification(1, 1)

        def generate_remove_notification() -> Dict[str, Any]:
            return {
                "type": "remove",
                "user_profile_id": 1,
                "message_ids": [1],
            }

        with simulated_queue_client(fake_client):
            worker = PushNotificationsWorker()
            worker.setup()
            with patch(
                "zerver.worker.missedmessage_mobile_notifications.handle_push_notification"
            ) as mock_handle_new, patch(
                "zerver.worker.missedmessage_mobile_notifications.handle_remove_push_notification"
            ) as mock_handle_remove, patch(
                "zerver.worker.missedmessage_mobile_notifications.initialize_push_notifications"
            ):
                event_new = generate_new_message_notification()
                event_remove = generate_remove_notification()
                fake_client.enqueue("missedmessage_mobile_notifications", event_new)
                fake_client.enqueue("missedmessage_mobile_notifications", event_remove)

                worker.start()
                mock_handle_new.assert_called_once_with(event_new["user_profile_id"], event_new)
                mock_handle_remove.assert_called_once_with(
                    event_remove["user_profile_id"], event_remove["message_ids"]
                )

            with patch(
                "zerver.worker.missedmessage_mobile_notifications.handle_push_notification",
                side_effect=PushNotificationBouncerRetryLaterError("test"),
            ) as mock_handle_new, patch(
                "zerver.worker.missedmessage_mobile_notifications.handle_remove_push_notification",
                side_effect=PushNotificationBouncerRetryLaterError("test"),
            ) as mock_handle_remove, patch(
                "zerver.worker.missedmessage_mobile_notifications.initialize_push_notifications"
            ):
                event_new = generate_new_message_notification()
                event_remove = generate_remove_notification()
                fake_client.enqueue("missedmessage_mobile_notifications", event_new)
                fake_client.enqueue("missedmessage_mobile_notifications", event_remove)

                with mock_queue_publish(
                    "zerver.lib.queue.queue_json_publish", side_effect=fake_publish
                ), self.assertLogs(
                    "zerver.worker.missedmessage_mobile_notifications", "WARNING"
                ) as warn_logs:
                    worker.start()
                    self.assertEqual(mock_handle_new.call_count, 1 + MAX_REQUEST_RETRIES)
                    self.assertEqual(mock_handle_remove.call_count, 1 + MAX_REQUEST_RETRIES)
                self.assertEqual(
                    warn_logs.output,
                    [
                        "WARNING:zerver.worker.missedmessage_mobile_notifications:Maximum retries exceeded for trigger:1 event:push_notification",
                    ]
                    * 2,
                )

    @patch("zerver.worker.email_mirror.mirror_email")
    def test_mirror_worker(self, mock_mirror_email: MagicMock) -> None:
        fake_client = FakeClient()
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        data = [
            dict(
                msg_base64=base64.b64encode(b"\xf3test").decode(),
                time=time.time(),
                rcpt_to=stream_to_address,
            ),
        ] * 3
        for element in data:
            fake_client.enqueue("email_mirror", element)

        with simulated_queue_client(fake_client):
            worker = MirrorWorker()
            worker.setup()
            worker.start()

        self.assertEqual(mock_mirror_email.call_count, 3)

    @patch("zerver.worker.email_mirror.mirror_email")
    @override_settings(RATE_LIMITING_MIRROR_REALM_RULES=[(10, 2)])
    def test_mirror_worker_rate_limiting(self, mock_mirror_email: MagicMock) -> None:
        fake_client = FakeClient()
        realm = get_realm("zulip")
        RateLimitedRealmMirror(realm).clear_history()
        stream = get_stream("Denmark", realm)
        stream_to_address = encode_email_address(stream)
        data = [
            dict(
                msg_base64=base64.b64encode(b"\xf3test").decode(),
                time=time.time(),
                rcpt_to=stream_to_address,
            ),
        ] * 5
        for element in data:
            fake_client.enqueue("email_mirror", element)

        with simulated_queue_client(fake_client), self.assertLogs(
            "zerver.worker.email_mirror", level="WARNING"
        ) as warn_logs:
            start_time = time.time()
            with patch("time.time", return_value=start_time):
                worker = MirrorWorker()
                worker.setup()
                worker.start()
                # Of the first 5 messages, only 2 should be processed
                # (the rest being rate-limited):
                self.assertEqual(mock_mirror_email.call_count, 2)

                # If a new message is sent into the stream mirror, it will get rejected:
                fake_client.enqueue("email_mirror", data[0])
                worker.start()
                self.assertEqual(mock_mirror_email.call_count, 2)

                # However, message notification emails don't get rate limited:
                with self.settings(EMAIL_GATEWAY_PATTERN="%s@example.com"):
                    address = "mm" + ("x" * 32) + "@example.com"
                    event = dict(
                        msg_base64=base64.b64encode(b"\xf3test").decode(),
                        time=time.time(),
                        rcpt_to=address,
                    )
                    fake_client.enqueue("email_mirror", event)
                    worker.start()
                    self.assertEqual(mock_mirror_email.call_count, 3)

            # After some time passes, emails get accepted again:
            with patch("time.time", return_value=start_time + 11.0):
                fake_client.enqueue("email_mirror", data[0])
                worker.start()
                self.assertEqual(mock_mirror_email.call_count, 4)

                # If RateLimiterLockingError is thrown, we rate-limit the new message:
                with patch(
                    "zerver.lib.rate_limiter.RedisRateLimiterBackend.incr_ratelimit",
                    side_effect=RateLimiterLockingError,
                ):
                    with self.assertLogs("zerver.lib.rate_limiter", "WARNING") as mock_warn:
                        fake_client.enqueue("email_mirror", data[0])
                        worker.start()
                        self.assertEqual(mock_mirror_email.call_count, 4)
                        self.assertEqual(
                            mock_warn.output,
                            [
                                "WARNING:zerver.lib.rate_limiter:Deadlock trying to incr_ratelimit for RateLimitedRealmMirror:zulip"
                            ],
                        )
        self.assertEqual(
            warn_logs.output,
            [
                "WARNING:zerver.worker.email_mirror:MirrorWorker: Rejecting an email from: None to realm: zulip - rate limited."
            ]
            * 5,
        )

    def test_email_sending_worker_retries(self) -> None:
        """Tests the retry_send_email_failures decorator to make sure it
        retries sending the email 3 times and then gives up."""
        fake_client = FakeClient()

        data = {
            "template_prefix": "zerver/emails/confirm_new_email",
            "to_emails": [self.example_email("hamlet")],
            "from_name": "Zulip Account Security",
            "from_address": FromAddress.NOREPLY,
            "context": {},
        }
        fake_client.enqueue("email_senders", data)

        def fake_publish(
            queue_name: str, event: Dict[str, Any], processor: Optional[Callable[[Any], None]]
        ) -> None:
            fake_client.enqueue(queue_name, event)

        with simulated_queue_client(fake_client):
            worker = EmailSendingWorker()
            worker.setup()
            with patch(
                "zerver.lib.send_email.build_email", side_effect=EmailNotDeliveredError
            ), mock_queue_publish(
                "zerver.lib.queue.queue_json_publish", side_effect=fake_publish
            ), self.assertLogs(level="ERROR") as m:
                worker.start()
                self.assertIn("failed due to exception EmailNotDeliveredError", m.output[0])

        self.assertEqual(data["failed_tries"], 1 + MAX_REQUEST_RETRIES)

    def test_error_handling(self) -> None:
        processed = []

        @base_worker.assign_queue("unreliable_worker", is_test_queue=True)
        class UnreliableWorker(base_worker.QueueProcessingWorker):
            @override
            def consume(self, data: Mapping[str, Any]) -> None:
                if data["type"] == "unexpected behaviour":
                    raise Exception("Worker task not performing as expected!")
                processed.append(data["type"])

        fake_client = FakeClient()
        for msg in ["good", "fine", "unexpected behaviour", "back to normal"]:
            fake_client.enqueue("unreliable_worker", {"type": msg})

        fn = os.path.join(settings.QUEUE_ERROR_DIR, "unreliable_worker.errors")
        with suppress(FileNotFoundError):
            os.remove(fn)

        with simulated_queue_client(fake_client):
            worker = UnreliableWorker()
            worker.setup()
            with self.assertLogs(level="ERROR") as m:
                worker.start()
                self.assertEqual(
                    m.records[0].message, "Problem handling data on queue unreliable_worker"
                )
                self.assertIn(m.records[0].stack_info, m.output[0])

        self.assertEqual(processed, ["good", "fine", "back to normal"])
        with open(fn) as f:
            line = f.readline().strip()
        events = orjson.loads(line.split("\t")[1])
        self.assert_length(events, 1)
        event = events[0]
        self.assertEqual(event["type"], "unexpected behaviour")

        processed = []

        @base_worker.assign_queue("unreliable_loopworker", is_test_queue=True)
        class UnreliableLoopWorker(base_worker.LoopQueueProcessingWorker):
            @override
            def consume_batch(self, events: List[Dict[str, Any]]) -> None:
                for event in events:
                    if event["type"] == "unexpected behaviour":
                        raise Exception("Worker task not performing as expected!")
                    processed.append(event["type"])

        for msg in ["good", "fine", "unexpected behaviour", "back to normal"]:
            fake_client.enqueue("unreliable_loopworker", {"type": msg})

        fn = os.path.join(settings.QUEUE_ERROR_DIR, "unreliable_loopworker.errors")
        with suppress(FileNotFoundError):
            os.remove(fn)

        with simulated_queue_client(fake_client):
            loopworker = UnreliableLoopWorker()
            loopworker.setup()
            with self.assertLogs(level="ERROR") as m:
                loopworker.start()
                self.assertEqual(
                    m.records[0].message, "Problem handling data on queue unreliable_loopworker"
                )
                self.assertIn(m.records[0].stack_info, m.output[0])

        self.assertEqual(processed, ["good", "fine"])
        with open(fn) as f:
            line = f.readline().strip()
        events = orjson.loads(line.split("\t")[1])
        self.assert_length(events, 4)

        self.assertEqual(
            [event["type"] for event in events],
            ["good", "fine", "unexpected behaviour", "back to normal"],
        )

    def test_timeouts(self) -> None:
        processed = []

        @base_worker.assign_queue("timeout_worker", is_test_queue=True)
        class TimeoutWorker(base_worker.QueueProcessingWorker):
            MAX_CONSUME_SECONDS = 1

            @override
            def consume(self, data: Mapping[str, Any]) -> None:
                if data["type"] == "timeout":
                    time.sleep(1.5)
                processed.append(data["type"])

        fake_client = FakeClient()

        def assert_timeout(should_timeout: bool, threaded: bool, disable_timeout: bool) -> None:
            processed.clear()
            for msg in ["good", "fine", "timeout", "back to normal"]:
                fake_client.enqueue("timeout_worker", {"type": msg})

            fn = os.path.join(settings.QUEUE_ERROR_DIR, "timeout_worker.errors")
            with suppress(FileNotFoundError):
                os.remove(fn)

            with simulated_queue_client(fake_client):
                worker = TimeoutWorker(threaded=threaded, disable_timeout=disable_timeout)
                worker.setup()
                if not should_timeout:
                    worker.start()
                else:
                    with self.assertLogs(level="ERROR") as m:
                        worker.start()
                        self.assertEqual(
                            m.records[0].message,
                            "Timed out in timeout_worker after 1 seconds processing 1 events",
                        )
                        self.assertIn(m.records[0].stack_info, m.output[0])

            if not should_timeout:
                self.assertEqual(processed, ["good", "fine", "timeout", "back to normal"])
                return

            self.assertEqual(processed, ["good", "fine", "back to normal"])
            with open(fn) as f:
                line = f.readline().strip()
            events = orjson.loads(line.split("\t")[1])
            self.assert_length(events, 1)
            event = events[0]
            self.assertEqual(event["type"], "timeout")

        # Do the bulky truth table check
        assert_timeout(should_timeout=False, threaded=True, disable_timeout=False)
        assert_timeout(should_timeout=False, threaded=True, disable_timeout=True)
        assert_timeout(should_timeout=True, threaded=False, disable_timeout=False)
        assert_timeout(should_timeout=False, threaded=False, disable_timeout=True)

    def test_embed_links_timeout(self) -> None:
        @base_worker.assign_queue("timeout_worker", is_test_queue=True)
        class TimeoutWorker(FetchLinksEmbedData):
            MAX_CONSUME_SECONDS = 1

            @override
            def consume(self, data: Mapping[str, Any]) -> None:
                # Send SIGALRM to ourselves to simulate a timeout.
                pid = os.getpid()
                os.kill(pid, signal.SIGALRM)

        fake_client = FakeClient()
        fake_client.enqueue(
            "timeout_worker",
            {
                "type": "timeout",
                "message_id": 15,
                "urls": ["first", "second"],
            },
        )

        with simulated_queue_client(fake_client):
            worker = TimeoutWorker()
            worker.setup()
            with self.assertLogs(level="WARNING") as m:
                worker.start()
                self.assertEqual(
                    m.records[0].message,
                    "Timed out in timeout_worker after 1 seconds while fetching URLs for message 15: ['first', 'second']",
                )

    def test_worker_noname(self) -> None:
        class TestWorker(base_worker.QueueProcessingWorker):
            def __init__(self) -> None:
                super().__init__()

            @override
            def consume(self, data: Mapping[str, Any]) -> None:
                pass  # nocoverage # this is intentionally not called

        with self.assertRaises(base_worker.WorkerDeclarationError):
            TestWorker()

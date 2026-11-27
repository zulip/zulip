import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest import mock

import orjson
from django.db import connection, connections, transaction
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.actions.message_send import SentMessageResult, check_send_message, do_send_messages
from zerver.lib.exceptions import AccessDeniedError, ServerNotReadyError
from zerver.lib.message import SendMessageRequest
from zerver.lib.test_classes import ZulipTransactionTestCase
from zerver.models import IdempotentRequest, Message, UserTopic
from zerver.models.clients import get_client
from zerver.models.realms import get_realm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

IDEMPOTENCY_KEY = "8e118d41-39d7-4a82-8da9-a6a3162d57eb"

POST_DATA = {
    "type": "channel",
    "to": orjson.dumps("Verona").decode(),
    "topic": "idempotency",
    "content": "idempotent message",
}


class IdempotencyKeyTransactionTest(ZulipTransactionTestCase):
    @override
    def tearDown(self) -> None:
        with transaction.atomic(durable=True):
            Message.objects.filter(realm=get_realm("zulip"), content="idempotent message").delete()
            UserTopic.objects.filter(topic_name="idempotency").delete()
            IdempotentRequest.objects.all().delete()
        super().tearDown()

    def count_messages(self) -> int:
        return Message.objects.filter(
            realm=get_realm("zulip"), content="idempotent message"
        ).count()

    def send_message(self, channel_name: str = "Verona") -> "TestHttpResponse":
        return self.api_post(
            self.example_user("hamlet"),
            "/api/v1/messages",
            {**POST_DATA, "to": orjson.dumps(channel_name).decode()},
            HTTP_IDEMPOTENCY_KEY=IDEMPOTENCY_KEY,
        )

    @contextmanager
    def first_request_in_progress(self) -> Iterator[list[SentMessageResult]]:
        """Starts a request in a thread, and yields once it holds its row's
        lock. The request finishes when the with block ends, adding its
        result to the yielded list.

        do_send_messages runs while the lock is held, so it's mocked to
        block until then. The test client can't be used from two threads
        at once, so the request skips the view.
        """
        first_request_holds_lock = threading.Event()
        with_block_exited = threading.Event()

        def hold_lock_until_with_block_exited(
            send_message_requests: Sequence[SendMessageRequest | None],
            *,
            mark_as_read: Sequence[int],
        ) -> list[SentMessageResult]:
            first_request_holds_lock.set()
            assert with_block_exited.wait(timeout=10)
            return do_send_messages(send_message_requests, mark_as_read=mark_as_read)

        hamlet = self.example_user("hamlet")
        first_results: list[SentMessageResult] = []

        def send_first_request() -> None:
            idempotent_request, _ = IdempotentRequest.objects.get_or_create(
                realm=hamlet.realm, user=hamlet, idempotency_key=IDEMPOTENCY_KEY
            )
            try:
                first_results.append(
                    check_send_message(
                        hamlet,
                        get_client("website"),
                        "stream",
                        ["Verona"],
                        "idempotency",
                        "idempotent message",
                        idempotent_request=idempotent_request,
                    )
                )
            finally:
                connections.close_all()

        first_request = threading.Thread(target=send_first_request)
        with mock.patch(
            "zerver.actions.message_send.do_send_messages",
            side_effect=hold_lock_until_with_block_exited,
        ):
            first_request.start()
            assert first_request_holds_lock.wait(timeout=10)
            try:
                yield first_results
            finally:
                with_block_exited.set()
                first_request.join(timeout=10)

    def wait_for_query_blocked_on_lock(self) -> None:
        with connection.cursor() as cursor:
            for _ in range(1000):
                cursor.execute(
                    """
                    SELECT 1 FROM pg_stat_activity
                    WHERE datname = current_database() AND wait_event_type = 'Lock'
                    """
                )
                if cursor.fetchone() is not None:
                    return
                time.sleep(0.01)
        raise AssertionError("No query waited for a lock")

    def test_concurrent_request_gets_conflict_error(self) -> None:
        """A duplicate gets a 409 while the first request holds the lock.
        A replay after the first request finishes gets its result.
        """
        with self.first_request_in_progress() as first_results:
            second_response = self.send_message()

        self.assert_json_error(
            second_response, "A request with this Idempotency-Key is already in progress", 409
        )
        self.assertEqual(second_response.json()["code"], "IDEMPOTENCY_KEY_IN_USE")
        replay_response = self.assert_json_success(self.send_message())
        self.assertEqual(replay_response["id"], first_results[0].message_id)
        self.assertEqual(self.count_messages(), 1)

    def test_failing_concurrent_request_waits_for_result(self) -> None:
        """A duplicate that fails validation while the first request holds
        the lock waits for the lock to save its error, and then gets the
        first request's result instead.
        """
        second_responses: list[TestHttpResponse] = []

        def send_failing_second_request() -> None:
            try:
                second_responses.append(self.send_message(channel_name="nonexistent"))
            finally:
                connections.close_all()

        second_request = threading.Thread(target=send_failing_second_request)
        with self.first_request_in_progress() as first_results:
            second_request.start()
            self.wait_for_query_blocked_on_lock()
        second_request.join(timeout=10)

        second_response = self.assert_json_success(second_responses[0])
        self.assertEqual(second_response["id"], first_results[0].message_id)
        self.assertEqual(self.count_messages(), 1)

    def test_failed_work_is_rolled_back_and_cached(self) -> None:
        """The mocked error stands in for a 4xx error raised while the row is
        locked, which nothing in do_send_messages raises today. It's cached
        after the message's transaction is rolled back.
        """
        with mock.patch(
            "zerver.actions.message_send.create_user_messages",
            side_effect=AccessDeniedError,
        ):
            self.assert_json_error(self.send_message(), "Access denied", 403)
        self.assertEqual(self.count_messages(), 0)

        self.assert_json_error(self.send_message(), "Access denied", 403)
        self.assertEqual(self.count_messages(), 0)

    def test_server_error_is_rolled_back_and_not_cached(self) -> None:
        with (
            mock.patch(
                "zerver.actions.message_send.create_user_messages",
                side_effect=ServerNotReadyError(_("Server not ready")),
            ),
            self.assertRaises(ServerNotReadyError),
            self.assertLogs("django.request", "ERROR"),
        ):
            self.send_message()
        self.assertEqual(self.count_messages(), 0)

        self.assert_json_success(self.send_message())
        self.assertEqual(self.count_messages(), 1)

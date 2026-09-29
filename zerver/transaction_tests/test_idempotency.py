import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING
from unittest import mock

import orjson
from django.db import connections, transaction
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.actions.message_send import SentMessageResult, check_send_message, do_send_messages
from zerver.lib.exceptions import JsonableError
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

    def send_message(self) -> "TestHttpResponse":
        return self.api_post(
            self.example_user("hamlet"),
            "/api/v1/messages",
            POST_DATA,
            HTTP_IDEMPOTENCY_KEY=IDEMPOTENCY_KEY,
        )

    def test_concurrent_request_gets_conflict_error(self) -> None:
        """A duplicate gets a 409 while the first request holds the lock.

        A replay after the first request finishes gets the first request's result.
        The first request runs in a thread, with do_send_messages mocked to
        block until the duplicate has been sent. Since do_send_messages runs
        while the lock is held, this keeps the lock held.
        """
        first_request_holds_lock = threading.Event()
        second_request_done = threading.Event()

        def hold_lock_until_second_request_done(
            send_message_requests: Sequence[SendMessageRequest | None],
            *,
            mark_as_read: Sequence[int],
        ) -> list[SentMessageResult]:
            first_request_holds_lock.set()
            assert second_request_done.wait(timeout=10)
            return do_send_messages(send_message_requests, mark_as_read=mark_as_read)

        hamlet = self.example_user("hamlet")
        first_results: list[SentMessageResult] = []

        # The test client isn't thread-safe, so this request skips the view.
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
            side_effect=hold_lock_until_second_request_done,
        ):
            first_request.start()
            assert first_request_holds_lock.wait(timeout=10)
            second_response = self.send_message()
            second_request_done.set()
            first_request.join(timeout=10)

        self.assert_json_error(
            second_response, "A request with this Idempotency-Key is already in progress", 409
        )
        replay_response = self.assert_json_success(self.send_message())
        self.assertEqual(replay_response["id"], first_results[0].message_id)
        self.assertEqual(self.count_messages(), 1)

    def test_failed_work_is_rolled_back_and_not_cached(self) -> None:
        with mock.patch(
            "zerver.actions.message_send.create_user_messages",
            side_effect=JsonableError(_("Work failed")),
        ):
            self.assert_json_error(self.send_message(), "Work failed")
        self.assertEqual(self.count_messages(), 0)
        self.assertIsNone(IdempotentRequest.objects.get().cached_result)

        self.assert_json_success(self.send_message())
        self.assertEqual(self.count_messages(), 1)

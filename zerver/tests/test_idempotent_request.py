import asyncio
from typing import TYPE_CHECKING, Any, cast
from unittest import mock

import orjson
from asgiref.sync import sync_to_async
from django.db import connections, transaction
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.message_send import build_message_send_dict, do_send_messages
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.exceptions import JsonableError
from zerver.lib.idempotent_request import json_error_deserializer
from zerver.lib.response import json_response_from_error
from zerver.lib.test_classes import ZulipTestCase, ZulipTransactionTestCase
from zerver.lib.test_helpers import make_client
from zerver.models import Message, UserProfile
from zerver.models.idempotent_requests import IdempotentRequest
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def get_cached_result_json(cached_result: dict[str, Any]) -> dict[str, Any]:
    return orjson.loads(json_response_from_error(json_error_deserializer(cached_result)).content)


class IdempotencyTest(ZulipTestCase):
    def test_invalid_idempotency_key(self) -> None:
        """
        Ensure server only accepts valid uuid for the Idempotency-key header.
        """

        self.login("hamlet")
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test message",
            "topic": "Test topic",
        }

        invalid_uuids = [
            "",
            "1",
            "8e118d41-39d7-4a82-8da9-a6a3162d57",
            "8e118d41-39d74a82-8da9-a6a3162d57",
        ]

        for invalid_uuid in invalid_uuids:
            # Do any POST request with invalid Idempotency-Key value.
            result = self.client_post(
                "/json/messages", post_data, headers={"Idempotency-Key": invalid_uuid}
            )
            # Invalid Idempotency-Key should be refused.
            self.assert_json_error(
                result, f"Invalid UUID in Idempotency-Key header: '{invalid_uuid}'".format(), 400
            )

    def test_message_idempotency(self) -> None:
        """
        Ensure message idempotency through Idempotency-Key.

        This simulates the issue of 'HTTP request replay' by sending duplicate POST requests.
        """
        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        # Change the default setting to enable automatic follow/unmute policy,
        # to ensure that it will also be included in the cached response as extra parameter.
        do_change_user_setting(
            sender,
            "automatically_follow_topics_policy",
            UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND,
            acting_user=None,
        )

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test message",
            "topic": "Test topic",
        }

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57eb"}

        first_response = None
        # Send 4 identical requests, all of which should succeed.
        for _ in range(4):
            result = self.client_post("/json/messages", post_data, headers=headers)
            content = self.assert_json_success(result)
            if first_response is None:
                first_response = content
            # All response should be identical, indicating duplicate requests are
            # cached (only once) successfully.
            self.assertEqual(first_response, content)

        # Only one idempotency row should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # ONLY a single message should be inserted i.e. idempotency.
        self.assert_length(Message.objects.filter(realm_id=realm.id, content="Test message"), 1)

        # Send without Idempotency-key
        result = self.client_post("/json/messages", post_data)
        content = self.assert_json_success(result)
        # No extra idempotency row should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # Another 2nd message should be inserted with a new ID.
        self.assert_length(Message.objects.filter(realm_id=realm.id, content="Test message"), 2)

        # Change Idempotency-key.
        headers["Idempotency-Key"] = "38eb6668-c46d-4380-bf78-10c66698ab82"
        # Send 2 identical requests with that new Idempotency-key.
        result_a = self.client_post("/json/messages", post_data, headers=headers)
        result_b = self.client_post("/json/messages", post_data, headers=headers)
        content_a = self.assert_json_success(result_a)
        content_b = self.assert_json_success(result_b)
        # Again, responses should be identical, indicating duplicate requests are
        # cached successfully.
        self.assertEqual(content_a, content_b)

        # Since we changed Idempotency-Key, Only another single idempotency row
        # is expected.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 2
        )
        # Only another 3rd message should be inserted.
        self.assert_length(Message.objects.filter(realm_id=realm.id, content="Test message"), 3)

    def test_invalid_request_idempotency(self) -> None:
        """
        Ensure idempotency when the request fails early during validation
        and before the actual work (e.g. do_send_messages) which is the most common case.

        Here we only ensure 2 things:
        1- We cache the response error, but  actually we never get to the work
        (e.g. do_send_messages) code which would deserialize and return it.
        2- A subsequent failing request's error (with the same idempotency key)
        should override that of first request.
        """

        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57eb"}

        # Prepare an invalid data to make the request fails.
        post_data = {
            "type": "channel",
            "to": "nonexistent_stream",  # invalid.
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "Channel 'nonexistent_stream' does not exist")

        idempotent_requests = IdempotentRequest.objects.filter(
            realm_id=realm.id, user_id=sender.id, completed=False, cached_result__isnull=False
        )
        # Only one idempotency row (with the expected values filtered above) should be created.
        self.assert_length(idempotent_requests, 1)

        # Ensure cached_result has the expected value,
        # i.e. can be deserialized back to the original error response.
        self.assertEqual(
            orjson.loads(result.content),
            get_cached_result_json(cast(dict[str, Any], idempotent_requests[0].cached_result)),
        )

        # Change the cause for the invalid request.
        post_data["to"] = orjson.dumps([99999]).decode()

        # Send another request with the same idempotency key, but this one
        # should return a different error response from the first request.
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "Channel with ID '99999' does not exist")

        idempotent_requests = IdempotentRequest.objects.filter(
            realm_id=realm.id, user_id=sender.id, completed=False, cached_result__isnull=False
        )
        # No more idempotency rows should be created.
        self.assert_length(idempotent_requests, 1)

        # Ensure that the second request's failed response overrides that of the first.
        self.assertEqual(
            orjson.loads(result.content),
            get_cached_result_json(cast(dict[str, Any], idempotent_requests[0].cached_result)),
        )

        # Since all requests failed, No messages should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, content=post_data["content"]), 0
        )

    def test_correct_idempotent_work_transaction(self) -> None:
        """
        In case of applying idempotency (i.e. idempotency_key is not None),
        @idempotent_work_transaction MUST only be called within the scope
        of @idempotent_endpoint.
        """
        realm = get_realm("zulip")
        sender = self.example_user("hamlet")
        stream = get_stream("Denmark", realm)
        recipient = stream.recipient
        assert recipient is not None

        message = Message(
            sender=sender,
            recipient=recipient,
            realm=realm,
            content="Message content",
            date_sent=timezone_now(),
            sending_client=make_client(name="test suite"),
        )
        message.set_topic_name("topic name")

        with self.assertRaisesMessage(
            AssertionError,
            "No matching row found for IdempotentRequest, make sure you are inside @idempotent_endpoint.",
        ):
            do_send_messages(
                [build_message_send_dict(message=message)],
                user=sender,
                idempotency_key="8e118d41-39d7-4a82-8da9-a6a3162d57eb",
            )


class TransactionIdempotencyTest(ZulipTransactionTestCase):
    @override
    def tearDown(self) -> None:
        # Clean up data created during this test, to prevent leakage.
        with transaction.atomic(durable=True):
            realm = get_realm("zulip")
            IdempotentRequest.objects.filter(realm=realm).delete()
            Message.objects.filter(realm=realm, content="Test Idempotency message").delete()
        super().tearDown()

    async def test_concurrency(self) -> None:
        """ "
        Ensure idempotency system works as expected during concurrent requests.
        """

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",  # Do not change this.
            "topic": "Test topic",
        }

        # UUID V4 Idempotency-Key.
        idempotency_key = "8e118d41-39d7-4a82-8da9-a6a3162d57eb"

        sender = await sync_to_async(lambda: self.example_user("hamlet"))()

        def send_message_request(idempotency_key: str) -> "TestHttpResponse":
            # Each thread has its own separate db connection,
            # so we must login each time.
            self.login("hamlet")
            result = self.client_post(
                "/json/messages", post_data, headers={"Idempotency-Key": idempotency_key}
            )
            # And we must explicitly close that thread's db connection
            # after we finish our work.
            connections.close_all()
            return result

        async def async_send_request(idempotency_key: str) -> "TestHttpResponse":
            result = await sync_to_async(
                lambda: send_message_request(idempotency_key), thread_sensitive=False
            )()
            return result

        # Prepare and send 5 concurrent requests with the same Idempotency-Key.
        results = await asyncio.gather(*[async_send_request(idempotency_key) for _ in range(5)])

        def check_result(result: "TestHttpResponse") -> int:
            # Asserts that the response must only be one of the following:
            # successful (200), conflict (409), or render error (400).
            # Note: The render error is not part of idempotency system, however,
            # sometimes the threads spawned by this test conflict
            # with the threads of the markdown rendering system,
            # initiated by zerver.lib.markdown.unsafe_timeout.
            try:
                self.assert_json_success(result)
                return 200

            except AssertionError:
                try:
                    self.assert_json_error(
                        result,
                        "A request with the same Idempotency-Key is currently being processed; retry to observe its result.",
                        409,
                    )
                    return 409
                except AssertionError:  # nocoverage
                    self.assert_json_error(result, "Unable to render message")
                    return 400

        # During true concurrency, it's hard to predict
        # how many requests succeeded or aborted.
        # But we know that at least one request must succeed.
        # And with 5 concurrent requests, at least one must abort,
        # in practice usually 3-4 requests abort, but that's not guaranteed.

        result_status_codes = {check_result(result) for result in results}

        # At least one request succeeded (200).
        self.assertTrue(200 in result_status_codes)

        # At least one request aborted due to row-lock (409).
        self.assertTrue(409 in result_status_codes)

        # Only one idempotency row should be created.
        await sync_to_async(
            lambda: self.assert_length(
                IdempotentRequest.objects.filter(realm_id=sender.realm_id, user_id=sender.id), 1
            )
        )()

        # Only one message should be created.
        await sync_to_async(
            lambda: self.assert_length(
                Message.objects.filter(realm_id=sender.realm_id, content=post_data["content"]),
                1,
            )
        )()

        # Send 2 concurrent requests with 2 different idempotency keys
        # to ensure the two requests don't interfere with each other
        # during concurrency.
        tasks = [
            async_send_request("8e118d41-39d7-4a82-8da9-a6a3162d57e0"),
            async_send_request("8e118d41-39d7-4a82-8da9-a6a3162d57e1"),
        ]
        results = await asyncio.gather(*tasks)

        for result in results:
            # Since each request has a different Idempotency-Key,
            # each request should succeed as it's independent.
            self.assert_json_success(result)

        # Only another 2 idempotency rows should be created.
        await sync_to_async(
            lambda: self.assert_length(
                IdempotentRequest.objects.filter(realm_id=sender.realm_id, user_id=sender.id), 3
            )
        )()

        # Only another 2 messages should be created.
        await sync_to_async(
            lambda: self.assert_length(
                Message.objects.filter(realm_id=sender.realm_id, content=post_data["content"]),
                3,
            )
        )()

    def test_work_failure_idempotency(self) -> None:
        """
        Ensure idempotency when the core work fails.
        This ensures we cache the response error and returns it for subsequent requests
        with the same Idempotency-Key.

        Note: This test should only be inside ZulipTransactionTestCase because the mock behavior below
        raises an exception that breaks the transaction created by ZulipTestCase
        and raises TransactionManagementError.
        """
        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57eb"}

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",  # Do not change this.
            "topic": "Test topic",
        }

        # Here we make the core work fail, by mocking create_user_messages
        # a function inside (do_send_message).
        with mock.patch(
            "zerver.actions.message_send.create_user_messages",
            side_effect=JsonableError("Error while doing the work."),
        ) as do_work_mock:
            first_failed_req_result = self.client_post("/json/messages", post_data, headers=headers)
            self.assert_json_error(first_failed_req_result, "Error while doing the work.")

            idempotent_requests = IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, completed=False, cached_result__isnull=False
            )
            # Only one idempotency row (with the expected values filtered above) should be created.
            self.assert_length(idempotent_requests, 1)

            first_cached_result_json = get_cached_result_json(
                cast(dict[str, Any], idempotent_requests[0].cached_result)
            )

            # Ensure cached_result has the expected value,
            # i.e. can be deserialized back to the original error response.
            self.assertEqual(
                orjson.loads(first_failed_req_result.content), first_cached_result_json
            )

            second_failed_req_result = self.client_post(
                "/json/messages", post_data, headers=headers
            )
            self.assert_json_error(second_failed_req_result, "Error while doing the work.")

            idempotent_requests = IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, completed=False, cached_result__isnull=False
            )
            # No more idempotency rows should be created.
            self.assert_length(idempotent_requests, 1)

            # Check that cached_result didn't change, since the 2 requests have the same error.
            self.assertEqual(
                first_cached_result_json,
                get_cached_result_json(cast(dict[str, Any], idempotent_requests[0].cached_result)),
            )
            self.assertEqual(
                self.get_json_error(first_failed_req_result),
                self.get_json_error(second_failed_req_result),
            )

            # Important: Ensure the work was only done once (by 1st request),
            # so we don't redo the work.
            do_work_mock.assert_called_once()

        # Since all requests failed, No messages should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, content=post_data["content"]), 0
        )

import asyncio
from typing import TYPE_CHECKING, Any, cast

import orjson
from asgiref.sync import sync_to_async
from django.db import connections, transaction
from typing_extensions import override

from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.idempotent_request import json_error_deserializer
from zerver.lib.response import json_response_from_error
from zerver.lib.test_classes import ZulipTestCase, ZulipTransactionTestCase
from zerver.models import Message, UserProfile
from zerver.models.idempotent_requests import IdempotentRequest
from zerver.models.realms import get_realm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class IdempotentRequestTest(ZulipTestCase):
    def test_invalid_idempotency_key(self) -> None:
        """
        Ensure server only accepts valid uuid for the Idempotency-key header.
        """
        # TODO: We can also invalidate non-v4 if needed.

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

    def test_failed_message_idempotency(self) -> None:
        """
        Ensure correct caching of json_error in case of idempotent requests.
        """

        def get_cached_result_json_content(cached_result: dict[str, Any]) -> dict[str, Any]:
            return orjson.loads(
                json_response_from_error(json_error_deserializer(cached_result)).content
            )

        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")
        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57eb"}

        post_data = {
            "type": "channel",
            "to": "nonexistent_stream",  # this makes it an invalid request,
            "content": "Test message",
            "topic": "Test topic",
        }

        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "Channel 'nonexistent_stream' does not exist")

        idempotent_requests = IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id)

        # Only one idempotency row should be created.
        self.assert_length(idempotent_requests, 1)

        # Ensure we mark the row as NOT completed.
        self.assertEqual(idempotent_requests[0].completed, False)

        # Ensure cached_result is the expected type and not None.
        self.assertIsInstance(idempotent_requests[0].cached_result, dict)

        # Ensure cached_result has the expected value,
        # i.e. can deserialized back to the original json error response.
        self.assertEqual(
            orjson.loads(result.content),
            get_cached_result_json_content(
                cast(dict[str, Any], idempotent_requests[0].cached_result)
            ),
        )

        # Send another invalid request but with a different error cause.
        post_data["to"] = orjson.dumps([99999]).decode()
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "Channel with ID '99999' does not exist")

        idempotent_requests = IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id)

        # Ensure idempotency rows are still only one.
        self.assert_length(idempotent_requests, 1)

        # Ensure we mark the row as NOT completed.
        self.assertEqual(idempotent_requests[0].completed, False)

        # Ensure cached_result is the expected type and not None.
        self.assertIsInstance(idempotent_requests[0].cached_result, dict)

        # Ensure cached_result has the expected value,
        # i.e. can be deserialized back to the original json error response.
        # And is updated with the new json_error.
        self.assertEqual(
            orjson.loads(result.content),
            get_cached_result_json_content(
                cast(dict[str, Any], idempotent_requests[0].cached_result)
            ),
        )

        # No messages should be created.
        self.assert_length(Message.objects.filter(realm_id=realm.id, content="Test message"), 0)


class ConcurrentIdempotentRequestTest(ZulipTransactionTestCase):
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
            "content": "Test Idempotency message",
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

        # Prepare and send 6 concurrent requests with the same Idempotency-Key.
        tasks = [async_send_request(idempotency_key) for _ in range(6)]
        results = await asyncio.gather(*tasks)

        def check_result(result: "TestHttpResponse") -> int:
            # helper function, returns  the status code of the response.
            # and raises AssertionError in case of unexpected error.
            try:
                self.assert_json_success(result)
                return 200

            except AssertionError:
                pass

            try:
                self.assert_json_error(
                    result,
                    "A request with the same Idempotency-Key is currently being processed; retry to observe its result.",
                    409,
                )
                return 409

            except AssertionError as un_expected_error:  # nocoverage
                raise un_expected_error

        # During true concurrency, it's hard to predict
        # how many requests were successful or aborted.
        # But we know that at least one request must succeed.
        # And with 6 concurrent requests, at least one must abort,
        # in practice usually 4-5 requests abort, but that's not guaranteed.

        # At least one request succeeded (200).
        self.assertTrue(any(check_result(result) == 200 for result in results))

        # At least one request aborted with the expected 409 error.
        self.assertTrue(any(check_result(result) == 409 for result in results))

        # Important check, ensure all requests either succeeded (200) or
        # aborted (409) due to row-lock, not other failures.
        for result in results:
            # no need to capture result as it will raise if the result is not as expected.
            check_result(result)

        # Only one idempotency row should be created.
        await sync_to_async(
            lambda: self.assert_length(
                IdempotentRequest.objects.filter(realm_id=sender.realm_id, user_id=sender.id), 1
            )
        )()

        # Only one message should be created.
        await sync_to_async(
            lambda: self.assert_length(
                Message.objects.filter(
                    realm_id=sender.realm_id, content="Test Idempotency message"
                ),
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
                Message.objects.filter(
                    realm_id=sender.realm_id, content="Test Idempotency message"
                ),
                3,
            )
        )()

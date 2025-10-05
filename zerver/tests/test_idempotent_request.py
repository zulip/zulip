import asyncio
from typing import TYPE_CHECKING, Any, cast
from unittest import mock

import orjson
from asgiref.sync import sync_to_async
from django.db import connections
from django.utils.timezone import now as timezone_now

from zerver.actions.message_send import build_message_send_dict, do_send_messages
from zerver.actions.streams import do_change_stream_group_based_setting
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.exceptions import JsonableError
from zerver.lib.idempotent_request import json_error_deserializer
from zerver.lib.per_request_cache import flush_per_request_caches
from zerver.lib.response import json_response_from_error
from zerver.lib.test_classes import ZulipTestCase, ZulipTransactionTestCase
from zerver.lib.test_helpers import make_client, queries_captured
from zerver.models import Message, NamedUserGroup, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.idempotent_requests import IdempotentRequest
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def get_cached_result_json(cached_result: dict[str, Any]) -> dict[str, Any]:
    return orjson.loads(json_response_from_error(json_error_deserializer(cached_result)).content)


class IdempotencyTest(ZulipTestCase):
    """Tests here ensure idempotency of the work using Idempotency-Key header.

    We simulate the issue of 'HTTP request replay'
    by sending duplicate POST (non-idempotent) requests.

    We test different cases like:
    1- Successful requests.
    2- Failed requests.
    3- A successful request that failed to reach the client.
    4- Failed then succeeded request.
    5- Server error before and after doing the work.
    """

    def test_invalid_idempotency_key(self) -> None:
        """
        Ensure server only accepts valid uuid for the Idempotency-key header.
        """
        self.login("hamlet")
        sender = self.example_user("hamlet")
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test message",
            "topic": "Test topic",
        }
        invalid_uuids = [
            "",
            "1",
            "abcd",
            "ze118d41-39d7-4a82-8da9-a6a3162d57eb",
            "8e118d41-39d7-4a82-8da9-a6a3162d57",
            "8e118d41-39d74a82-8da9-a6a3162d57",
            "8e1841-39d7a82-8da9-a6a3162d57",
        ]

        # POST requests using those invalid keys.
        for invalid_uuid in invalid_uuids:
            result = self.client_post(
                "/json/messages", post_data, headers={"Idempotency-Key": invalid_uuid}
            )
            # Invalid uuid in Idempotency-Key header should be refused.
            self.assert_json_error(
                result, f"Invalid UUID in Idempotency-Key header: '{invalid_uuid}'".format(), 400
            )

        # Since all requests were refused, no data should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=sender.realm_id, user_id=sender.id), 0
        )
        self.assert_length(
            Message.objects.filter(realm_id=sender.realm_id, content="Test message"), 0
        )

    def test_successful_request(self) -> None:
        """
        Ensure work idempotency in case of duplicate successful requests,
        which is the most common case.

        Currently testing only sending a message, i.e. POST to /json/messages
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

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57eb"}

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test message",
            "topic": "Test topic 1",
        }

        # Send a request without the Idempotency-Key header to:
        # 1- Ensure requests succeed without the key, since
        # it's not mandatory.
        # 2- Capture the number of queries executed without any
        # feature of this idempotency system included.
        with queries_captured() as queries:
            result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)
        base_query_count = len(queries)

        # We will only consider messages with this content.
        post_data["content"] = "Test Idempotency message"

        # Change topic so the query count is consistent;
        # query count increases when sending the 1st message to a topic.
        post_data["topic"] = "Test topic 2"

        first_response = None
        # Start applying idempotency, sending 4 identical requests
        # with the same key.
        for i in range(4):
            if i == 0:
                # First succeeded request, we expect 3 extra queries:
                # 1 to insert the initial row +
                # 1 to fetch cached_result and lock the row +
                # 1 to mark the work as succeeded and cache its result.
                expected_query_count = base_query_count + 3
            else:
                # Duplicate succeeded request has lower query count
                # since the core work (e.g. do_send_messages) is avoided.
                # expected_query_count in this case includes the first 2 queries
                # from the previous case.
                expected_query_count = 12
                assert expected_query_count < base_query_count

            flush_per_request_caches()
            with self.assert_database_query_count(expected_query_count):
                result = self.client_post("/json/messages", post_data, headers=headers)

            content = self.assert_json_success(result)
            first_response = content if first_response is None else first_response

            # All responses should be identical, indicating duplicate requests are
            # cached successfully.
            self.assertEqual(first_response, content)

        # Only one idempotency row should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # That one row should be succeeded and has the cached_result.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=True, cached_result__isnull=False
            ),
            1,
        )
        # Ensure idempotency: only 1 message should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, content=post_data["content"]), 1
        )

        post_data["topic"] = "Test topic 3"
        # Change Idempotency-key.
        headers["Idempotency-Key"] = "38eb6668-c46d-4380-bf78-10c66698ab82"
        # Send 2 identical requests with that new Idempotency-key, while making
        # sure the query count is still consistent.
        with self.assert_database_query_count(base_query_count + 3):
            # First succeeded request.
            result_a = self.client_post("/json/messages", post_data, headers=headers)
        with self.assert_database_query_count(12):
            # Duplicate succeeded request.
            result_b = self.client_post("/json/messages", post_data, headers=headers)

        # Again, responses should be identical, indicating duplicate requests are
        # cached successfully.
        self.assertEqual(self.assert_json_success(result_a), self.assert_json_success(result_b))

        # Since we changed Idempotency-Key, only another idempotency row
        # is expected.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 2
        )
        # That one extra row should be succeeded and has the cached_result
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=True, cached_result__isnull=False
            ),
            2,
        )
        # Ensure idempotency: only a 2nd message should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, content=post_data["content"]), 2
        )

    def test_early_failed_request(self) -> None:
        """
        Ensure idempotency when the request fails early during validation
        and before the actual work is attempted.

        Note: this is the most common case for validation failures when sending
        a message.

        Here we ensure 2 things:
        1- We cache the response error, but actually we never get to the work
        (e.g. do_send_messages) code which would deserialize and return it.
        2- A subsequent failing request's error (with the same idempotency key)
        should override that of first request.
        """

        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        # Prepare an invalid data to make the request fails.
        post_data = {
            "type": "channel",
            "to": "nonexistent_stream",  # invalid.
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        # Send a request without the Idempotency-Key header to:
        # 1- Ensure requests fail as expected without the key, since
        # it's not mandatory.
        # 2- Capture the number of queries executed without any
        # feature of this idempotency system included.
        with queries_captured() as base_query_count:
            result = self.client_post("/json/messages", post_data)
        self.assert_json_error(result, "Channel 'nonexistent_stream' does not exist")

        # For early failures, we expect only 2 extra queries, executed
        # by idempotent_endpoint code.
        with self.assert_database_query_count(len(base_query_count) + 2):
            result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "Channel 'nonexistent_stream' does not exist")

        # Only one idempotency row should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # That one row should not be succeeded, and has the cached_result
        idempotent_rows = IdempotentRequest.objects.filter(
            realm_id=realm.id, user_id=sender.id, succeeded=False, cached_result__isnull=False
        )
        self.assert_length(idempotent_rows, 1)

        # Ensure cached_result has the expected value,
        # i.e. can be deserialized back to the original error response.
        self.assertEqual(
            orjson.loads(result.content),
            get_cached_result_json(cast(dict[str, Any], idempotent_rows[0].cached_result)),
        )

        # Change the cause for the invalid request.
        post_data["to"] = orjson.dumps([99999]).decode()

        # Send another request with the same idempotency key, but this one
        # should return a different error response from the first request.
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "Channel with ID '99999' does not exist")

        idempotent_rows = IdempotentRequest.objects.filter(
            realm_id=realm.id, user_id=sender.id, succeeded=False, cached_result__isnull=False
        )
        # No more idempotency rows should be created.
        self.assert_length(idempotent_rows, 1)

        # Ensure the second request's failed response overrides that of the first.
        self.assertEqual(
            orjson.loads(result.content),
            get_cached_result_json(cast(dict[str, Any], idempotent_rows[0].cached_result)),
        )

        # Since all requests failed, No messages should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, content=post_data["content"]), 0
        )

    def test_different_requests_with_same_key(self) -> None:
        """
        Test behaviour when a confused client reuses the same Idempotency-Key for a different request.

        TODO: Ideally, in future, we should detect this behaviour by comparing the parameters for both requests,
        and if they differ, we return an error telling the user that they should change the key.
        """
        realm = get_realm("zulip")
        sender = self.example_user("hamlet")
        self.login("hamlet")

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "message sent to Verona",
            "topic": "Test topic",
        }

        result = self.client_post("/json/messages", post_data, headers=headers)
        first_response_dict = self.assert_json_success(result)

        # Change post_data, making it a different request.
        post_data["to"] = orjson.dumps("Denmark").decode()
        post_data["content"] = "message sent to Denmark"

        # Send a different request with the same key.
        result = self.client_post("/json/messages", post_data, headers=headers)
        second_response_dict = self.assert_json_success(result)

        # Although the two requests differ, they have the exact same response, as a result of
        # mistakenly using the same key.
        self.assertEqual(first_response_dict, second_response_dict)

        # Ensure idempotency: only one message, belonging to the first request, is created.
        self.assert_length(
            Message.objects.filter(
                realm_id=realm.id, sender=sender, content="message sent to Verona"
            ),
            1,
        )

    def test_correct_idempotent_work(self) -> None:
        """
        @idempotent_endpoint is the scope that applies idempotency to functions decorated with
        @idempotent_work. However, those functions are still expected to be called,
        in other non-idempotent contexts like tests, outside that scope. So we just document
        that here.
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

        # Call @idempotent_work decorated function directly.
        do_send_messages([build_message_send_dict(message=message)], acting_user=sender)

        # No idempotency rows should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 0
        )


class TransactionIdempotencyTest(ZulipTransactionTestCase):
    """Tests inside this class raise expected errors that can prevent
    the test from continuing and throw TransactionManagementError,
    so we put them inside ZulipTransactionTestCase to prevent this.
    """

    async def test_concurrency(self) -> None:
        """
        Ensure idempotency system works as expected during concurrent requests.
        """
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

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

        # UUID V4 Idempotency-Key.
        idempotency_key = "8e118d41-39d7-4a82-8da9-a6a3162d57eb"
        # Send 5 concurrent requests with the same Idempotency-Key.
        results = await asyncio.gather(*[async_send_request(idempotency_key) for _ in range(5)])

        def get_expected_status_code(result: "TestHttpResponse") -> int:
            """
            Asserts that the response must be either
            successful(200) or conflict(409)
            """
            try:
                self.assert_json_success(result)
                return 200

            except AssertionError:
                self.assert_json_error(
                    result,
                    "A request with the same Idempotency-Key is currently being processed; retry to observe its result.",
                    409,
                )
                return 409

        result_status_codes = {get_expected_status_code(result) for result in results}

        # During true concurrency, it's hard to predict
        # how many requests succeeded or aborted.
        # But we know that at least one request must succeed.
        # And with 5 concurrent requests, at least one must abort,
        # in practice usually 3-4 requests abort, but that's not guaranteed.

        # At least one request succeeded (200).
        self.assertTrue(200 in result_status_codes)

        # At least one request aborted due to row-lock (409).
        self.assertTrue(409 in result_status_codes)

        # Only one idempotency row should be created.
        await sync_to_async(
            lambda: self.assert_length(
                IdempotentRequest.objects.filter(
                    realm_id=sender.realm_id, user_id=sender.id, idempotency_key=idempotency_key
                ),
                1,
            )
        )()

        # Ensure idempotency: only one message should be created.
        await sync_to_async(
            lambda: self.assert_length(
                Message.objects.filter(realm_id=sender.realm_id, content=post_data["content"]),
                1,
            )
        )()

        request_keys: list[str] = [
            "8e118d41-39d7-4a82-8da9-a6a3162d57e0",
            "8e118d41-39d7-4a82-8da9-a6a3162d57e1",
            "8e118d41-39d7-4a82-8da9-a6a3162d57e2",
            "8e118d41-39d7-4a82-8da9-a6a3162d57e3",
            "8e118d41-39d7-4a82-8da9-a6a3162d57e4",
        ]
        # Send 5 concurrent requests with different keys, to ensure
        # requests don't interfere with each other during concurrency.
        tasks = [async_send_request(key) for key in request_keys]
        results = await asyncio.gather(*tasks)

        # Since each request has a different key,
        # each request should succeed, as it's independent.
        for result in results:
            self.assert_json_success(result)

        idempotent_rows = await sync_to_async(
            lambda: set(
                IdempotentRequest.objects.filter(realm_id=sender.realm_id, user_id=sender.id)
            )
        )()
        # Since we are using concrete values in request_keys, we should be explicit
        # about which key values are expected to be created.
        created_keys = [str(row.idempotency_key) for row in idempotent_rows]
        for key in request_keys:
            self.assertTrue(key in created_keys)

        # Only another 5 idempotency rows should be created.
        self.assert_length(idempotent_rows, 6)

        # Ensure idempotency: only another 6 messages should be created.
        await sync_to_async(
            lambda: self.assert_length(
                Message.objects.filter(realm_id=sender.realm_id, content=post_data["content"]),
                6,
            )
        )()

    def test_work_failure(self) -> None:
        """
        Ensure idempotency when the core work fails.
        This ensures we cache the response error and returns it for subsequent requests
        having the same Idempotency-Key.
        """
        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57eb"}

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        # The following 2 mocks are the same, they
        # make the core work fail, by mocking a function
        # inside the core work (e.g. do_send_message).
        # In the first mock we send a request without
        # the Idempotency-Key header to:
        # 1- Ensure requests fail as expected without the key, since
        # it's not mandatory.
        # 2- Capture the number of queries executed without any
        # feature of this idempotency system included.
        with mock.patch(
            "zerver.actions.message_send.create_user_messages",
            side_effect=JsonableError("Error while doing the work."),
        ) as do_work_mock:
            with queries_captured() as base_query_count:
                result = self.client_post("/json/messages", post_data)
            self.assert_json_error(result, "Error while doing the work.")

        with mock.patch(
            "zerver.actions.message_send.create_user_messages",
            side_effect=JsonableError("Error while doing the work."),
        ) as do_work_mock:
            # For work failure, we expect 3 extra queries:
            # 1 to insert the initial row +
            # 1 to fetch cached_result and lock the row +
            # 1 (if it's non-transient 4xx error)to cache the error.
            with self.assert_database_query_count(len(base_query_count) + 3):
                first_result = self.client_post("/json/messages", post_data, headers=headers)
            self.assert_json_error(first_result, "Error while doing the work.")

            # Only one idempotency row should be created.
            self.assert_length(
                IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
            )
            # That one row should NOT be succeeded, and has the cached_result.
            idempotent_rows = IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=False, cached_result__isnull=False
            )
            self.assert_length(idempotent_rows, 1)

            # Ensure cached_result has the expected value,
            # i.e. can be deserialized back to the original error response.
            first_cached_result_json = get_cached_result_json(
                cast(dict[str, Any], idempotent_rows[0].cached_result)
            )
            self.assertEqual(orjson.loads(first_result.content), first_cached_result_json)

            second_result = self.client_post("/json/messages", post_data, headers=headers)
            self.assert_json_error(second_result, "Error while doing the work.")

            idempotent_rows = IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=False, cached_result__isnull=False
            )
            # No more idempotency rows should be created.
            self.assert_length(idempotent_rows, 1)

            # Check that cached_result didn't change, since the 2 requests have the same error.
            self.assertEqual(
                first_cached_result_json,
                get_cached_result_json(cast(dict[str, Any], idempotent_rows[0].cached_result)),
            )
            self.assertEqual(
                self.get_json_error(first_result),
                self.get_json_error(second_result),
            )

            # Important: ensure work was attempted ONLY once (by 1st request).
            do_work_mock.assert_called_once()

        # Since all requests failed, no work should be done.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, content=post_data["content"]), 0
        )

    def test_request_validation_changes(self) -> None:
        """
        Test behaviour when server's validation for the same request changes;
        a request initially fails validation but passes it on retry.
        """
        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)
        sender = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")
        self.login("hamlet")

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        post_data = {
            "type": "channel",
            "to": orjson.dumps(stream.name).decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm_for_sharding=realm, is_system_group=True
        )

        # Save the default permission (for sending a message to that stream),
        # before changing it.
        default_can_send_message_group = stream.can_send_message_group.named_user_group

        # Now, only owners are allowed to send messages to the stream.
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", owners_group, acting_user=desdemona
        )

        # Client doesn't have the permission to post to this stream.
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "You do not have permission to post in this channel.")
        # Ensure we cache the failed result.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=False, cached_result__isnull=False
            ),
            1,
        )

        # Change can_send_message_group back to its default so the client regains the
        # permission to send.
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", default_can_send_message_group, acting_user=desdemona
        )

        # Although client regained the permission to send (i.e. the new server validation),
        # they still get the cached result of the previous request because the client is
        # using the same key.
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "You do not have permission to post in this channel.")
        # Idempotency row should not change.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=False, cached_result__isnull=False
            ),
            1,
        )
        # No work is done, as a result of using the same key.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            0,
        )

        # Resend the request with a different key.
        # This is the favorable client behaviour in this case,
        # and as a result the client gets the result of the new server validation,
        # i.e. the permission to post.
        headers["Idempotency-Key"] = "8e118d41-39d7-4a82-8da9-a6a3162d57e1"
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_success(result)
        # Now, idempotency row should be updated to reflect the succeeded work,
        # and to cache the successful result.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=True, cached_result__isnull=False
            ),
            1,
        )
        # Now, work is done.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            1,
        )

    def test_server_failure_before_completing_work(self) -> None:
        """
        Test the case where the server fails (5xx transient error) before starting/completing the work.
        """
        realm = get_realm("zulip")
        sender = self.example_user("hamlet")
        self.login("hamlet")

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        # Make the server fails before attempting to do the work.
        with (
            mock.patch(
                "zerver.actions.message_send.do_send_messages",
                side_effect=AssertionError("Some server failure before completing the work."),
            ),
            self.assertLogs(level="ERROR"),
            self.assertRaisesMessage(
                AssertionError, "Some server failure before completing the work."
            ),
        ):
            self.client_post("/json/messages", post_data, headers=headers)

        # We don't cache transient errors (e.g. 5xx server), so
        # we should expect both cached_result and succeeded to be None,
        # representing a not-yet-attempted work or a transient error occurring
        # before starting/completing the work (this case).
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id,
                user_id=sender.id,
                succeeded__isnull=True,
                cached_result__isnull=True,
            ),
            1,
        )
        # Ensure work is NOT done.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            0,
        )

        # Since request failed, we retry the same request to observe its result.
        # In this special case, sending the same or a different key would have no effect
        # on idempotency; the work was not attempted anyway.
        # However, the client doesn't know that and should ideally
        # retry with the same key, in case the work was actually done and succeeded/failed.
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_success(result)
        # Expect one idemotency row.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # That one row should be succeeded and has the cached_result.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id,
                user_id=sender.id,
                succeeded=True,
                cached_result__isnull=False,
            ),
            1,
        )
        # Ensure work is done.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            1,
        )

    def test_server_failure_after_successful_work(self) -> None:
        """
        Test a special case where the request is processed and cached successfully
        by the server, but failed (because of an unexpected server error) to reach the client.
        """
        realm = get_realm("zulip")
        sender = self.example_user("hamlet")
        self.login("hamlet")

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        def do_work_then_fail(*args: Any, **kwargs: Any) -> None:
            do_send_messages(*args, **kwargs)
            raise AssertionError("Some server failure after doing the work.")

        # Make the server fails after successfully doing the work.
        with (
            mock.patch(
                "zerver.actions.message_send.do_send_messages", side_effect=do_work_then_fail
            ),
            self.assertLogs(level="ERROR"),
            self.assertRaisesMessage(AssertionError, "Some server failure after doing the work."),
        ):
            self.client_post("/json/messages", post_data, headers=headers)

        # Ensure result is cached successfully.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=True, cached_result__isnull=False
            ),
            1,
        )
        # Ensure work is done.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            1,
        )

        # Ideally, the client should retry the request with the same key
        # to get the result of the previously unreceived successful response.
        # Actually, Zulip web app retries the request using the same key in case of a server error (5xx).
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_success(result)

        # Ensure idempotency: no more messages should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            1,
        )

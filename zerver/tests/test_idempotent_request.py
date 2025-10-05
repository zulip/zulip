import asyncio
import json
import threading
from typing import TYPE_CHECKING, Any, cast
from unittest import mock
from urllib.parse import urlencode

import orjson
from asgiref.sync import sync_to_async
from django.db import connections, transaction
from django.http import HttpRequest
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy
from typing_extensions import override

from zerver.actions.message_send import (
    build_message_send_dict,
    create_user_messages,
    do_send_messages,
)
from zerver.actions.streams import do_change_stream_group_based_setting
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.exceptions import (
    CannotDeactivateLastUserError,
    DirectMessagePermissionError,
    IncompatibleParametersError,
    JsonableError,
    RateLimitedError,
    StreamWithIDDoesNotExistError,
    UnauthorizedError,
)
from zerver.lib.idempotent_request import json_error_deserializer, json_error_serializer
from zerver.lib.initial_password import initial_password
from zerver.lib.response import json_response_from_error
from zerver.lib.test_classes import (
    ZulipTestCase,
    ZulipTestClient,
    ZulipTransactionTestCase,
    get_row_pks_in_all_tables,
)
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

    We also test different cases when the client retries failed requests.
    """

    def test_invalid_idempotency_key(self) -> None:
        """
        Ensure the server only accepts a valid UUID for the Idempotency-Key header.
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
                result, f"Invalid UUID in Idempotency-Key header: '{invalid_uuid}'", 400
            )

        # Since all requests were refused, no data should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=sender.realm_id, user_id=sender.id), 0
        )
        self.assert_length(
            Message.objects.filter(realm_id=sender.realm_id, content="Test message"), 0
        )

    def test_duplicate_direct_message(self) -> None:
        """
        Idempotency is already recipient-type-agnostic; all cases are covered
        for stream messages, so here we only confirm the DM
        send path also flows through the idempotency system.
        """

        self.login("hamlet")
        sender = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57ff"}

        post_data = {
            "type": "direct",
            "to": orjson.dumps([cordelia.id]).decode(),
            "content": "Idempotent DM",
        }

        first = self.assert_json_success(
            self.client_post("/json/messages", post_data, headers=headers)
        )
        second = self.assert_json_success(
            self.client_post("/json/messages", post_data, headers=headers)
        )
        self.assertEqual(first, second)

        self.assertEqual(IdempotentRequest.objects.count(), 1)

        # Ensure idempotency: only one message should be created.
        self.assert_length(
            Message.objects.filter(
                realm_id=sender.realm_id, sender=sender, content=post_data["content"]
            ),
            1,
        )

    def test_successful_request(self) -> None:
        """
        Ensure work idempotency in case of duplicate successful requests,
        which is the most common case.

        Currently, idempotency is only applied to sending a message,
        i.e., POST to /json/messages
        """
        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        # Change the default setting to enable automatic follow/unmute policy,
        # to ensure that it will also be included in the cached response as an extra parameter.
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
        with queries_captured() as base_queries:
            result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)
        base_query_count = len(base_queries)

        # We will only consider messages with this content.
        post_data["content"] = "Test Idempotency message"

        # Change topic so the query count is consistent;
        # query count increases when sending the 1st message to a topic.
        post_data["topic"] = "Test topic 2"

        successful_responses: list[dict[str, Any]] = []
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
                expected_query_count = 13
                assert expected_query_count < base_query_count

            with self.assert_database_query_count(expected_query_count):
                result = self.client_post("/json/messages", post_data, headers=headers)
            successful_responses.append(self.assert_json_success(result))

        # All responses should be identical, indicating duplicate requests are
        # cached successfully.
        self.assertTrue(
            all(response == successful_responses[0] for response in successful_responses)
        )

        # Only one idempotency row should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # That one row should have succeeded and have a cached_result.
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
        # Change Idempotency-Key.
        headers["Idempotency-Key"] = "38eb6668-c46d-4380-bf78-10c66698ab82"

        # Send 2 identical requests with that new Idempotency-Key, while making
        # sure the query count is still consistent.
        with self.assert_database_query_count(base_query_count + 3):
            # First succeeded request.
            result_a = self.client_post("/json/messages", post_data, headers=headers)

        with self.assert_database_query_count(13):
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
        # That one extra row should have succeeded and have the cached_result.
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

    def test_early_failure(self) -> None:
        """
        Ensure idempotency when the request fails early during validation
        and before the actual work is attempted.

        Note: this is the most common case for validation failures when sending
        a message.

        Here we ensure 3 things:
        1- We cache the response error correctly, but actually we never get to the work
        (e.g., do_send_messages) path which would deserialize and return it.
        2- A subsequent failing request's error (with the same idempotency key)
        should override that of the previous one.
        3- A lazy error message is processed and cached correctly.
        """
        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        # Prepare invalid data to make the request fail.
        post_data = {
            "type": "channel",
            "to": "nonexistent_stream",  # invalid.
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        # Send a request without the Idempotency-Key header to:
        # 1- Ensure requests fail as expected without the key, since it's not mandatory.
        # 2- Capture the number of queries executed without any
        # feature of this idempotency system included.
        with queries_captured() as base_queries:
            result = self.client_post("/json/messages", post_data)
        self.assert_json_error(result, "Channel 'nonexistent_stream' does not exist")

        # For early failures, we expect only 2 extra queries, executed
        # by @idempotent_endpoint.
        with self.assert_database_query_count(len(base_queries) + 2):
            result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_error(result, "Channel 'nonexistent_stream' does not exist")

        # Only one idempotency row should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # That one row should NOT have succeeded and should have the cached_result.
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

        # Send a 2nd request with the same idempotency key, with a different
        # failure cause.
        post_data["to"] = orjson.dumps([99999]).decode()
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

        # Send a 3rd request with the same idempotency key, with a different
        # failure cause.

        # A lazily-translated error message (NOT yet evaluated to str).
        lazy_error_message = gettext_lazy("Lazy validation failure while sending.")

        # Make the request fail carrying a lazy message.
        with mock.patch(
            "zerver.views.message_send.check_send_message",
            side_effect=JsonableError(lazy_error_message),
        ):
            result = self.client_post("/json/messages", post_data, headers=headers)

        self.assert_json_error(result, str(lazy_error_message))

        idempotent_rows = IdempotentRequest.objects.filter(
            realm_id=realm.id, user_id=sender.id, succeeded=False, cached_result__isnull=False
        )
        # No more idempotency rows should be created.
        self.assert_length(idempotent_rows, 1)

        # Ensure the 3rd request's failed response overrides that of the 2nd.
        # And cached_result deserializes back to the same response,
        # confirming lazy message survived the round-trip as a string.
        self.assertEqual(
            orjson.loads(result.content),
            get_cached_result_json(cast(dict[str, Any], idempotent_rows[0].cached_result)),
        )

        # Since all requests failed, no messages should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, content=post_data["content"]), 0
        )

    def test_failure_after_successful_work(self) -> None:
        """
        When request fails (e.g., post-work validation)
        after the work has already completed successfully and cached.

        By this system design, the work is preferred to be the
        final fallible operation, but that's not guaranteed.
        That's why we test and document this behavior and developers
        should be aware of this nuance especially when applying
        this system to other endpoints.

        Important: This case doesn't apply to the message sending path since
        there is no validation check that would raise a post-send 4xx failure
        after the message is sent.
        """
        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        # Set a UUID V4 Idempotency-Key.
        headers = {"Idempotency-Key": "8e118d41-39d7-4a82-8da9-a6a3162d57e0"}

        # Make the request fail after successfully
        # completing the work: we mock a failure after
        # do_send_messages has completed and returned.
        with mock.patch(
            "zerver.views.message_send.json_success",
            side_effect=JsonableError("Error after successful work."),
        ):
            result = self.client_post("/json/messages", post_data, headers=headers)
            self.assert_json_error(result, "Error after successful work.")

            # Retry the failed request with the same key.
            result = self.client_post("/json/messages", post_data, headers=headers)
            self.assert_json_error(result, "Error after successful work.")

            # Retry the failed request with a different key.
            # Our edge case and sad path that would duplicate the work.
            # This is avoidable if the client decides to treat this 4xx error
            # as a transient error and doesn't change the key.
            headers["Idempotency-Key"] = "8e118d41-39d7-4a82-8da9-a6a3162d57e1"
            result = self.client_post("/json/messages", post_data, headers=headers)
            self.assert_json_error(result, "Error after successful work.")

        # Important check: even though all requests failed, the cache should
        # faithfully reflect the 2 successful (duplicated) work.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, succeeded=True, cached_result__isnull=False
            ),
            2,
        )

        # Now retry the first failed request with the same key to
        # ensure that the preserved cached success is actually replayable.
        # In practice, this can happen when that 4xx error is treated
        # as a transient error.
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_success(result)

        # We expect 2 messages only:
        # 2 from the 1st and 3rd failed requests that completed the work successfully.
        # 0 from the successful and duplicate requests.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            2,
        )

    def test_different_requests_with_same_key(self) -> None:
        """
        Test behavior when a confused client reuses the same Idempotency-Key for a different request.

        TODO: Ideally, in future, we should detect this behavior by comparing the parameters for both requests,
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
        # mistakenly using the same key. This is an expected behavior since it's the client's
        # responsibility to change the key in this case.
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

        # Call an idempotent_work-decorated function directly.
        do_send_messages([build_message_send_dict(message=message)], acting_user=sender)

        # No idempotency rows should be created.
        self.assertEqual(IdempotentRequest.objects.count(), 0)


class TransactionIdempotencyTest(ZulipTransactionTestCase):
    """Tests inside this class raise expected errors that can prevent
    the test from continuing and throw TransactionManagementError,
    so we put them inside ZulipTransactionTestCase to prevent this.
    """

    @override
    def tearDown(self) -> None:
        # Delete every row created during the test.
        # _raw_delete bypasses Django's delete collector, so it
        # skips cascade/RESTRICT/PROTECT; doing all deletes in one transaction
        # lets PostgreSQL check its deferred foreign keys once at commit,
        # so deletion order doesn't matter.
        with transaction.atomic(durable=True):
            for model, pks in get_row_pks_in_all_tables():
                pre_existing_pks = self.models_pks_set[model]
                new_pks = pks - pre_existing_pks
                if new_pks:
                    queryset = model._default_manager.filter(pk__in=new_pks)
                    queryset._raw_delete(queryset.db)
        super().tearDown()

    def post_message_in_new_client(
        self, post_data: dict[str, str], idempotency_key: str
    ) -> "TestHttpResponse":
        """Send a message POST on a fresh client and db connection.

        Django's test client shares mutable per-instance state (its cookie
        jar) and isn't safe across threads, so each concurrent request needs
        its own client. We replicate self.login("hamlet") and self.client_post().
        """
        sender = self.example_user("hamlet")
        client = ZulipTestClient()
        request = HttpRequest()
        request.session = client.session
        client.login(
            request=request,
            username=sender.delivery_email,
            password=initial_password(sender.delivery_email),
            realm=sender.realm,
        )

        # set_http_headers() only mutates the local extra dict (adding
        # HTTP_HOST and a User-Agent), so it is safe to reuse across threads.
        extra: dict[str, str] = {}
        self.set_http_headers(extra)
        try:
            return client.post(
                "/json/messages",
                urlencode(post_data, doseq=True),
                follow=False,
                secure=False,
                headers={"Idempotency-Key": idempotency_key},
                query_params=None,
                content_type="application/x-www-form-urlencoded",
                **extra,
            )
        finally:
            # Close this thread's db connection now that its work is done.
            connections.close_all()

    async def test_concurrency(self) -> None:
        """
        Ensure the idempotency system works as expected during concurrency.
        """
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        sender = await sync_to_async(lambda: self.example_user("hamlet"))()

        async def async_send_request(idempotency_key: str) -> "TestHttpResponse":
            result = await sync_to_async(
                lambda: self.post_message_in_new_client(post_data, idempotency_key),
                thread_sensitive=False,
            )()
            return result

        # UUID V4 Idempotency-Key.
        idempotency_key = "8e118d41-39d7-4a82-8da9-a6a3162d57eb"
        # Send 5 concurrent requests with the same Idempotency-Key.
        results = await asyncio.gather(*[async_send_request(idempotency_key) for _ in range(5)])

        # IMPORTANT: While asyncio sends these 5 requests concurrently,
        # nothing prevents them from being processed serially and all
        # returning 200, so a conflict error (409) is expected but not
        # guaranteed to be raised.
        # test_concurrent_request_aborts_with_conflict is what actually
        # verifies the lock and abort behavior in a very deterministic way.
        one_succeeded = False
        for result in results:
            try:
                self.assert_json_success(result)
                one_succeeded = True

            # If a request fails, the failure should only be caused by
            # a conflict error (409).
            except AssertionError:
                self.assert_json_error(
                    result,
                    "A request with the same Idempotency-Key is currently being processed; retry to observe its result.",
                    409,
                )

        # During true concurrency, it's hard to predict
        # how many requests succeed or abort, but we know at least one must succeed.
        self.assertTrue(one_succeeded)

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
            lambda: list(
                IdempotentRequest.objects.filter(realm_id=sender.realm_id, user_id=sender.id)
            )
        )()
        # Since we are using concrete values in request_keys, we should be explicit
        # about which key values are expected to be created.
        created_keys = {str(row.idempotency_key) for row in idempotent_rows}
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

    def test_concurrent_request_aborts_with_conflict(self) -> None:
        """
        A request that arrives while another request with the same key is
        still doing the work must abort immediately with a 409.

        We force the contention deterministically: the "winner" request pauses
        inside the work while holding the db row lock; the contender then runs and
        must abort; only then is the winner released to finish successfully.
        """
        realm = get_realm("zulip")
        self.login("hamlet")
        sender = self.example_user("hamlet")

        idempotency_key = "8e118d41-39d7-4a82-8da9-a6a3162d57eb"
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "Test Idempotency message",
            "topic": "Test topic",
        }

        # Two one-way signals to coordinate the requests in opposite directions:
        # winner_holds_lock: tells the contender once it is holding the db lock.
        # contender_has_aborted: tells the winner once it has aborted, so the winner can proceed.
        winner_holds_lock = threading.Event()
        contender_has_aborted = threading.Event()
        original_create_user_messages = create_user_messages

        def hold_lock_until_contender_aborts(*args: Any, **kwargs: Any) -> Any:
            # 1st signal: db lock is acquired so contender can proceed.
            winner_holds_lock.set()
            # Pausing here keeps the db row locked until the contender has aborted.
            assert contender_has_aborted.wait(timeout=10), "contender did not run in time"
            # Resume work after contender has aborted.
            return original_create_user_messages(*args, **kwargs)

        winner_responses: list[TestHttpResponse] = []

        def send_winner_request() -> None:
            winner_responses.append(self.post_message_in_new_client(post_data, idempotency_key))

        # The winner runs in a background thread so it can hold the lock open
        # while this (main) thread sends the contender.
        # We mock create_user_messages which runs after @idempotent_work
        # has acquired the db lock.
        winner_thread = threading.Thread(target=send_winner_request)
        with mock.patch(
            "zerver.actions.message_send.create_user_messages",
            side_effect=hold_lock_until_contender_aborts,
        ):
            winner_thread.start()

            # Send the contender only once the winner holds the db lock.
            assert winner_holds_lock.wait(timeout=10), "winner did not acquire the lock in time"
            contender_result = self.client_post(
                "/json/messages", post_data, headers={"Idempotency-Key": idempotency_key}
            )

            # 2nd signal: Release the winner lock now that the contender has aborted.
            contender_has_aborted.set()
            # Wait for the winner thread to finish.
            winner_thread.join(timeout=10)
        self.assertFalse(winner_thread.is_alive(), "winner thread did not finish in time")

        # Contender aborted with a 409.
        self.assert_json_error(
            contender_result,
            "A request with the same Idempotency-Key is currently being processed; retry to observe its result.",
            409,
        )
        # Winner succeeded.
        self.assert_json_success(winner_responses[0])

        # Only one idempotency row should be created.
        self.assert_length(
            IdempotentRequest.objects.filter(
                realm_id=realm.id, user_id=sender.id, idempotency_key=idempotency_key
            ),
            1,
        )

        # The contender didn't duplicate the work.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            1,
        )

    def test_work_failure(self) -> None:
        """
        Ensure idempotency when the core work fails.
        This ensures we cache the response error and return it for subsequent requests
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

        # The following 2 mocks are identical; they
        # make the core work fail by mocking a function
        # inside the core work (e.g. do_send_messages).
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
            with queries_captured() as base_queries:
                result = self.client_post("/json/messages", post_data)
            self.assert_json_error(result, "Error while doing the work.")

        with mock.patch(
            "zerver.actions.message_send.create_user_messages",
            side_effect=JsonableError("Error while doing the work."),
        ) as do_work_mock:
            # For work failure, we expect 3 extra queries:
            # 1 to insert the initial row +
            # 1 to fetch cached_result and lock the row +
            # 1 (if it's a non-transient 4xx error) to cache the error.
            with self.assert_database_query_count(len(base_queries) + 3):
                first_result = self.client_post("/json/messages", post_data, headers=headers)
            self.assert_json_error(first_result, "Error while doing the work.")

            # Only one idempotency row should be created.
            self.assert_length(
                IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
            )
            # That one row should NOT have succeeded and should have the cached_result.
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
        Test behavior when the server's validation for the same request changes;
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
        # This is the favorable client behavior in this case,
        # and as a result the client gets the result of the new server validation,
        # i.e. the permission to post.
        headers["Idempotency-Key"] = "8e118d41-39d7-4a82-8da9-a6a3162d57e1"
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_success(result)
        # Now, an idempotency row should be updated to reflect the
        # succeeded and cached work.
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

    def test_server_failure_before_work(self) -> None:
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

        # Make the server fail before attempting to do the work.
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
        # Expect one idempotency row.
        self.assert_length(
            IdempotentRequest.objects.filter(realm_id=realm.id, user_id=sender.id), 1
        )
        # That one row should have succeeded and have a cached_result.
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

        # Make the server fail after successfully doing the work.
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
        # Actually, the Zulip web app retries the request using the same key in case of a server error (5xx).
        result = self.client_post("/json/messages", post_data, headers=headers)
        self.assert_json_success(result)

        # Ensure idempotency: no more messages should be created.
        self.assert_length(
            Message.objects.filter(realm_id=realm.id, sender=sender, content=post_data["content"]),
            1,
        )


class JsonErrorSerializationTest(ZulipTestCase):
    """
    The idempotency system caches a failed request's error and then replays it
    for duplicates. For that to be correct, a reconstructed error
    must be indistinguishable from the original when raised.

    So we verify json_error_serializer -> json_error_deserializer round-trip
    faithfully for the different shapes of JsonableError for better coverage.
    """

    def assert_roundtrip_matches_original(self, error: JsonableError) -> None:
        """
        Reconstruct the error exactly as the idempotency system does.
        Then match against the original error.
        """
        cached_result_field = IdempotentRequest._meta.get_field("cached_result")
        serialized_error = json_error_serializer(error)

        # We normally use orjson, but since IdempotentRequest.cached_result
        # uses json internally and not orjson, we replicate this here with the same
        # DjangoJSONEncoder as encoder.
        stored_and_reloaded = json.loads(
            json.dumps(serialized_error, cls=cached_result_field.encoder)
        )
        reconstructed_error = json_error_deserializer(stored_and_reloaded)
        original_response = json_response_from_error(error)
        reconstructed_response = json_response_from_error(reconstructed_error)

        self.assertEqual(reconstructed_response.status_code, original_response.status_code)
        self.assertEqual(reconstructed_response.content, original_response.content)
        self.assertEqual(dict(reconstructed_response.headers), dict(original_response.headers))

    def test_different_json_errors(self) -> None:

        self.assert_roundtrip_matches_original(JsonableError("A plain error message."))

        self.assert_roundtrip_matches_original(
            JsonableError(gettext_lazy("A lazily translated error message."))
        )

        self.assert_roundtrip_matches_original(DirectMessagePermissionError(is_nobody_group=True))

        self.assert_roundtrip_matches_original(IncompatibleParametersError(["param_a", "param_b"]))

        self.assert_roundtrip_matches_original(StreamWithIDDoesNotExistError(99999))

        self.assert_roundtrip_matches_original(CannotDeactivateLastUserError(is_last_owner=True))

        self.assert_roundtrip_matches_original(UnauthorizedError())

        self.assert_roundtrip_matches_original(RateLimitedError(secs_to_freedom=100))

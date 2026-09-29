import uuid
from dataclasses import asdict
from typing import TYPE_CHECKING

import orjson

from zerver.actions.message_send import SentMessageResult, check_send_message
from zerver.actions.streams import do_change_stream_group_based_setting
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import do_change_can_forge_sender
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import IdempotentRequest, Message, UserProfile
from zerver.models.clients import get_client
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

IDEMPOTENCY_KEY = "8e118d41-39d7-4a82-8da9-a6a3162d57eb"


class IdempotencyKeyTest(ZulipTestCase):
    def count_messages(self, **filters: object) -> int:
        return Message.objects.filter(realm=get_realm("zulip"), **filters).count()

    def send_channel_message(
        self, idempotency_key: str | None = IDEMPOTENCY_KEY, channel_name: str = "Verona"
    ) -> "TestHttpResponse":
        return self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": orjson.dumps(channel_name).decode(),
                "topic": "idempotency",
                "content": "idempotent message",
            },
            headers={} if idempotency_key is None else {"Idempotency-Key": idempotency_key},
        )

    def send_with_idempotent_request(
        self, idempotent_request: IdempotentRequest
    ) -> SentMessageResult:
        return check_send_message(
            self.example_user("hamlet"),
            get_client("website"),
            "stream",
            ["Verona"],
            "idempotency",
            "idempotent message",
            idempotent_request=idempotent_request,
        )

    def test_invalid_idempotency_key(self) -> None:
        self.login("hamlet")
        for invalid_key in ["", "not-a-uuid", IDEMPOTENCY_KEY[:-1]]:
            self.assert_json_error(
                self.send_channel_message(invalid_key),
                f"Invalid UUID in Idempotency-Key header: '{invalid_key}'",
            )
        self.assertFalse(IdempotentRequest.objects.exists())
        self.assertEqual(self.count_messages(content="idempotent message"), 0)

    def test_request_without_idempotency_key(self) -> None:
        self.login("hamlet")
        self.assert_json_success(self.send_channel_message(None))
        self.assert_json_success(self.send_channel_message(None))
        self.assertFalse(IdempotentRequest.objects.exists())
        self.assertEqual(self.count_messages(content="idempotent message"), 2)

    def test_replayed_request(self) -> None:
        self.login("hamlet")
        response = self.assert_json_success(self.send_channel_message())
        self.assertEqual(self.assert_json_success(self.send_channel_message()), response)
        self.assertEqual(self.count_messages(content="idempotent message"), 1)

    def test_replay_includes_automatic_new_visibility_policy(self) -> None:
        hamlet = self.example_user("hamlet")
        do_change_user_setting(
            hamlet,
            "automatically_follow_topics_policy",
            UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND,
            acting_user=None,
        )
        self.login_user(hamlet)

        response = self.assert_json_success(self.send_channel_message())
        self.assertIn("automatic_new_visibility_policy", response)
        self.assertEqual(self.assert_json_success(self.send_channel_message()), response)

    def test_new_idempotency_key_sends_new_message(self) -> None:
        self.login("hamlet")
        self.assert_json_success(self.send_channel_message())
        self.assert_json_success(self.send_channel_message(str(uuid.uuid4())))
        self.assertEqual(self.count_messages(content="idempotent message"), 2)

    def test_query_counts(self) -> None:
        self.login("hamlet")
        # The first message to a topic takes extra queries.
        self.assert_json_success(self.send_channel_message(None))
        with self.assert_database_query_count(18):
            self.assert_json_success(self.send_channel_message(None))
        with self.assert_database_query_count(18 + 4):
            self.assert_json_success(self.send_channel_message())
        with self.assert_database_query_count(4):
            self.assert_json_success(self.send_channel_message())

    def test_replay_skips_revalidation(self) -> None:
        self.login("hamlet")
        response = self.assert_json_success(self.send_channel_message())

        stream = get_stream("Verona", get_realm("zulip"))
        do_change_stream_group_based_setting(
            stream,
            "can_send_message_group",
            get_system_user_group_by_name(SystemGroups.NOBODY, stream.realm_id),
            acting_user=self.example_user("iago"),
        )
        self.assert_json_error(
            self.send_channel_message(str(uuid.uuid4())),
            "You do not have permission to post in this channel.",
        )
        self.assertEqual(self.assert_json_success(self.send_channel_message()), response)

    def test_replay_of_request_completed_after_lookup(self) -> None:
        """A duplicate that looked up the row before the original succeeded
        still gets the original's result.
        """
        hamlet = self.example_user("hamlet")
        idempotent_request = IdempotentRequest.objects.create(
            realm=hamlet.realm, user=hamlet, idempotency_key=IDEMPOTENCY_KEY
        )
        stale_idempotent_request = IdempotentRequest.objects.get(id=idempotent_request.id)

        result = self.send_with_idempotent_request(idempotent_request)
        self.assertIsNone(stale_idempotent_request.cached_result)
        self.assertEqual(self.send_with_idempotent_request(stale_idempotent_request), result)
        self.assertEqual(self.count_messages(content="idempotent message"), 1)

    def test_reused_idempotency_key_with_different_parameters(self) -> None:
        """A key reused with different parameters gets the original response, as documented."""
        self.login("hamlet")
        response = self.assert_json_success(self.send_channel_message())
        self.assertEqual(
            self.assert_json_success(self.send_channel_message(channel_name="Denmark")), response
        )
        self.assertEqual(self.count_messages(content="idempotent message"), 1)

    def test_idempotent_request_deleted_after_lookup(self) -> None:
        """A row deleted by the cron job after the view's lookup is recreated with the result."""
        hamlet = self.example_user("hamlet")
        idempotent_request = IdempotentRequest.objects.create(
            realm=hamlet.realm, user=hamlet, idempotency_key=IDEMPOTENCY_KEY
        )
        IdempotentRequest.objects.filter(id=idempotent_request.id).delete()

        result = self.send_with_idempotent_request(idempotent_request)
        self.assertEqual(IdempotentRequest.objects.get().cached_result, asdict(result))

    def test_idempotency_key_is_scoped_to_user(self) -> None:
        self.login("hamlet")
        self.assert_json_success(self.send_channel_message())
        self.login("othello")
        self.assert_json_success(self.send_channel_message())
        self.assertEqual(self.count_messages(content="idempotent message"), 2)

    def test_failed_request_is_not_cached(self) -> None:
        self.login("hamlet")
        self.assert_json_error(
            self.send_channel_message(channel_name="new channel"),
            "Channel 'new channel' does not exist",
        )

        create_stream_if_needed(get_realm("zulip"), "new channel")
        self.assert_json_success(self.send_channel_message(channel_name="new channel"))
        self.assertEqual(self.count_messages(content="idempotent message"), 1)

    def test_replayed_forged_message(self) -> None:
        """A replayed forged message is sent once, and the row belongs to the
        requester rather than the forged sender.
        """
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        do_change_can_forge_sender(cordelia, True)
        self.login_user(cordelia)
        post_data = {
            "type": "direct",
            "sender": hamlet.email,
            "to": orjson.dumps([cordelia.id]).decode(),
            "content": "forged message",
        }

        def send_forged_message() -> dict[str, object]:
            return self.assert_json_success(
                self.client_post(
                    "/json/messages", post_data, headers={"Idempotency-Key": IDEMPOTENCY_KEY}
                )
            )

        response = send_forged_message()
        self.assertEqual(send_forged_message(), response)
        self.assertEqual(self.count_messages(sender=hamlet, content="forged message"), 1)
        self.assertEqual(IdempotentRequest.objects.get().user, cordelia)

    def test_replayed_bot_message_to_channel_without_subscribers(self) -> None:
        """A replay sends neither the bot's message nor the owner notification from validation."""
        bot = self.create_test_bot(
            short_name="whatever", user_profile=self.example_user("cordelia")
        )
        create_stream_if_needed(get_realm("zulip"), "Acropolis")
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Acropolis").decode(),
            "topic": "idempotency",
            "content": "bot message",
        }

        def send_bot_message() -> dict[str, object]:
            return self.assert_json_success(
                self.api_post(
                    bot, "/api/v1/messages", post_data, HTTP_IDEMPOTENCY_KEY=IDEMPOTENCY_KEY
                )
            )

        response = send_bot_message()
        # Owner notifications are rate-limited; reset that so a replay
        # that revalidated the message would send a second one.
        bot.last_reminder = None
        bot.save(update_fields=["last_reminder"])
        self.assertEqual(send_bot_message(), response)
        self.assertEqual(self.count_messages(sender=bot, content="bot message"), 1)
        self.assertEqual(self.count_messages(content__contains="does not have any subscribers"), 1)

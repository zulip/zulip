from datetime import timedelta
from email.headerregistry import Address
from typing import Any, Optional, Set
from unittest import mock

import orjson
from django.conf import settings
from django.db.models import Q
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_create_user
from zerver.actions.message_send import (
    build_message_send_dict,
    check_message,
    check_send_stream_message,
    do_send_messages,
    extract_private_recipients,
    extract_stream_indicator,
    internal_prep_private_message,
    internal_prep_stream_message_by_name,
    internal_send_huddle_message,
    internal_send_private_message,
    internal_send_stream_message,
    internal_send_stream_message_by_name,
    send_rate_limited_pm_notification_to_bot_owner,
)
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.streams import do_change_stream_post_policy
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import do_change_can_forge_sender, do_deactivate_user
from zerver.lib.addressee import Addressee
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import get_raw_unread_data, get_recent_private_conversations
from zerver.lib.message_cache import MessageDict
from zerver.lib.per_request_cache import flush_per_request_caches
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    get_user_messages,
    make_client,
    message_stream_count,
    most_recent_message,
    most_recent_usermessage,
    reset_email_visibility_to_everyone_in_zulip_realm,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import (
    Message,
    NamedUserGroup,
    Realm,
    RealmDomain,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.recipients import get_or_create_huddle
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot, get_user
from zerver.views.message_send import InvalidMirrorInputError


class MessagePOSTTest(ZulipTestCase):
    def _send_and_verify_message(
        self, user: UserProfile, stream_name: str, error_msg: Optional[str] = None
    ) -> None:
        if error_msg is None:
            msg_id = self.send_stream_message(user, stream_name)
            result = self.api_get(user, "/api/v1/messages/" + str(msg_id))
            self.assert_json_success(result)
        else:
            with self.assertRaisesRegex(JsonableError, error_msg):
                self.send_stream_message(user, stream_name)

    def test_message_to_stream_by_name(self) -> None:
        """
        Sending a message to a stream to which you are subscribed is
        successful.
        """
        recipient_type_name = ["stream", "channel"]
        self.login("hamlet")

        for recipient_type in recipient_type_name:
            result = self.client_post(
                "/json/messages",
                {
                    "type": recipient_type,
                    "to": orjson.dumps("Verona").decode(),
                    "content": "Test message",
                    "topic": "Test topic",
                },
            )
            self.assert_json_success(result)

    def test_api_message_to_stream_by_name(self) -> None:
        """
        Same as above, but for the API view
        """
        recipient_type_name = ["stream", "channel"]
        user = self.example_user("hamlet")

        for recipient_type in recipient_type_name:
            result = self.api_post(
                user,
                "/api/v1/messages",
                {
                    "type": recipient_type,
                    "to": orjson.dumps("Verona").decode(),
                    "content": "Test message",
                    "topic": "Test topic",
                },
            )
            self.assert_json_success(result)

    def test_message_to_stream_with_nonexistent_id(self) -> None:
        cordelia = self.example_user("cordelia")
        bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )
        result = self.api_post(
            bot,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": orjson.dumps([99999]).decode(),
                "content": "Stream message by ID.",
                "topic": "Test topic for stream ID message",
            },
        )
        self.assert_json_error(result, "Channel with ID '99999' does not exist")

        msg = self.get_last_message()
        expected = (
            "Your bot `whatever-bot@zulip.testserver` tried to send a message to "
            "channel ID 99999, but there is no channel with that ID."
        )
        self.assertEqual(msg.content, expected)

    def test_message_to_stream_with_no_subscribers(self) -> None:
        """
        Sending a message to an empty stream succeeds, but sends a warning
        to the owner.
        """
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )
        stream = create_stream_if_needed(realm, "Acropolis")[0]
        result = self.api_post(
            bot,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": orjson.dumps(stream.name).decode(),
                "content": "Stream message to an empty stream by name.",
                "topic": "Test topic for empty stream name message",
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        expected = "Stream message to an empty stream by name."
        self.assertEqual(msg.content, expected)

        msg = self.get_second_to_last_message()
        expected = (
            "Your bot `whatever-bot@zulip.testserver` tried to send a message to "
            "channel #**Acropolis**. The channel exists but does not have any subscribers."
        )
        self.assertEqual(msg.content, expected)

    def test_message_to_stream_with_no_subscribers_by_id(self) -> None:
        """
        Sending a message to an empty stream succeeds, but sends a warning
        to the owner.
        """
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )
        stream = create_stream_if_needed(realm, "Acropolis")[0]
        result = self.api_post(
            bot,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": orjson.dumps([stream.id]).decode(),
                "content": "Stream message to an empty stream by id.",
                "topic": "Test topic for empty stream id message",
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        expected = "Stream message to an empty stream by id."
        self.assertEqual(msg.content, expected)

        msg = self.get_second_to_last_message()
        expected = (
            "Your bot `whatever-bot@zulip.testserver` tried to send a message to "
            "channel #**Acropolis**. The channel exists but does not have any subscribers."
        )
        self.assertEqual(msg.content, expected)

    def test_message_to_stream_by_id(self) -> None:
        """
        Sending a message to a stream (by stream ID) to which you are
        subscribed is successful.
        """
        recipient_type_name = ["stream", "channel"]
        self.login("hamlet")
        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)

        for recipient_type in recipient_type_name:
            content = f"Stream message by ID, type parameter: {recipient_type}."
            result = self.client_post(
                "/json/messages",
                {
                    "type": recipient_type,
                    "to": orjson.dumps([stream.id]).decode(),
                    "content": content,
                    "topic": "Test topic for stream ID message",
                },
            )
            self.assert_json_success(result)
            sent_message = self.get_last_message()
            self.assertEqual(sent_message.content, content)

    def test_sending_message_as_stream_post_policy_admins(self) -> None:
        """
        Sending messages to streams which only the admins can post to.
        """
        admin_profile = self.example_user("iago")
        self.login_user(admin_profile)

        stream_name = "Verona"
        stream = get_stream(stream_name, admin_profile.realm)
        do_change_stream_post_policy(
            stream, Stream.STREAM_POST_POLICY_ADMINS, acting_user=admin_profile
        )

        # Admins and their owned bots can send to STREAM_POST_POLICY_ADMINS streams
        self._send_and_verify_message(admin_profile, stream_name)
        admin_owned_bot = self.create_test_bot(
            short_name="whatever1",
            full_name="whatever1",
            user_profile=admin_profile,
        )
        self._send_and_verify_message(admin_owned_bot, stream_name)

        non_admin_profile = self.example_user("hamlet")
        self.login_user(non_admin_profile)

        # Non admins and their owned bots cannot send to STREAM_POST_POLICY_ADMINS streams
        self._send_and_verify_message(
            non_admin_profile,
            stream_name,
            "Only organization administrators can send to this channel.",
        )
        non_admin_owned_bot = self.create_test_bot(
            short_name="whatever2",
            full_name="whatever2",
            user_profile=non_admin_profile,
        )
        self._send_and_verify_message(
            non_admin_owned_bot,
            stream_name,
            "Only organization administrators can send to this channel.",
        )

        moderator_profile = self.example_user("shiva")
        self.login_user(moderator_profile)

        # Moderators and their owned bots cannot send to STREAM_POST_POLICY_ADMINS streams
        self._send_and_verify_message(
            moderator_profile,
            stream_name,
            "Only organization administrators can send to this channel.",
        )
        moderator_owned_bot = self.create_test_bot(
            short_name="whatever3",
            full_name="whatever3",
            user_profile=moderator_profile,
        )
        self._send_and_verify_message(
            moderator_owned_bot,
            stream_name,
            "Only organization administrators can send to this channel.",
        )

        # Bots without owner (except cross realm bot) cannot send to announcement only streams
        bot_without_owner = do_create_user(
            email="free-bot@zulip.testserver",
            password="",
            realm=non_admin_profile.realm,
            full_name="freebot",
            bot_type=UserProfile.DEFAULT_BOT,
            acting_user=None,
        )
        self._send_and_verify_message(
            bot_without_owner,
            stream_name,
            "Only organization administrators can send to this channel.",
        )

        # Cross realm bots should be allowed
        notification_bot = get_system_bot("notification-bot@zulip.com", stream.realm_id)
        internal_send_stream_message(
            notification_bot, stream, "Test topic", "Test message by notification bot"
        )
        self.assertEqual(self.get_last_message().content, "Test message by notification bot")

        guest_profile = self.example_user("polonius")
        # Guests cannot send to non-STREAM_POST_POLICY_EVERYONE streams
        self._send_and_verify_message(
            guest_profile, stream_name, "Only organization administrators can send to this channel."
        )

    def test_sending_message_as_stream_post_policy_moderators(self) -> None:
        """
        Sending messages to streams which only the moderators can post to.
        """
        admin_profile = self.example_user("iago")
        self.login_user(admin_profile)

        stream_name = "Verona"
        stream = get_stream(stream_name, admin_profile.realm)
        do_change_stream_post_policy(
            stream, Stream.STREAM_POST_POLICY_MODERATORS, acting_user=admin_profile
        )

        # Admins and their owned bots can send to STREAM_POST_POLICY_MODERATORS streams
        self._send_and_verify_message(admin_profile, stream_name)
        admin_owned_bot = self.create_test_bot(
            short_name="whatever1",
            full_name="whatever1",
            user_profile=admin_profile,
        )
        self._send_and_verify_message(admin_owned_bot, stream_name)

        moderator_profile = self.example_user("shiva")
        self.login_user(moderator_profile)

        # Moderators and their owned bots can send to STREAM_POST_POLICY_MODERATORS streams
        self._send_and_verify_message(moderator_profile, stream_name)
        moderator_owned_bot = self.create_test_bot(
            short_name="whatever2",
            full_name="whatever2",
            user_profile=moderator_profile,
        )
        self._send_and_verify_message(moderator_owned_bot, stream_name)

        non_admin_profile = self.example_user("hamlet")
        self.login_user(non_admin_profile)

        # Members and their owned bots cannot send to STREAM_POST_POLICY_MODERATORS streams
        self._send_and_verify_message(
            non_admin_profile,
            stream_name,
            "Only organization administrators and moderators can send to this channel.",
        )
        non_admin_owned_bot = self.create_test_bot(
            short_name="whatever3",
            full_name="whatever3",
            user_profile=non_admin_profile,
        )
        self._send_and_verify_message(
            non_admin_owned_bot,
            stream_name,
            "Only organization administrators and moderators can send to this channel.",
        )

        # Bots without owner (except cross realm bot) cannot send to STREAM_POST_POLICY_MODERATORS streams.
        bot_without_owner = do_create_user(
            email="free-bot@zulip.testserver",
            password="",
            realm=non_admin_profile.realm,
            full_name="freebot",
            bot_type=UserProfile.DEFAULT_BOT,
            acting_user=None,
        )
        self._send_and_verify_message(
            bot_without_owner,
            stream_name,
            "Only organization administrators and moderators can send to this channel.",
        )

        # System bots should be allowed
        notification_bot = get_system_bot("notification-bot@zulip.com", stream.realm_id)
        internal_send_stream_message(
            notification_bot, stream, "Test topic", "Test message by notification bot"
        )
        self.assertEqual(self.get_last_message().content, "Test message by notification bot")

        guest_profile = self.example_user("polonius")
        # Guests cannot send to non-STREAM_POST_POLICY_EVERYONE streams
        self._send_and_verify_message(
            guest_profile,
            stream_name,
            "Only organization administrators and moderators can send to this channel.",
        )

    def test_sending_message_as_stream_post_policy_restrict_new_members(self) -> None:
        """
        Sending messages to streams which new members cannot post to.
        """
        admin_profile = self.example_user("iago")
        self.login_user(admin_profile)

        do_set_realm_property(admin_profile.realm, "waiting_period_threshold", 10, acting_user=None)
        admin_profile.date_joined = timezone_now() - timedelta(days=9)
        admin_profile.save()
        self.assertTrue(admin_profile.is_provisional_member)
        self.assertTrue(admin_profile.is_realm_admin)

        stream_name = "Verona"
        stream = get_stream(stream_name, admin_profile.realm)
        do_change_stream_post_policy(
            stream, Stream.STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS, acting_user=admin_profile
        )

        # Admins and their owned bots can send to STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS streams,
        # even if the admin is a new user
        self._send_and_verify_message(admin_profile, stream_name)
        admin_owned_bot = self.create_test_bot(
            short_name="whatever1",
            full_name="whatever1",
            user_profile=admin_profile,
        )
        self._send_and_verify_message(admin_owned_bot, stream_name)

        non_admin_profile = self.example_user("hamlet")
        self.login_user(non_admin_profile)

        non_admin_profile.date_joined = timezone_now() - timedelta(days=9)
        non_admin_profile.save()
        self.assertTrue(non_admin_profile.is_provisional_member)
        self.assertFalse(non_admin_profile.is_realm_admin)

        # Non admins and their owned bots can send to STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS streams,
        # if the user is not a new member
        self._send_and_verify_message(
            non_admin_profile, stream_name, "New members cannot send to this channel."
        )
        non_admin_owned_bot = self.create_test_bot(
            short_name="whatever2",
            full_name="whatever2",
            user_profile=non_admin_profile,
        )
        self._send_and_verify_message(
            non_admin_owned_bot, stream_name, "New members cannot send to this channel."
        )

        non_admin_profile.date_joined = timezone_now() - timedelta(days=11)
        non_admin_profile.save()
        self.assertFalse(non_admin_profile.is_provisional_member)

        self._send_and_verify_message(non_admin_profile, stream_name)
        # We again set bot owner here, as date_joined of non_admin_profile is changed.
        non_admin_owned_bot.bot_owner = non_admin_profile
        non_admin_owned_bot.save()
        self._send_and_verify_message(non_admin_owned_bot, stream_name)

        # Bots without owner (except cross realm bot) cannot send to STREAM_POST_POLICY_ADMINS_ONLY and
        # STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS streams
        bot_without_owner = do_create_user(
            email="free-bot@zulip.testserver",
            password="",
            realm=non_admin_profile.realm,
            full_name="freebot",
            bot_type=UserProfile.DEFAULT_BOT,
            acting_user=None,
        )
        self._send_and_verify_message(
            bot_without_owner, stream_name, "New members cannot send to this channel."
        )

        moderator_profile = self.example_user("shiva")
        moderator_profile.date_joined = timezone_now() - timedelta(days=9)
        moderator_profile.save()
        self.assertTrue(moderator_profile.is_moderator)
        self.assertFalse(moderator_profile.is_provisional_member)

        # Moderators and their owned bots can send to STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS
        # streams, even if the moderator is a new user
        self._send_and_verify_message(moderator_profile, stream_name)
        moderator_owned_bot = self.create_test_bot(
            short_name="whatever3",
            full_name="whatever3",
            user_profile=moderator_profile,
        )
        moderator_owned_bot.date_joined = timezone_now() - timedelta(days=11)
        moderator_owned_bot.save()
        self._send_and_verify_message(moderator_owned_bot, stream_name)

        # System bots should be allowed
        notification_bot = get_system_bot("notification-bot@zulip.com", stream.realm_id)
        internal_send_stream_message(
            notification_bot, stream, "Test topic", "Test message by notification bot"
        )
        self.assertEqual(self.get_last_message().content, "Test message by notification bot")

        guest_profile = self.example_user("polonius")
        # Guests cannot send to non-STREAM_POST_POLICY_EVERYONE streams
        self._send_and_verify_message(
            guest_profile, stream_name, "Guests cannot send to this channel."
        )

    def test_api_message_with_default_to(self) -> None:
        """
        Sending messages without a to field should be sent to the default
        stream for the user_profile.
        """
        user = self.example_user("hamlet")
        user.default_sending_stream_id = get_stream("Verona", user.realm).id
        user.save()
        # The `to` field is required according to OpenAPI specification
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "channel",
                "content": "Test message no to",
                "topic": "Test topic",
            },
            intentionally_undocumented=True,
        )
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "Test message no to")

    def test_message_to_nonexistent_stream(self) -> None:
        """
        Sending a message to a nonexistent stream fails.
        """
        self.login("hamlet")
        self.assertFalse(Stream.objects.filter(name="nonexistent_stream"))
        result = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": "nonexistent_stream",
                "content": "Test message",
                "topic": "Test topic",
            },
        )
        self.assert_json_error(result, "Channel 'nonexistent_stream' does not exist")

    def test_message_to_nonexistent_stream_with_bad_characters(self) -> None:
        """
        Nonexistent stream name with bad characters should be escaped properly.
        """
        self.login("hamlet")
        self.assertFalse(Stream.objects.filter(name="""&<"'><non-existent>"""))
        result = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": """&<"'><non-existent>""",
                "content": "Test message",
                "topic": "Test topic",
            },
        )
        self.assert_json_error(
            result, "Channel '&amp;&lt;&quot;&#x27;&gt;&lt;non-existent&gt;' does not exist"
        )

    def test_message_to_stream_with_automatically_change_visibility_policy(self) -> None:
        """
        Sending a message to a stream with the automatic follow/unmute policy
        enabled results in including an extra optional parameter in the response.
        """
        user = self.example_user("hamlet")
        do_change_user_setting(
            user,
            "automatically_follow_topics_policy",
            UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND,
            acting_user=None,
        )
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": orjson.dumps("Verona").decode(),
                "content": "Test message",
                "topic": "Test topic",
            },
        )
        content = self.assert_json_success(result)
        assert "automatic_new_visibility_policy" in content
        self.assertEqual(content["automatic_new_visibility_policy"], 3)

        # Hamlet sends another message to the same topic. There will be no change in the visibility
        # policy, so the 'automatic_new_visibility_policy' parameter should be absent in the result.
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": orjson.dumps("Verona").decode(),
                "content": "Another Test message",
                "topic": "Test topic",
            },
        )
        content = self.assert_json_success(result)
        assert "automatic_new_visibility_policy" not in content

    def test_personal_message(self) -> None:
        """
        Sending a personal message to a valid username is successful.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        othello = self.example_user("othello")
        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test message",
                "to": orjson.dumps([othello.email]).decode(),
            },
        )
        self.assert_json_success(result)
        message_id = orjson.loads(result.content)["id"]

        recent_conversations = get_recent_private_conversations(user_profile)
        [(recipient_id, recent_conversation)] = recent_conversations.items()
        self.assertEqual(set(recent_conversation["user_ids"]), {othello.id})
        self.assertEqual(recent_conversation["max_message_id"], message_id)

        # Now send a message to yourself and see how that interacts with the data structure
        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test message",
                "to": orjson.dumps([user_profile.email]).decode(),
            },
        )
        self.assert_json_success(result)
        self_message_id = orjson.loads(result.content)["id"]

        recent_conversations = get_recent_private_conversations(user_profile)
        self.assert_length(recent_conversations, 2)
        recent_conversation = recent_conversations[recipient_id]
        self.assertEqual(set(recent_conversation["user_ids"]), {othello.id})
        self.assertEqual(recent_conversation["max_message_id"], message_id)

        # Now verify we have the appropriate self-pm data structure
        del recent_conversations[recipient_id]
        [(recipient_id, recent_conversation)] = recent_conversations.items()
        self.assertEqual(set(recent_conversation["user_ids"]), set())
        self.assertEqual(recent_conversation["max_message_id"], self_message_id)

    def test_personal_message_by_id(self) -> None:
        """
        Sending a personal message to a valid user ID is successful
        for both valid strings for `type` parameter.
        """
        self.login("hamlet")
        recipient_type_name = ["direct", "private"]

        for type in recipient_type_name:
            result = self.client_post(
                "/json/messages",
                {
                    "type": type,
                    "content": "Test message",
                    "to": orjson.dumps([self.example_user("othello").id]).decode(),
                },
            )
            self.assert_json_success(result)

            msg = self.get_last_message()
            self.assertEqual("Test message", msg.content)
            self.assertEqual(msg.recipient_id, self.example_user("othello").recipient_id)

    def test_group_personal_message_by_id(self) -> None:
        """
        Sending a personal message to a valid user ID is successful
        for both valid strings for `type` parameter.
        """
        self.login("hamlet")
        recipient_type_name = ["direct", "private"]

        for type in recipient_type_name:
            result = self.client_post(
                "/json/messages",
                {
                    "type": type,
                    "content": "Test message",
                    "to": orjson.dumps(
                        [self.example_user("othello").id, self.example_user("cordelia").id]
                    ).decode(),
                },
            )
            self.assert_json_success(result)

            msg = self.get_last_message()
            self.assertEqual("Test message", msg.content)
            huddle = get_or_create_huddle(
                [
                    self.example_user("hamlet").id,
                    self.example_user("othello").id,
                    self.example_user("cordelia").id,
                ]
            )
            self.assertEqual(msg.recipient_id, huddle.recipient_id)

    def test_personal_message_copying_self(self) -> None:
        """
        Sending a personal message to yourself plus another user is successful,
        and counts as a message just to that user.
        """
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(hamlet)
        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test message",
                "to": orjson.dumps([hamlet.id, othello.id]).decode(),
            },
        )
        self.assert_json_success(result)
        msg = self.get_last_message()
        # Verify that we're not actually on the "recipient list"
        self.assertNotIn("Hamlet", str(msg.recipient))

    def test_personal_message_to_nonexistent_user(self) -> None:
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test message",
                "to": "nonexistent",
            },
        )
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_personal_message_to_deactivated_user(self) -> None:
        """
        Sending a personal message to a deactivated user returns error JSON.
        """
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        do_deactivate_user(othello, acting_user=None)
        self.login("hamlet")

        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test message",
                "to": orjson.dumps([othello.id]).decode(),
            },
        )
        self.assert_json_error(result, f"'{othello.email}' is no longer using Zulip.")

        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test message",
                "to": orjson.dumps([othello.id, cordelia.id]).decode(),
            },
        )
        self.assert_json_error(result, f"'{othello.email}' is no longer using Zulip.")

    def test_personal_message_to_inaccessible_users(self) -> None:
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        self.set_up_db_for_testing_user_access()
        self.login("polonius")

        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test direct message",
                "to": orjson.dumps([othello.id]).decode(),
            },
        )
        self.assert_json_error(
            result, "You do not have permission to access some of the recipients."
        )

        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test direct message",
                "to": orjson.dumps([hamlet.id]).decode(),
            },
        )
        self.assert_json_success(result)
        msg = self.get_last_message()
        self.assertEqual(msg.content, "Test direct message")

        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test group direct message",
                "to": orjson.dumps([othello.id, cordelia.id]).decode(),
            },
        )
        self.assert_json_error(
            result, "You do not have permission to access some of the recipients."
        )

        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test group direct message",
                "to": orjson.dumps([hamlet.id, cordelia.id]).decode(),
            },
        )
        self.assert_json_error(
            result, "You do not have permission to access some of the recipients."
        )

        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "content": "Test group direct message",
                "to": orjson.dumps([hamlet.id, iago.id]).decode(),
            },
        )
        self.assert_json_success(result)
        msg = self.get_last_message()
        self.assertEqual(msg.content, "Test group direct message")

    def test_invalid_type(self) -> None:
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login("hamlet")
        othello = self.example_user("othello")
        result = self.client_post(
            "/json/messages",
            {
                "type": "invalid type",
                "content": "Test message",
                "to": othello.email,
            },
        )
        self.assert_json_error(result, "Invalid type")

    def test_empty_message(self) -> None:
        """
        Sending a message that is empty or only whitespace should fail
        """
        self.login("hamlet")
        othello = self.example_user("othello")
        result = self.client_post(
            "/json/messages",
            {"type": "direct", "content": " ", "to": othello.email},
        )
        self.assert_json_error(result, "Message must not be empty")

    def test_empty_string_topic(self) -> None:
        """
        Sending a message that has empty string topic should fail
        """
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": "Verona",
                "content": "Test message",
                "topic": "",
            },
        )
        self.assert_json_error(result, "Topic can't be empty!")

    def test_missing_topic(self) -> None:
        """
        Sending a message without topic should fail
        """
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {"type": "channel", "to": "Verona", "content": "Test message"},
        )
        self.assert_json_error(result, "Missing topic")

    def test_invalid_topic(self) -> None:
        """
        Sending a message with invalid 'Cc', 'Cs' and 'Cn' category of unicode characters
        """
        # For 'Cc' category
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": "Verona",
                "topic": "Test\n\rTopic",
                "content": "Test message",
            },
        )
        self.assert_json_error(result, "Invalid character in topic, at position 5!")

        # For 'Cn' category
        result = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": "Verona",
                "topic": "Test\ufffeTopic",
                "content": "Test message",
            },
        )
        self.assert_json_error(result, "Invalid character in topic, at position 5!")

    def test_invalid_recipient_type(self) -> None:
        """
        Messages other than the type of "direct", "private", "channel" or "stream" are invalid.
        """
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "invalid",
                "to": "Verona",
                "content": "Test message",
                "topic": "Test topic",
            },
        )
        self.assert_json_error(result, "Invalid type")

    def test_private_message_without_recipients(self) -> None:
        """
        Sending a direct message without recipients should fail
        """
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {"type": "direct", "content": "Test content", "to": ""},
        )
        self.assert_json_error(result, "Message must have recipients")

    def test_mirrored_huddle(self) -> None:
        """
        Sending a mirrored huddle message works
        """
        result = self.api_post(
            self.mit_user("starnine"),
            "/api/v1/messages",
            {
                "type": "direct",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": orjson.dumps(
                    [self.mit_email("starnine"), self.mit_email("espuser")]
                ).decode(),
            },
            subdomain="zephyr",
        )
        self.assert_json_success(result)

    def test_mirrored_personal(self) -> None:
        """
        Sending a mirrored personal message works
        """
        result = self.api_post(
            self.mit_user("starnine"),
            "/api/v1/messages",
            {
                "type": "direct",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": orjson.dumps([self.mit_email("starnine")]).decode(),
            },
            subdomain="zephyr",
        )
        self.assert_json_success(result)

    def test_mirrored_personal_browser(self) -> None:
        """
        Sending a mirrored personal message via the browser should not work.
        """
        user = self.mit_user("starnine")
        self.login_user(user)
        result = self.client_post(
            "/json/messages",
            {
                "type": "direct",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": self.mit_email("starnine"),
            },
            subdomain="zephyr",
        )
        self.assert_json_error(result, "Invalid mirrored message")

    def test_mirrored_personal_to_someone_else(self) -> None:
        """
        Sending a mirrored personal message to someone else is not allowed.
        """
        result = self.api_post(
            self.mit_user("starnine"),
            "/api/v1/messages",
            {
                "type": "direct",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": self.mit_email("espuser"),
            },
            subdomain="zephyr",
        )
        self.assert_json_error(result, "User not authorized for this query")

    def test_duplicated_mirrored_huddle(self) -> None:
        """
        Sending two mirrored huddles in the row return the same ID
        """
        msg = {
            "type": "direct",
            "sender": self.mit_email("sipbtest"),
            "content": "Test message",
            "client": "zephyr_mirror",
            "to": orjson.dumps([self.mit_email("espuser"), self.mit_email("starnine")]).decode(),
        }

        with mock.patch(
            "DNS.dnslookup",
            return_value=[
                ["starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash"]
            ],
        ):
            result1 = self.api_post(
                self.mit_user("starnine"), "/api/v1/messages", msg, subdomain="zephyr"
            )
            self.assert_json_success(result1)

        with mock.patch(
            "DNS.dnslookup",
            return_value=[["espuser:*:95494:101:Esp Classroom,,,:/mit/espuser:/bin/athena/bash"]],
        ):
            result2 = self.api_post(
                self.mit_user("espuser"), "/api/v1/messages", msg, subdomain="zephyr"
            )
            self.assert_json_success(result2)

        self.assertEqual(orjson.loads(result1.content)["id"], orjson.loads(result2.content)["id"])

    def test_message_with_null_bytes(self) -> None:
        """
        A message with null bytes in it is handled.
        """
        self.login("hamlet")
        post_data = {
            "type": "channel",
            "to": "Verona",
            "content": "  I like null bytes \x00 in my content",
            "topic": "Test topic",
        }
        result = self.client_post("/json/messages", post_data)
        self.assert_json_error(result, "Message must not contain null bytes")

    def test_strip_message(self) -> None:
        """
        A message with mixed whitespace at the end is cleaned up.
        """
        self.login("hamlet")
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "  I like whitespace at the end! \n\n \n",
            "topic": "Test topic",
        }
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)
        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "  I like whitespace at the end!")

        # Test if it removes the new line from the beginning of the message.
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "\nAvoid the new line at the beginning of the message.",
            "topic": "Test topic",
        }
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)
        sent_message = self.get_last_message()
        self.assertEqual(
            sent_message.content, "Avoid the new line at the beginning of the message."
        )

    @override_settings(MAX_MESSAGE_LENGTH=25)
    def test_long_message(self) -> None:
        """
        Sending a message longer than the maximum message length succeeds but is
        truncated.
        """
        self.login("hamlet")
        MAX_MESSAGE_LENGTH = settings.MAX_MESSAGE_LENGTH
        long_message = "A" * (MAX_MESSAGE_LENGTH + 1)
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": long_message,
            "topic": "Test topic",
        }
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(
            sent_message.content, "A" * (MAX_MESSAGE_LENGTH - 20) + "\n[message truncated]"
        )

    def test_long_topic(self) -> None:
        """
        Sending a message with a topic longer than the maximum topic length
        succeeds, but the topic is truncated.
        """
        self.login("hamlet")
        long_topic_name = "A" * (MAX_TOPIC_NAME_LENGTH + 1)
        post_data = {
            "type": "channel",
            "to": orjson.dumps("Verona").decode(),
            "content": "test content",
            "topic": long_topic_name,
        }
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.topic_name(), "A" * (MAX_TOPIC_NAME_LENGTH - 3) + "...")

    def test_send_forged_message_as_not_superuser(self) -> None:
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": "Verona",
                "content": "Test message",
                "topic": "Test topic",
                "forged": "true",
            },
        )
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_when_sender_is_not_set(self) -> None:
        result = self.api_post(
            self.mit_user("starnine"),
            "/api/v1/messages",
            {
                "type": "direct",
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": self.mit_email("starnine"),
            },
            subdomain="zephyr",
        )
        self.assert_json_error(result, "Missing sender")

    def test_send_message_as_not_superuser_when_type_is_not_private(self) -> None:
        result = self.api_post(
            self.mit_user("starnine"),
            "/api/v1/messages",
            {
                "type": "channel",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": self.mit_email("starnine"),
            },
            subdomain="zephyr",
        )
        self.assert_json_error(result, "User not authorized for this query")

    @mock.patch("zerver.views.message_send.create_mirrored_message_users")
    def test_send_message_create_mirrored_message_user_returns_invalid_input(
        self, create_mirrored_message_users_mock: Any
    ) -> None:
        create_mirrored_message_users_mock.side_effect = InvalidMirrorInputError()
        result = self.api_post(
            self.mit_user("starnine"),
            "/api/v1/messages",
            {
                "type": "direct",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": self.mit_email("starnine"),
            },
            subdomain="zephyr",
        )
        self.assert_json_error(result, "Invalid mirrored message")

    @mock.patch("zerver.views.message_send.create_mirrored_message_users")
    def test_send_message_when_client_is_zephyr_mirror_but_string_id_is_not_zephyr(
        self, create_mirrored_message_users_mock: Any
    ) -> None:
        create_mirrored_message_users_mock.return_value = mock.Mock()
        user = self.mit_user("starnine")
        user.realm.string_id = "notzephyr"
        user.realm.save()
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "direct",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": user.email,
            },
            subdomain="notzephyr",
        )
        self.assert_json_error(result, "Zephyr mirroring is not allowed in this organization")

    @mock.patch("zerver.views.message_send.create_mirrored_message_users")
    def test_send_message_when_client_is_zephyr_mirror_but_recipient_is_user_id(
        self, create_mirrored_message_users_mock: Any
    ) -> None:
        create_mirrored_message_users_mock.return_value = mock.Mock()
        user = self.mit_user("starnine")
        self.login_user(user)
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "direct",
                "sender": self.mit_email("sipbtest"),
                "content": "Test message",
                "client": "zephyr_mirror",
                "to": orjson.dumps([user.id]).decode(),
            },
            subdomain="zephyr",
        )
        self.assert_json_error(result, "Mirroring not allowed with recipient user IDs")

    def test_send_message_irc_mirror(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()
        self.login("hamlet")
        bot_info = {
            "full_name": "IRC bot",
            "short_name": "irc",
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        email = "irc-bot@zulip.testserver"
        user = get_user(email, get_realm("zulip"))
        user.can_forge_sender = True
        user.save()
        user = get_user(email, get_realm("zulip"))
        self.subscribe(user, "IRCland")

        # Simulate a mirrored message with a slightly old timestamp.
        fake_date_sent = timezone_now() - timedelta(minutes=37)
        fake_timestamp = datetime_to_timestamp(fake_date_sent)

        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "channel",
                "forged": "true",
                "time": fake_timestamp,
                "sender": "irc-user@irc.zulip.com",
                "content": "Test message",
                "client": "irc_mirror",
                "topic": "from irc",
                "to": orjson.dumps("IRCLand").decode(),
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assertEqual(int(datetime_to_timestamp(msg.date_sent)), int(fake_timestamp))

        # Now test again using forged=yes
        fake_date_sent = timezone_now() - timedelta(minutes=22)
        fake_timestamp = datetime_to_timestamp(fake_date_sent)

        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "channel",
                "forged": "yes",
                "time": fake_timestamp,
                "sender": "irc-user@irc.zulip.com",
                "content": "Test message",
                "client": "irc_mirror",
                "topic": "from irc",
                "to": orjson.dumps("IRCLand").decode(),
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assertEqual(int(datetime_to_timestamp(msg.date_sent)), int(fake_timestamp))

    def test_unsubscribed_can_forge_sender(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        cordelia = self.example_user("cordelia")
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True)

        self.unsubscribe(cordelia, stream_name)

        # As long as Cordelia cam_forge_sender, she can send messages
        # to ANY stream, even one she is not unsubscribed to, and
        # she can do it for herself or on behalf of a mirrored user.

        def test_with(sender_email: str, client: str, forged: bool) -> None:
            payload = dict(
                type="channel",
                to=orjson.dumps(stream_name).decode(),
                client=client,
                topic="whatever",
                content="whatever",
                forged=orjson.dumps(forged).decode(),
            )

            # Only pass the 'sender' property when doing mirroring behavior.
            if forged:
                payload["sender"] = sender_email

            cordelia.can_forge_sender = False
            cordelia.save()

            result = self.api_post(cordelia, "/api/v1/messages", payload)
            self.assert_json_error_contains(result, "authorized")

            cordelia.can_forge_sender = True
            cordelia.save()

            result = self.api_post(cordelia, "/api/v1/messages", payload)
            self.assert_json_success(result)

        test_with(
            sender_email=cordelia.email,
            client="test suite",
            forged=False,
        )

        test_with(
            sender_email="irc_person@zulip.com",
            client="irc_mirror",
            forged=True,
        )

    def test_bot_can_send_to_owner_stream(self) -> None:
        cordelia = self.example_user("cordelia")
        bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )

        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True)

        payload = dict(
            type="channel",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content="whatever",
        )

        result = self.api_post(bot, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, "Not authorized to send")

        # We subscribe the bot owner! (aka cordelia)
        assert bot.bot_owner is not None
        self.subscribe(bot.bot_owner, stream_name)

        result = self.api_post(bot, "/api/v1/messages", payload)
        self.assert_json_success(result)

    def test_cross_realm_bots_can_use_api_on_own_subdomain(self) -> None:
        # Cross realm bots should use internal_send_*_message, not the API:
        internal_realm = get_realm("zulipinternal")
        notification_bot = self.notification_bot(internal_realm)
        stream = self.make_stream("notify_channel", internal_realm)

        result = self.api_post(
            notification_bot,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": orjson.dumps("notify_channel").decode(),
                "content": "Test message",
                "topic": "Test topic",
            },
            subdomain="zulipinternal",
        )

        self.assert_json_success(result)
        message = self.get_last_message()

        self.assertEqual(message.content, "Test message")
        self.assertEqual(message.sender, notification_bot)
        self.assertEqual(message.recipient.type_id, stream.id)

    def test_guest_user(self) -> None:
        sender = self.example_user("polonius")

        stream_name = "public stream"
        self.make_stream(stream_name, invite_only=False)
        payload = dict(
            type="channel",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content="whatever",
        )

        # Guest user can't send message to unsubscribed public streams
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_error(result, "Not authorized to send to channel 'public stream'")

        self.subscribe(sender, stream_name)
        # Guest user can send message to subscribed public streams
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)


class StreamMessagesTest(ZulipTestCase):
    def assert_stream_message(
        self, stream_name: str, topic_name: str = "test topic", content: str = "test content"
    ) -> None:
        """
        Check that messages sent to a stream reach all subscribers to that stream.
        """
        realm = get_realm("zulip")
        subscribers = self.users_subscribed_to_stream(stream_name, realm)

        # Outgoing webhook bots don't store UserMessage rows; they will be processed later.
        subscribers = [
            subscriber
            for subscriber in subscribers
            if subscriber.bot_type != UserProfile.OUTGOING_WEBHOOK_BOT
        ]

        old_subscriber_messages = list(map(message_stream_count, subscribers))

        non_subscribers = [
            user_profile
            for user_profile in UserProfile.objects.all()
            if user_profile not in subscribers
        ]
        old_non_subscriber_messages = list(map(message_stream_count, non_subscribers))

        non_bot_subscribers = [
            user_profile for user_profile in subscribers if not user_profile.is_bot
        ]
        a_subscriber = non_bot_subscribers[0]
        self.login_user(a_subscriber)
        self.send_stream_message(a_subscriber, stream_name, content=content, topic_name=topic_name)

        # Did all of the subscribers get the message?
        new_subscriber_messages = list(map(message_stream_count, subscribers))

        # Did non-subscribers not get the message?
        new_non_subscriber_messages = list(map(message_stream_count, non_subscribers))

        self.assertEqual(old_non_subscriber_messages, new_non_subscriber_messages)
        self.assertEqual(new_subscriber_messages, [elt + 1 for elt in old_subscriber_messages])

    def test_performance(self) -> None:
        """
        This test is part of the automated test suite, but
        it is more intended as an aid to measuring the
        performance of do_send_messages() with consistent
        data setup across different commits.  You can modify
        the values below and run just this test, and then
        comment out the print statement toward the bottom.
        """
        num_messages = 2
        num_extra_users = 10

        sender = self.example_user("cordelia")
        realm = sender.realm
        message_content = "whatever"
        stream = get_stream("Denmark", realm)
        topic_name = "lunch"
        recipient = stream.recipient
        assert recipient is not None
        sending_client = make_client(name="test suite")

        for i in range(num_extra_users):
            # Make every other user be idle.
            long_term_idle = i % 2 > 0

            email = f"foo{i}@example.com"
            user = UserProfile.objects.create(
                realm=realm,
                email=email,
                delivery_email=email,
                long_term_idle=long_term_idle,
            )
            Subscription.objects.create(
                user_profile=user,
                is_user_active=user.is_active,
                recipient=recipient,
            )

        def send_test_message() -> None:
            message = Message(
                sender=sender,
                recipient=recipient,
                realm=stream.realm,
                content=message_content,
                date_sent=timezone_now(),
                sending_client=sending_client,
            )
            message.set_topic_name(topic_name)
            message_dict = build_message_send_dict(message=message)
            do_send_messages([message_dict])

        before_um_count = UserMessage.objects.count()

        for i in range(num_messages):
            send_test_message()

        after_um_count = UserMessage.objects.count()
        ums_created = after_um_count - before_um_count

        num_active_users = num_extra_users / 2
        self.assertTrue(ums_created > (num_active_users * num_messages))

    def test_not_too_many_queries(self) -> None:
        recipient_list = [
            self.example_user("hamlet"),
            self.example_user("iago"),
            self.example_user("cordelia"),
            self.example_user("othello"),
        ]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_user("hamlet")
        user = self.example_user("othello")
        sending_client = make_client(name="test suite")
        stream_name = "Denmark"
        topic_name = "foo"
        content = "whatever"

        # Note: We don't need to assert the db query count for each possible
        # combination of 'automatically_follow_topics_policy' and 'automatically_unmute_topics_in_muted_streams_policy',
        # as the query count depends only on the actions, i.e., 'ON_INITIATION',
        # 'ON_PARTICIPATION', and 'NEVER', and is independent of the final visibility_policy set.
        # Asserting query count using one of the above-mentioned settings fulfils our purpose.

        # To get accurate count of the queries, we should make sure that
        # caches don't come into play. If we count queries while caches are
        # filled, we will get a lower count. Caches are not supposed to be
        # persistent, so our test can also fail if cache is invalidated
        # during the course of the unit test.
        flush_per_request_caches()
        do_change_user_setting(
            user_profile=sender,
            setting_name="automatically_follow_topics_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER,
            acting_user=None,
        )
        with self.assert_database_query_count(13):
            check_send_stream_message(
                sender=sender,
                client=sending_client,
                stream_name=stream_name,
                topic_name=topic_name,
                body=content,
            )

        do_change_user_setting(
            user_profile=sender,
            setting_name="automatically_follow_topics_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION,
            acting_user=None,
        )
        # There will be an increase in the query count of 5 while sending
        # the first message to a topic.
        # 5 queries: 1 to check if it is the first message in the topic +
        # 1 to check if the topic is already followed + 3 to follow the topic.
        flush_per_request_caches()
        with self.assert_database_query_count(18):
            check_send_stream_message(
                sender=sender,
                client=sending_client,
                stream_name=stream_name,
                topic_name="new topic",
                body=content,
            )

        do_change_user_setting(
            user_profile=sender,
            setting_name="automatically_follow_topics_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION,
            acting_user=None,
        )
        self.send_stream_message(self.example_user("iago"), stream_name, "Hello", "topic 2")
        # There will be an increase in the query count of 4 while sending
        # a message to a topic with visibility policy other than FOLLOWED.
        # 1 to check if the topic is already followed + 3 queries to follow the topic.
        flush_per_request_caches()
        with self.assert_database_query_count(17):
            check_send_stream_message(
                sender=sender,
                client=sending_client,
                stream_name=stream_name,
                topic_name="topic 2",
                body=content,
            )
        # If the topic is already FOLLOWED, there will be an increase in the query
        # count of 1 to check if the topic is already followed.
        flush_per_request_caches()
        with self.assert_database_query_count(14):
            check_send_stream_message(
                sender=sender,
                client=sending_client,
                stream_name=stream_name,
                topic_name="topic 2",
                body=content,
            )

        realm = get_realm("zulip")
        subscribers = self.users_subscribed_to_stream(stream_name, realm)

        for user in subscribers:
            do_change_user_setting(
                user_profile=user,
                setting_name="automatically_follow_topics_where_mentioned",
                setting_value=True,
                acting_user=None,
            )
        # There will be an increase in the query count of 5 while sending
        # a message with a mention to a topic if visibility policy for the
        # mentioned user is other than FOLLOWED.
        # 1 to get the user_id of the mentioned user + 1 to check if the topic
        # is already followed + 3 queries to follow the topic.
        flush_per_request_caches()
        with self.assert_database_query_count(22):
            check_send_stream_message(
                sender=sender,
                client=sending_client,
                stream_name=stream_name,
                topic_name="topic 2",
                body="@**" + user.full_name + "**",
            )
        # If the topic is already FOLLOWED, there will be an increase in the query
        # count of 2.
        # 1 to get the user_id of the mentioned user + 1 to check if the topic is
        # already followed.
        flush_per_request_caches()
        with self.assert_database_query_count(19):
            check_send_stream_message(
                sender=sender,
                client=sending_client,
                stream_name=stream_name,
                topic_name="topic 2",
                body="@**" + user.full_name + "**",
            )

        flush_per_request_caches()
        with self.assert_database_query_count(16):
            check_send_stream_message(
                sender=sender,
                client=sending_client,
                stream_name=stream_name,
                topic_name="topic 2",
                body="@**all**",
            )

    def test_stream_message_dict(self) -> None:
        user_profile = self.example_user("iago")
        self.subscribe(user_profile, "Denmark")
        self.send_stream_message(
            self.example_user("hamlet"), "Denmark", content="whatever", topic_name="my topic"
        )
        message = most_recent_message(user_profile)
        dct = MessageDict.ids_to_dict([message.id])[0]
        MessageDict.post_process_dicts(
            [dct],
            apply_markdown=True,
            client_gravatar=False,
            realm=user_profile.realm,
        )
        self.assertEqual(dct["display_recipient"], "Denmark")

        stream = get_stream("Denmark", user_profile.realm)
        self.assertEqual(dct["stream_id"], stream.id)

    def test_stream_message_unicode(self) -> None:
        receiving_user_profile = self.example_user("iago")
        sender = self.example_user("hamlet")
        self.subscribe(receiving_user_profile, "Denmark")
        self.send_stream_message(sender, "Denmark", content="whatever", topic_name="my topic")
        message = most_recent_message(receiving_user_profile)
        self.assertEqual(
            repr(message),
            f"<Message: Denmark / my topic / <UserProfile: {sender.email} {sender.realm!r}>>",
        )

    def test_message_mentions(self) -> None:
        user_profile = self.example_user("iago")
        self.subscribe(user_profile, "Denmark")
        self.send_stream_message(
            self.example_user("hamlet"), "Denmark", content="test @**Iago** rules"
        )
        message = most_recent_message(user_profile)
        assert UserMessage.objects.get(
            user_profile=user_profile, message=message
        ).flags.mentioned.is_set

    def test_is_private_flag(self) -> None:
        user_profile = self.example_user("iago")
        self.subscribe(user_profile, "Denmark")

        self.send_stream_message(self.example_user("hamlet"), "Denmark", content="test")
        message = most_recent_message(user_profile)
        self.assertFalse(
            UserMessage.objects.get(
                user_profile=user_profile, message=message
            ).flags.is_private.is_set
        )

        self.send_personal_message(self.example_user("hamlet"), user_profile, content="test")
        message = most_recent_message(user_profile)
        self.assertTrue(
            UserMessage.objects.get(
                user_profile=user_profile, message=message
            ).flags.is_private.is_set
        )

    def _send_stream_message(self, user: UserProfile, stream_name: str, content: str) -> Set[int]:
        with self.capture_send_event_calls(expected_num_events=1) as events:
            self.send_stream_message(
                user,
                stream_name,
                content=content,
            )
        users = events[0]["users"]
        user_ids = {u["id"] for u in users}
        return user_ids

    def test_unsub_mention(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        stream_name = "Test stream"

        self.subscribe(hamlet, stream_name)

        UserMessage.objects.filter(
            user_profile=cordelia,
        ).delete()

        def mention_cordelia() -> Set[int]:
            content = "test @**Cordelia, Lear's daughter** rules"

            user_ids = self._send_stream_message(
                user=hamlet,
                stream_name=stream_name,
                content=content,
            )
            return user_ids

        def num_cordelia_messages() -> int:
            return UserMessage.objects.filter(
                user_profile=cordelia,
            ).count()

        user_ids = mention_cordelia()
        self.assertEqual(0, num_cordelia_messages())
        self.assertNotIn(cordelia.id, user_ids)

        # Make sure test isn't too brittle-subscribing
        # Cordelia and mentioning her should give her a
        # message.
        self.subscribe(cordelia, stream_name)
        user_ids = mention_cordelia()
        self.assertIn(cordelia.id, user_ids)
        self.assertEqual(1, num_cordelia_messages())

    def test_message_bot_mentions(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        stream_name = "Test stream"

        self.subscribe(hamlet, stream_name)

        normal_bot = do_create_user(
            email="normal-bot@zulip.com",
            password="",
            realm=realm,
            full_name="Normal Bot",
            bot_type=UserProfile.DEFAULT_BOT,
            bot_owner=cordelia,
            acting_user=None,
        )

        content = "test @**Normal Bot** rules"

        user_ids = self._send_stream_message(
            user=hamlet,
            stream_name=stream_name,
            content=content,
        )

        self.assertIn(normal_bot.id, user_ids)
        user_message = most_recent_usermessage(normal_bot)
        self.assertEqual(user_message.message.content, content)
        self.assertTrue(user_message.flags.mentioned)

    def send_and_verify_topic_wildcard_mention_message(
        self, sender_name: str, test_fails: bool = False, topic_participant_count: int = 20
    ) -> None:
        sender = self.example_user(sender_name)
        content = "@**topic** test topic wildcard mention"
        participants_user_ids = set(range(topic_participant_count))
        with mock.patch(
            "zerver.actions.message_send.participants_for_topic", return_value=participants_user_ids
        ):
            if not test_fails:
                msg_id = self.send_stream_message(sender, "test_stream", content)
                result = self.api_get(sender, "/api/v1/messages/" + str(msg_id))
                self.assert_json_success(result)

            else:
                with self.assertRaisesRegex(
                    JsonableError,
                    "You do not have permission to use topic wildcard mentions in this topic.",
                ):
                    self.send_stream_message(sender, "test_stream", content)

    def test_topic_wildcard_mention_restrictions(self) -> None:
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        polonius = self.example_user("polonius")
        shiva = self.example_user("shiva")
        realm = cordelia.realm

        stream_name = "test_stream"
        self.subscribe(cordelia, stream_name)
        self.subscribe(iago, stream_name)
        self.subscribe(polonius, stream_name)
        self.subscribe(shiva, stream_name)

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_EVERYONE,
            acting_user=None,
        )
        self.send_and_verify_topic_wildcard_mention_message("polonius")

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_MEMBERS,
            acting_user=None,
        )
        self.send_and_verify_topic_wildcard_mention_message("polonius", test_fails=True)
        # There is no restriction on topics with less than 'Realm.WILDCARD_MENTION_THRESHOLD' participants.
        self.send_and_verify_topic_wildcard_mention_message("polonius", topic_participant_count=10)
        self.send_and_verify_topic_wildcard_mention_message("cordelia")

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_FULL_MEMBERS,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        iago.date_joined = timezone_now()
        iago.save()
        shiva.date_joined = timezone_now()
        shiva.save()
        cordelia.date_joined = timezone_now()
        cordelia.save()
        self.send_and_verify_topic_wildcard_mention_message("cordelia", test_fails=True)
        self.send_and_verify_topic_wildcard_mention_message("cordelia", topic_participant_count=10)
        # Administrators and moderators can use wildcard mentions even if they are new.
        self.send_and_verify_topic_wildcard_mention_message("iago")
        self.send_and_verify_topic_wildcard_mention_message("shiva")

        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        self.send_and_verify_topic_wildcard_mention_message("cordelia")

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_MODERATORS,
            acting_user=None,
        )
        self.send_and_verify_topic_wildcard_mention_message("cordelia", test_fails=True)
        self.send_and_verify_topic_wildcard_mention_message("cordelia", topic_participant_count=10)
        self.send_and_verify_topic_wildcard_mention_message("shiva")

        cordelia.date_joined = timezone_now()
        cordelia.save()
        do_set_realm_property(
            realm, "wildcard_mention_policy", Realm.WILDCARD_MENTION_POLICY_ADMINS, acting_user=None
        )
        self.send_and_verify_topic_wildcard_mention_message("shiva", test_fails=True)
        # There is no restriction on topics with less than 'Realm.WILDCARD_MENTION_THRESHOLD' participants.
        self.send_and_verify_topic_wildcard_mention_message("shiva", topic_participant_count=10)
        self.send_and_verify_topic_wildcard_mention_message("iago")

        do_set_realm_property(
            realm, "wildcard_mention_policy", Realm.WILDCARD_MENTION_POLICY_NOBODY, acting_user=None
        )
        self.send_and_verify_topic_wildcard_mention_message("iago", test_fails=True)
        self.send_and_verify_topic_wildcard_mention_message("iago", topic_participant_count=10)

    def send_and_verify_stream_wildcard_mention_message(
        self, sender_name: str, test_fails: bool = False, sub_count: int = 16
    ) -> None:
        sender = self.example_user(sender_name)
        content = "@**all** test stream wildcard mention"
        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=sub_count):
            if not test_fails:
                msg_id = self.send_stream_message(sender, "test_stream", content)
                result = self.api_get(sender, "/api/v1/messages/" + str(msg_id))
                self.assert_json_success(result)

            else:
                with self.assertRaisesRegex(
                    JsonableError,
                    "You do not have permission to use channel wildcard mentions in this channel.",
                ):
                    self.send_stream_message(sender, "test_stream", content)

    def test_stream_wildcard_mention_restrictions(self) -> None:
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        polonius = self.example_user("polonius")
        shiva = self.example_user("shiva")
        realm = cordelia.realm

        stream_name = "test_stream"
        self.subscribe(cordelia, stream_name)
        self.subscribe(iago, stream_name)
        self.subscribe(polonius, stream_name)
        self.subscribe(shiva, stream_name)

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_EVERYONE,
            acting_user=None,
        )
        self.send_and_verify_stream_wildcard_mention_message("polonius")

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_MEMBERS,
            acting_user=None,
        )
        self.send_and_verify_stream_wildcard_mention_message("polonius", test_fails=True)
        # There is no restriction on small streams.
        self.send_and_verify_stream_wildcard_mention_message("polonius", sub_count=10)
        self.send_and_verify_stream_wildcard_mention_message("cordelia")

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_FULL_MEMBERS,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        iago.date_joined = timezone_now()
        iago.save()
        shiva.date_joined = timezone_now()
        shiva.save()
        cordelia.date_joined = timezone_now()
        cordelia.save()
        self.send_and_verify_stream_wildcard_mention_message("cordelia", test_fails=True)
        self.send_and_verify_stream_wildcard_mention_message("cordelia", sub_count=10)
        # Administrators and moderators can use wildcard mentions even if they are new.
        self.send_and_verify_stream_wildcard_mention_message("iago")
        self.send_and_verify_stream_wildcard_mention_message("shiva")

        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        self.send_and_verify_stream_wildcard_mention_message("cordelia")

        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_MODERATORS,
            acting_user=None,
        )
        self.send_and_verify_stream_wildcard_mention_message("cordelia", test_fails=True)
        self.send_and_verify_stream_wildcard_mention_message("cordelia", sub_count=10)
        self.send_and_verify_stream_wildcard_mention_message("shiva")

        cordelia.date_joined = timezone_now()
        cordelia.save()
        do_set_realm_property(
            realm, "wildcard_mention_policy", Realm.WILDCARD_MENTION_POLICY_ADMINS, acting_user=None
        )
        self.send_and_verify_stream_wildcard_mention_message("shiva", test_fails=True)
        # There is no restriction on small streams.
        self.send_and_verify_stream_wildcard_mention_message("shiva", sub_count=10)
        self.send_and_verify_stream_wildcard_mention_message("iago")

        do_set_realm_property(
            realm, "wildcard_mention_policy", Realm.WILDCARD_MENTION_POLICY_NOBODY, acting_user=None
        )
        self.send_and_verify_stream_wildcard_mention_message("iago", test_fails=True)
        self.send_and_verify_stream_wildcard_mention_message("iago", sub_count=10)

    def test_topic_wildcard_mentioned_flag(self) -> None:
        # For topic wildcard mentions, the 'topic_wildcard_mentioned' flag should be
        # set for all the user messages for topic participants, irrespective of
        # their notifications settings.
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        for user_profile in [cordelia, hamlet, iago]:
            self.subscribe(user_profile, "Denmark")

        #   user   | topic participant |  wildcard_mentions_notify setting
        # -------- | ----------------- | ----------------------------------
        # cordelia |        YES        |                True
        #  hamlet  |        YES        |                False
        #   iago   |        NO         |                True
        self.send_stream_message(cordelia, "Denmark", content="test", topic_name="topic-1")
        do_change_user_setting(cordelia, "wildcard_mentions_notify", True, acting_user=None)
        self.send_stream_message(hamlet, "Denmark", content="Hi @**topic**", topic_name="topic-1")
        message = most_recent_message(cordelia)
        self.assertTrue(
            UserMessage.objects.get(
                user_profile=cordelia, message=message
            ).flags.topic_wildcard_mentioned.is_set
        )

        self.send_stream_message(hamlet, "Denmark", content="test", topic_name="topic-2")
        do_change_user_setting(hamlet, "wildcard_mentions_notify", False, acting_user=None)
        self.send_stream_message(cordelia, "Denmark", content="Hi @**topic**", topic_name="topic-2")
        message = most_recent_message(hamlet)
        self.assertTrue(
            UserMessage.objects.get(
                user_profile=hamlet, message=message
            ).flags.topic_wildcard_mentioned.is_set
        )

        do_change_user_setting(iago, "wildcard_mentions_notify", True, acting_user=None)
        self.send_stream_message(hamlet, "Denmark", content="Hi @**topic**", topic_name="topic-3")
        message = most_recent_message(iago)
        self.assertFalse(
            UserMessage.objects.get(
                user_profile=iago, message=message
            ).flags.topic_wildcard_mentioned.is_set
        )

    def test_invalid_wildcard_mention_policy(self) -> None:
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        self.subscribe(cordelia, "test_stream")
        do_set_realm_property(cordelia.realm, "wildcard_mention_policy", 10, acting_user=None)
        content = "@**all** test wildcard mention"
        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=16):
            with self.assertRaisesRegex(AssertionError, "Invalid wildcard mention policy"):
                self.send_stream_message(cordelia, "test_stream", content)

    def test_user_group_mention_restrictions(self) -> None:
        iago = self.example_user("iago")
        shiva = self.example_user("shiva")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.subscribe(iago, "test_stream")
        self.subscribe(shiva, "test_stream")
        self.subscribe(othello, "test_stream")
        self.subscribe(cordelia, "test_stream")

        leadership = check_add_user_group(othello.realm, "leadership", [othello], acting_user=None)
        support = check_add_user_group(othello.realm, "support", [othello], acting_user=None)

        moderators_system_group = NamedUserGroup.objects.get(
            realm=iago.realm, name=SystemGroups.MODERATORS, is_system_group=True
        )

        content = "Test mentioning user group @*leadership*"
        msg_id = self.send_stream_message(cordelia, "test_stream", content)
        result = self.api_get(cordelia, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

        leadership.can_mention_group = moderators_system_group
        leadership.save()
        with self.assertRaisesRegex(
            JsonableError,
            f"You are not allowed to mention user group '{leadership.name}'. You must be a member of '{moderators_system_group.name}' to mention this group.",
        ):
            self.send_stream_message(cordelia, "test_stream", content)

        # The restriction does not apply on silent mention.
        content = "Test mentioning user group @_*leadership*"
        msg_id = self.send_stream_message(cordelia, "test_stream", content)
        result = self.api_get(cordelia, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

        content = "Test mentioning user group @*leadership*"
        msg_id = self.send_stream_message(shiva, "test_stream", content)
        result = self.api_get(shiva, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

        msg_id = self.send_stream_message(iago, "test_stream", content)
        result = self.api_get(iago, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

        test = check_add_user_group(shiva.realm, "test", [shiva], acting_user=None)
        add_subgroups_to_user_group(leadership, [test], acting_user=None)
        support.can_mention_group = leadership
        support.save()

        content = "Test mentioning user group @*support*"
        with self.assertRaisesRegex(
            JsonableError,
            f"You are not allowed to mention user group '{support.name}'. You must be a member of '{leadership.name}' to mention this group.",
        ):
            self.send_stream_message(iago, "test_stream", content)

        msg_id = self.send_stream_message(othello, "test_stream", content)
        result = self.api_get(othello, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

        msg_id = self.send_stream_message(shiva, "test_stream", content)
        result = self.api_get(shiva, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

        content = "Test mentioning user group @*support* @*leadership*"
        with self.assertRaisesRegex(
            JsonableError,
            f"You are not allowed to mention user group '{support.name}'. You must be a member of '{leadership.name}' to mention this group.",
        ):
            self.send_stream_message(iago, "test_stream", content)

        with self.assertRaisesRegex(
            JsonableError,
            f"You are not allowed to mention user group '{leadership.name}'. You must be a member of '{moderators_system_group.name}' to mention this group.",
        ):
            self.send_stream_message(othello, "test_stream", content)

        msg_id = self.send_stream_message(shiva, "test_stream", content)
        result = self.api_get(shiva, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

        # Test system bots.
        content = "Test mentioning user group @*support*"
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=iago.realm, is_system_group=True
        )
        support.can_mention_group = members_group
        support.save()

        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        system_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT, internal_realm.id)
        with self.assertRaisesRegex(
            JsonableError,
            f"You are not allowed to mention user group '{support.name}'. You must be a member of '{members_group.name}' to mention this group.",
        ):
            self.send_stream_message(system_bot, "test_stream", content, recipient_realm=iago.realm)

        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=iago.realm, is_system_group=True
        )
        support.can_mention_group = everyone_group
        support.save()

        msg_id = self.send_stream_message(
            system_bot, "test_stream", content, recipient_realm=iago.realm
        )
        result = self.api_get(shiva, "/api/v1/messages/" + str(msg_id))
        self.assert_json_success(result)

    def test_stream_message_mirroring(self) -> None:
        user = self.mit_user("starnine")
        self.subscribe(user, "Verona")

        do_change_can_forge_sender(user, True)
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": orjson.dumps("Verona").decode(),
                "sender": self.mit_email("sipbtest"),
                "client": "zephyr_mirror",
                "topic": "announcement",
                "content": "Everyone knows Iago rules",
                "forged": "true",
            },
            subdomain="zephyr",
        )
        self.assert_json_success(result)

        do_change_can_forge_sender(user, False)
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "channel",
                "to": "Verona",
                "sender": self.mit_email("sipbtest"),
                "client": "zephyr_mirror",
                "topic": "announcement",
                "content": "Everyone knows Iago rules",
                "forged": "true",
            },
            subdomain="zephyr",
        )
        self.assert_json_error(result, "User not authorized for this query")

    def test_message_to_stream(self) -> None:
        """
        If you send a message to a stream, everyone subscribed to the stream
        receives the messages.
        """
        self.assert_stream_message("Scotland")

    def test_non_ascii_stream_message(self) -> None:
        """
        Sending a stream message containing non-ASCII characters in the stream
        name, topic, or message body succeeds.
        """
        self.login("hamlet")

        # Subscribe everyone to a stream with non-ASCII characters.
        non_ascii_stream_name = "hümbüǵ"
        realm = get_realm("zulip")
        stream = self.make_stream(non_ascii_stream_name)
        for user_profile in UserProfile.objects.filter(is_active=True, is_bot=False, realm=realm)[
            0:3
        ]:
            self.subscribe(user_profile, stream.name)

        self.assert_stream_message(non_ascii_stream_name, topic_name="hümbüǵ", content="hümbüǵ")

    def test_get_raw_unread_data_for_huddle_messages(self) -> None:
        users = [
            self.example_user("hamlet"),
            self.example_user("cordelia"),
            self.example_user("iago"),
            self.example_user("prospero"),
            self.example_user("othello"),
        ]

        message1_id = self.send_huddle_message(users[0], users, "test content 1")
        message2_id = self.send_huddle_message(users[0], users, "test content 2")

        msg_data = get_raw_unread_data(users[1])

        # both the messages are present in msg_data
        self.assertIn(message1_id, msg_data["huddle_dict"].keys())
        self.assertIn(message2_id, msg_data["huddle_dict"].keys())

        # only these two messages are present in msg_data
        self.assert_length(msg_data["huddle_dict"].keys(), 2)

        recent_conversations = get_recent_private_conversations(users[1])
        [recent_conversation] = recent_conversations.values()
        self.assertEqual(
            set(recent_conversation["user_ids"]), {user.id for user in users if user != users[1]}
        )
        self.assertEqual(recent_conversation["max_message_id"], message2_id)


class PersonalMessageSendTest(ZulipTestCase):
    def test_personal_to_self(self) -> None:
        """
        If you send a personal to yourself, only you see it.
        """
        old_user_profiles = list(UserProfile.objects.all())
        test_email = self.nonreg_email("test1")
        self.register(test_email, "test1")

        old_messages = list(map(message_stream_count, old_user_profiles))

        user_profile = self.nonreg_user("test1")
        self.send_personal_message(user_profile, user_profile)

        new_messages = list(map(message_stream_count, old_user_profiles))
        self.assertEqual(old_messages, new_messages)

        user_profile = self.nonreg_user("test1")
        recipient = Recipient.objects.get(type_id=user_profile.id, type=Recipient.PERSONAL)
        self.assertEqual(most_recent_message(user_profile).recipient, recipient)

    def assert_personal(
        self, sender: UserProfile, receiver: UserProfile, content: str = "testcontent"
    ) -> None:
        """
        Send a direct message from `sender_email` to `receiver_email` and check
        that only those two parties actually received the message.
        """
        sender_messages = message_stream_count(sender)
        receiver_messages = message_stream_count(receiver)

        other_user_profiles = UserProfile.objects.filter(~Q(id=sender.id) & ~Q(id=receiver.id))
        old_other_messages = list(map(message_stream_count, other_user_profiles))

        self.send_personal_message(sender, receiver, content)

        # Users outside the conversation don't get the message.
        new_other_messages = list(map(message_stream_count, other_user_profiles))
        self.assertEqual(old_other_messages, new_other_messages)

        # The personal message is in the streams of both the sender and receiver.
        self.assertEqual(message_stream_count(sender), sender_messages + 1)
        self.assertEqual(message_stream_count(receiver), receiver_messages + 1)

        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        self.assertEqual(most_recent_message(sender).recipient, recipient)
        self.assertEqual(most_recent_message(receiver).recipient, recipient)

    def test_personal(self) -> None:
        """
        If you send a personal, only you and the recipient see it.
        """
        self.login("hamlet")
        self.assert_personal(
            sender=self.example_user("hamlet"),
            receiver=self.example_user("othello"),
        )

    def test_private_message_policy(self) -> None:
        """
        Tests that PRIVATE_MESSAGE_POLICY_DISABLED works correctly.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        do_set_realm_property(
            user_profile.realm,
            "private_message_policy",
            Realm.PRIVATE_MESSAGE_POLICY_DISABLED,
            acting_user=None,
        )
        with self.assertRaises(JsonableError):
            self.send_personal_message(user_profile, self.example_user("cordelia"))

        bot_profile = self.create_test_bot("testbot", user_profile)
        notification_bot = get_system_bot("notification-bot@zulip.com", user_profile.realm_id)
        self.send_personal_message(user_profile, notification_bot)
        self.send_personal_message(user_profile, bot_profile)
        self.send_personal_message(bot_profile, user_profile)

    def test_non_ascii_personal(self) -> None:
        """
        Sending a direct message containing non-ASCII characters succeeds.
        """
        self.login("hamlet")
        self.assert_personal(
            sender=self.example_user("hamlet"),
            receiver=self.example_user("othello"),
            content="hümbüǵ",
        )


class ExtractTest(ZulipTestCase):
    def test_extract_stream_indicator(self) -> None:
        self.assertEqual(
            extract_stream_indicator("development"),
            "development",
        )
        self.assertEqual(
            extract_stream_indicator("commas,are,fine"),
            "commas,are,fine",
        )
        self.assertEqual(
            extract_stream_indicator('"Who hasn\'t done this?"'),
            "Who hasn't done this?",
        )
        self.assertEqual(
            extract_stream_indicator("999"),
            999,
        )

        # For legacy reasons it's plausible that users will
        # put a single stream into an array and then encode it
        # as JSON.  We can probably eliminate this support
        # by mid 2020 at the latest.
        self.assertEqual(
            extract_stream_indicator('["social"]'),
            "social",
        )

        self.assertEqual(
            extract_stream_indicator("[123]"),
            123,
        )

        with self.assertRaisesRegex(JsonableError, "Invalid data type for channel"):
            extract_stream_indicator("{}")

        with self.assertRaisesRegex(JsonableError, "Invalid data type for channel"):
            extract_stream_indicator("[{}]")

        with self.assertRaisesRegex(JsonableError, "Expected exactly one channel"):
            extract_stream_indicator('[1,2,"general"]')

    def test_extract_private_recipients_emails(self) -> None:
        # JSON list w/dups, empties, and trailing whitespace
        s = orjson.dumps([" alice@zulip.com ", " bob@zulip.com ", "   ", "bob@zulip.com"]).decode()
        # sorted() gets confused by extract_private_recipients' return type
        # For testing, ignorance here is better than manual casting
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, ["alice@zulip.com", "bob@zulip.com"])

        # simple string with one name
        s = "alice@zulip.com    "
        self.assertEqual(extract_private_recipients(s), ["alice@zulip.com"])

        # JSON-encoded string
        s = '"alice@zulip.com"'
        self.assertEqual(extract_private_recipients(s), ["alice@zulip.com"])

        # bare comma-delimited string
        s = "bob@zulip.com, alice@zulip.com"
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, ["alice@zulip.com", "bob@zulip.com"])

        # JSON-encoded, comma-delimited string
        s = '"bob@zulip.com,alice@zulip.com"'
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, ["alice@zulip.com", "bob@zulip.com"])

        # Invalid data
        s = orjson.dumps(dict(color="red")).decode()
        with self.assertRaisesRegex(JsonableError, "Invalid data type for recipients"):
            extract_private_recipients(s)

        s = orjson.dumps([{}]).decode()
        with self.assertRaisesRegex(JsonableError, "Invalid data type for recipients"):
            extract_private_recipients(s)

        # Empty list
        self.assertEqual(extract_private_recipients("[]"), [])

        # Heterogeneous lists are not supported
        mixed = orjson.dumps(["eeshan@example.com", 3, 4]).decode()
        with self.assertRaisesRegex(
            JsonableError, "Recipient lists may contain emails or user IDs, but not both."
        ):
            extract_private_recipients(mixed)

    def test_extract_recipient_ids(self) -> None:
        # JSON list w/dups
        s = orjson.dumps([3, 3, 12]).decode()
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, [3, 12])

        # Invalid data
        ids = orjson.dumps(dict(recipient=12)).decode()
        with self.assertRaisesRegex(JsonableError, "Invalid data type for recipients"):
            extract_private_recipients(ids)

        # Heterogeneous lists are not supported
        mixed = orjson.dumps([3, 4, "eeshan@example.com"]).decode()
        with self.assertRaisesRegex(
            JsonableError, "Recipient lists may contain emails or user IDs, but not both."
        ):
            extract_private_recipients(mixed)


class InternalPrepTest(ZulipTestCase):
    def test_returns_for_internal_sends(self) -> None:
        # For our internal_send_* functions we return
        # if the prep stages fail.  This is mostly defensive
        # code, since we are generally creating the messages
        # ourselves, but we want to make sure that the functions
        # won't actually explode if we give them bad content.
        bad_content = ""
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        stream = get_stream("Verona", realm)

        with self.assertLogs(level="ERROR") as m:
            internal_send_private_message(
                sender=cordelia,
                recipient_user=hamlet,
                content=bad_content,
            )

        self.assertEqual(
            m.output[0].split("\n")[0],
            "ERROR:root:Error queueing internal message by {}: {}".format(
                "cordelia@zulip.com", "Message must not be empty"
            ),
        )

        with self.assertLogs(level="ERROR") as m:
            internal_send_huddle_message(
                realm=realm,
                sender=cordelia,
                emails=[hamlet.email, othello.email],
                content=bad_content,
            )

        self.assertEqual(
            m.output[0].split("\n")[0],
            "ERROR:root:Error queueing internal message by {}: {}".format(
                "cordelia@zulip.com", "Message must not be empty"
            ),
        )

        with self.assertLogs(level="ERROR") as m:
            internal_send_stream_message(
                sender=cordelia,
                topic_name="whatever",
                content=bad_content,
                stream=stream,
            )

        self.assertEqual(
            m.output[0].split("\n")[0],
            "ERROR:root:Error queueing internal message by {}: {}".format(
                "cordelia@zulip.com", "Message must not be empty"
            ),
        )

        with self.assertLogs(level="ERROR") as m:
            internal_send_stream_message_by_name(
                realm=realm,
                sender=cordelia,
                stream_name=stream.name,
                topic_name="whatever",
                content=bad_content,
            )

        self.assertEqual(
            m.output[0].split("\n")[0],
            "ERROR:root:Error queueing internal message by {}: {}".format(
                "cordelia@zulip.com", "Message must not be empty"
            ),
        )

    def test_error_handling(self) -> None:
        sender = self.example_user("cordelia")
        recipient_user = self.example_user("hamlet")
        MAX_MESSAGE_LENGTH = settings.MAX_MESSAGE_LENGTH
        content = "x" * (MAX_MESSAGE_LENGTH + 10)

        result = internal_prep_private_message(
            sender=sender, recipient_user=recipient_user, content=content
        )
        assert result is not None
        message = result.message
        self.assertIn("message truncated", message.content)

        # Simulate sending a message to somebody not in the
        # realm of the sender.
        recipient_user = self.mit_user("starnine")
        with self.assertLogs(level="ERROR") as m:
            result = internal_prep_private_message(
                sender=sender, recipient_user=recipient_user, content=content
            )

        self.assertEqual(
            m.output[0].split("\n")[0],
            "ERROR:root:Error queueing internal message by {}: {}".format(
                "cordelia@zulip.com",
                "You can't send direct messages outside of your organization.",
            ),
        )

    def test_ensure_stream_gets_called(self) -> None:
        realm = get_realm("zulip")
        sender = self.example_user("cordelia")
        stream_name = "test_stream"
        topic_name = "whatever"
        content = "hello"

        internal_prep_stream_message_by_name(
            realm=realm,
            sender=sender,
            stream_name=stream_name,
            topic_name=topic_name,
            content=content,
        )

        # This would throw an error if the stream
        # wasn't automatically created.
        Stream.objects.get(name=stream_name, realm_id=realm.id)

    def test_direct_message_to_self_and_bot_in_dm_disabled_org(self) -> None:
        """
        Test that a user can send a direct message to themselves and to a bot in a DM disabled organization
        """
        sender = self.example_user("hamlet")
        sender.realm.private_message_policy = Realm.PRIVATE_MESSAGE_POLICY_DISABLED
        sender.realm.save()

        #  Create a non-bot user
        recipient_user = self.example_user("othello")
        recipient_user.realm = sender.realm

        # Create a new bot user
        bot = do_create_user(
            email="test-bot@zulip.com",
            password="",
            realm=sender.realm,
            full_name="Test Bot",
            bot_type=UserProfile.DEFAULT_BOT,
            bot_owner=sender,
            acting_user=None,
        )

        # Test sending a message to self
        result = self.api_post(
            sender,
            "/api/v1/messages",
            {
                "type": "private",
                "to": orjson.dumps([sender.id]).decode(),
                "content": "Test message to self",
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        expected = "Test message to self"
        self.assertEqual(msg.content, expected)

        # Test sending a message to non-bot user
        result = self.api_post(
            sender,
            "/api/v1/messages",
            {
                "type": "private",
                "to": orjson.dumps([recipient_user.id]).decode(),
                "content": "Test message",
            },
        )
        self.assert_json_error(result, "Direct messages are disabled in this organization.")

        # Test sending a message to the bot
        result = self.api_post(
            sender,
            "/api/v1/messages",
            {
                "type": "private",
                "to": orjson.dumps([bot.id]).decode(),
                "content": "Test message to bot",
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        expected = "Test message to bot"
        self.assertEqual(msg.content, expected)


class TestCrossRealmPMs(ZulipTestCase):
    def make_realm(self, domain: str) -> Realm:
        realm = do_create_realm(string_id=domain, name=domain)
        do_set_realm_property(realm, "invite_required", False, acting_user=None)
        RealmDomain.objects.create(realm=realm, domain=domain)
        return realm

    def create_user(self, email: str) -> UserProfile:
        subdomain = Address(addr_spec=email).domain
        self.register(email, "test", subdomain=subdomain)
        # self.register has the side-effect of ending up with a logged in session
        # for the new user. We don't want that in these tests.
        self.logout()

        return get_user(email, get_realm(subdomain))

    @override_settings(
        CROSS_REALM_BOT_EMAILS=[
            "notification-bot@zulip.com",
            "welcome-bot@zulip.com",
            "support@3.example.com",
        ]
    )
    def test_realm_scenarios(self) -> None:
        self.make_realm("1.example.com")
        r2 = self.make_realm("2.example.com")
        self.make_realm("3.example.com")

        def assert_message_received(to_user: UserProfile, from_user: UserProfile) -> None:
            messages = get_user_messages(to_user)
            self.assertEqual(messages[-1].sender.id, from_user.id)

        def assert_invalid_user() -> Any:
            return self.assertRaisesRegex(JsonableError, "Invalid user ID ")

        user1_email = "user1@1.example.com"
        user1a_email = "user1a@1.example.com"
        user2_email = "user2@2.example.com"
        user3_email = "user3@3.example.com"
        notification_bot_email = "notification-bot@zulip.com"
        support_email = "support@3.example.com"  # note: not zulip.com

        user1 = self.create_user(user1_email)
        user1a = self.create_user(user1a_email)
        user2 = self.create_user(user2_email)
        user3 = self.create_user(user3_email)

        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        notification_bot = get_system_bot(notification_bot_email, internal_realm.id)
        with self.settings(
            CROSS_REALM_BOT_EMAILS=["notification-bot@zulip.com", "welcome-bot@zulip.com"]
        ):
            # HACK: We should probably be creating this "bot" user another
            # way, but since you can't register a user with a
            # cross-realm email, we need to hide this for now.
            support_bot = self.create_user(support_email)

        # Users can send a direct message to themselves.
        self.send_personal_message(user1, user1)
        assert_message_received(user1, user1)

        # Users on the same realm can send direct messages to each other.
        self.send_personal_message(user1, user1a)
        assert_message_received(user1a, user1)

        # Cross-realm bots in the zulip.com realm can send a direct message
        # in any realm.
        # (They need lower level APIs to do this.)
        internal_send_private_message(
            sender=notification_bot,
            recipient_user=get_user(user2_email, r2),
            content="bla",
        )
        assert_message_received(user2, notification_bot)

        # All users can send a direct message to cross-realm bots in the
        # zulip.com realm.
        self.send_personal_message(user1, notification_bot)
        assert_message_received(notification_bot, user1)
        # Verify that internal_send_private_message can also successfully
        # be used.
        internal_send_private_message(
            sender=user2,
            recipient_user=notification_bot,
            content="blabla",
        )
        assert_message_received(notification_bot, user2)
        # Users can send a direct message to cross-realm bots on non-zulip
        # realms.
        # (The support bot represents some theoretical bot that we may
        # create in the future that does not have zulip.com as its realm.)
        self.send_personal_message(user1, support_bot)
        assert_message_received(support_bot, user1)

        # Allow sending direct messages to two different cross-realm bots
        # simultaneously.
        # (We don't particularly need this feature, but since users can
        # already individually send direct messages to cross-realm bots,
        # we shouldn't prevent them from sending multiple bots at once.
        # We may revisit this if it's a nuisance for huddles.)
        self.send_huddle_message(user1, [notification_bot, support_bot])
        assert_message_received(notification_bot, user1)
        assert_message_received(support_bot, user1)

        # Prevent old loophole where I could send direct messages to other
        # users as long as I copied a cross-realm bot from the same realm.
        with assert_invalid_user():
            self.send_huddle_message(user1, [user3, support_bot])

        # Users on three different realms can't send direct messages to
        # each other, even if one of the users is a cross-realm bot.
        with assert_invalid_user():
            self.send_huddle_message(user1, [user2, notification_bot])

        with assert_invalid_user():
            self.send_huddle_message(notification_bot, [user1, user2])

        # Users on the different realms cannot send direct messages to
        # each other.
        with assert_invalid_user():
            self.send_personal_message(user1, user2)

        # Users on non-zulip realms can't send direct messages to
        # "ordinary" Zulip users.
        with assert_invalid_user():
            self.send_personal_message(user1, self.example_user("hamlet"))

        # Users on three different realms cannot send direct messages
        # to each other.
        with assert_invalid_user():
            self.send_huddle_message(user1, [user2, user3])


class TestAddressee(ZulipTestCase):
    def test_addressee_for_user_ids(self) -> None:
        realm = get_realm("zulip")
        user_ids = [
            self.example_user("cordelia").id,
            self.example_user("hamlet").id,
            self.example_user("othello").id,
        ]

        result = Addressee.for_user_ids(user_ids=user_ids, realm=realm)
        user_profiles = result.user_profiles()
        result_user_ids = [user_profiles[0].id, user_profiles[1].id, user_profiles[2].id]

        self.assertEqual(set(result_user_ids), set(user_ids))

    def test_addressee_for_user_ids_nonexistent_id(self) -> None:
        def assert_invalid_user_id() -> Any:
            return self.assertRaisesRegex(JsonableError, "Invalid user ID ")

        with assert_invalid_user_id():
            Addressee.for_user_ids(user_ids=[779], realm=get_realm("zulip"))

    def test_addressee_legacy_build_for_user_ids(self) -> None:
        realm = get_realm("zulip")
        self.login("hamlet")
        user_ids = [self.example_user("cordelia").id, self.example_user("othello").id]

        result = Addressee.legacy_build(
            sender=self.example_user("hamlet"),
            recipient_type_name="private",
            message_to=user_ids,
            topic_name="random_topic",
            realm=realm,
        )
        user_profiles = result.user_profiles()
        result_user_ids = [user_profiles[0].id, user_profiles[1].id]

        self.assertEqual(set(result_user_ids), set(user_ids))

    def test_addressee_legacy_build_for_stream_id(self) -> None:
        realm = get_realm("zulip")
        self.login("iago")
        sender = self.example_user("iago")
        self.subscribe(sender, "Denmark")
        stream = get_stream("Denmark", realm)

        result = Addressee.legacy_build(
            sender=sender,
            recipient_type_name="stream",
            message_to=[stream.id],
            topic_name="random_topic",
            realm=realm,
        )

        stream_id = result.stream_id()
        self.assertEqual(stream.id, stream_id)


class CheckMessageTest(ZulipTestCase):
    def test_basic_check_message_call(self) -> None:
        sender = self.example_user("othello")
        client = make_client(name="test suite")
        stream_name = "España y Francia"
        self.make_stream(stream_name)
        topic_name = "issue"
        message_content = "whatever"
        addressee = Addressee.for_stream_name(stream_name, topic_name)
        ret = check_message(sender, client, addressee, message_content)
        self.assertEqual(ret.message.sender.id, sender.id)

    def test_check_message_normal_user_cant_send_to_stream_in_another_realm(self) -> None:
        mit_user = self.mit_user("sipbtest")

        client = make_client(name="test suite")
        stream = get_stream("Denmark", get_realm("zulip"))
        topic_name = "issue"
        message_content = "whatever"
        addressee = Addressee.for_stream(stream, topic_name)

        with self.assertRaisesRegex(JsonableError, "User not authorized for this query"):
            check_message(
                mit_user,
                client,
                addressee,
                message_content,
            )

    def test_check_message_cant_forge_message_as_other_realm_user(self) -> None:
        """
        Verifies that the .can_forge_sender permission doesn't allow
        forging another realm's user as sender of a message to a stream
        in the forwarder's realm.
        """
        forwarder_user_profile = self.example_user("othello")
        do_change_can_forge_sender(forwarder_user_profile, True)

        mit_user = self.mit_user("sipbtest")
        internal_realm = get_realm("zulipinternal")
        notification_bot = self.notification_bot(internal_realm)

        client = make_client(name="test suite")
        stream = get_stream("Denmark", forwarder_user_profile.realm)
        topic_name = "issue"
        message_content = "whatever"
        addressee = Addressee.for_stream(stream, topic_name)

        with self.assertRaisesRegex(JsonableError, "User not authorized for this query"):
            check_message(
                mit_user,
                client,
                addressee,
                message_content,
                forged=True,
                forwarder_user_profile=forwarder_user_profile,
            )
        with self.assertRaisesRegex(JsonableError, "User not authorized for this query"):
            check_message(
                notification_bot,
                client,
                addressee,
                message_content,
                forged=True,
                forwarder_user_profile=forwarder_user_profile,
            )

    def test_check_message_cant_forge_message_to_stream_in_different_realm(self) -> None:
        """
        Verifies that the .can_forge_sender permission doesn't allow
        forging another realm's user as sender of a message to a stream
        in the forged user's realm..
        """
        forwarder_user_profile = self.example_user("othello")
        do_change_can_forge_sender(forwarder_user_profile, True)

        mit_user = self.mit_user("sipbtest")
        internal_realm = get_realm("zulipinternal")
        notification_bot = self.notification_bot(internal_realm)

        client = make_client(name="test suite")
        stream_name = "España y Francia"
        stream = self.make_stream(stream_name, realm=mit_user.realm)
        self.subscribe(mit_user, stream_name)
        topic_name = "issue"
        message_content = "whatever"
        addressee = Addressee.for_stream(stream, topic_name)

        with self.assertRaisesRegex(JsonableError, "User not authorized for this query"):
            check_message(
                mit_user,
                client,
                addressee,
                message_content,
                forged=True,
                forwarder_user_profile=forwarder_user_profile,
            )
        with self.assertRaisesRegex(JsonableError, "User not authorized for this query"):
            check_message(
                notification_bot,
                client,
                addressee,
                message_content,
                forged=True,
                forwarder_user_profile=forwarder_user_profile,
            )

        # Make sure the special case of sending a message forged as cross-realm bot
        # to a stream in the bot's realm isn't allowed either.
        stream = self.make_stream(stream_name, realm=notification_bot.realm)
        self.subscribe(notification_bot, stream_name)
        addressee = Addressee.for_stream(stream, topic_name)
        with self.assertRaisesRegex(JsonableError, "User not authorized for this query"):
            check_message(
                notification_bot,
                client,
                addressee,
                message_content,
                forged=True,
                forwarder_user_profile=forwarder_user_profile,
            )

    def test_guest_user_can_send_message(self) -> None:
        # Guest users can write to web_public streams.
        sender = self.example_user("polonius")
        client = make_client(name="test suite")
        rome_stream = get_stream("Rome", sender.realm)

        is_sender_subscriber = Subscription.objects.filter(
            user_profile=sender,
            recipient__type_id=rome_stream.id,
        ).exists()
        self.assertFalse(is_sender_subscriber)
        self.assertTrue(rome_stream.is_web_public)

        topic_name = "issue"
        message_content = "whatever"
        addressee = Addressee.for_stream_name(rome_stream.name, topic_name)
        ret = check_message(sender, client, addressee, message_content)
        self.assertEqual(ret.message.sender.id, sender.id)

    def test_bot_pm_feature(self) -> None:
        """We send a direct message to a bot's owner if their bot sends a
        message to an unsubscribed stream"""
        parent = self.example_user("othello")
        bot = do_create_user(
            email="othello-bot@zulip.com",
            password="",
            realm=parent.realm,
            full_name="",
            bot_type=UserProfile.DEFAULT_BOT,
            bot_owner=parent,
            acting_user=None,
        )
        bot.last_reminder = None

        sender = bot
        client = make_client(name="test suite")
        stream_name = "Россия"
        topic_name = "issue"
        addressee = Addressee.for_stream_name(stream_name, topic_name)
        message_content = "whatever"
        old_count = message_stream_count(parent)

        # Try sending to stream that doesn't exist sends a reminder to
        # the sender
        with self.assertRaises(JsonableError):
            check_message(sender, client, addressee, message_content)

        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)
        self.assertIn("that channel does not exist.", most_recent_message(parent).content)

        # Try sending to stream that exists with no subscribers soon
        # after; due to rate-limiting, this should send nothing.
        self.make_stream(stream_name)
        ret = check_message(sender, client, addressee, message_content)
        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)

        # Try sending to stream that exists with no subscribers longer
        # after; this should send an error to the bot owner that the
        # stream doesn't exist
        assert sender.last_reminder is not None
        sender.last_reminder = sender.last_reminder - timedelta(hours=1)
        sender.save(update_fields=["last_reminder"])
        ret = check_message(sender, client, addressee, message_content)

        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 2)
        self.assertEqual(ret.message.sender.email, "othello-bot@zulip.com")
        self.assertIn("does not have any subscribers", most_recent_message(parent).content)

    def test_bot_pm_error_handling(self) -> None:
        # This just test some defensive code.
        cordelia = self.example_user("cordelia")
        test_bot = self.create_test_bot(
            short_name="test",
            user_profile=cordelia,
        )
        content = "whatever"
        good_realm = test_bot.realm
        wrong_realm = get_realm("zephyr")
        wrong_sender = cordelia

        send_rate_limited_pm_notification_to_bot_owner(test_bot, wrong_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

        send_rate_limited_pm_notification_to_bot_owner(wrong_sender, good_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

        test_bot.realm.deactivated = True
        send_rate_limited_pm_notification_to_bot_owner(test_bot, good_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

    def test_no_topic_message(self) -> None:
        realm = get_realm("zulip")
        sender = self.example_user("iago")
        client = make_client(name="test suite")
        stream = get_stream("Denmark", realm)
        topic_name = "(no topic)"
        message_content = "whatever"
        addressee = Addressee.for_stream(stream, topic_name)

        do_set_realm_property(realm, "mandatory_topics", True, acting_user=None)
        realm.refresh_from_db()

        with self.assertRaisesRegex(JsonableError, "Topics are required in this organization"):
            check_message(sender, client, addressee, message_content, realm)

        do_set_realm_property(realm, "mandatory_topics", False, acting_user=None)
        realm.refresh_from_db()
        ret = check_message(sender, client, addressee, message_content, realm)
        self.assertEqual(ret.message.sender.id, sender.id)

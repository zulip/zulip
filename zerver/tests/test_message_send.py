import datetime
from typing import Any, Optional
from unittest import mock

import ujson
from django.http import HttpResponse
from django.utils.timezone import now as timezone_now

from zerver.decorator import JsonableError
from zerver.lib.actions import (
    do_change_stream_post_policy,
    do_create_user,
    do_deactivate_user,
    do_set_realm_property,
    internal_send_stream_message,
)
from zerver.lib.message import get_recent_private_conversations
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import reset_emails_in_zulip_realm
from zerver.lib.timestamp import convert_to_UTC, datetime_to_timestamp
from zerver.lib.timezone import get_timezone
from zerver.models import (
    MAX_MESSAGE_LENGTH,
    MAX_TOPIC_NAME_LENGTH,
    ScheduledMessage,
    Stream,
    UserProfile,
    get_huddle_recipient,
    get_realm,
    get_stream,
    get_system_bot,
    get_user,
)
from zerver.views.message_send import InvalidMirrorInput


class MessagePOSTTest(ZulipTestCase):

    def _send_and_verify_message(self, user: UserProfile, stream_name: str, error_msg: Optional[str]=None) -> None:
        if error_msg is None:
            msg_id = self.send_stream_message(user, stream_name)
            result = self.api_get(user, '/json/messages/' + str(msg_id))
            self.assert_json_success(result)
        else:
            with self.assertRaisesRegex(JsonableError, error_msg):
                self.send_stream_message(user, stream_name)

    def test_message_to_self(self) -> None:
        """
        Sending a message to a stream to which you are subscribed is
        successful.
        """
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "topic": "Test topic"})
        self.assert_json_success(result)

    def test_api_message_to_self(self) -> None:
        """
        Same as above, but for the API view
        """
        user = self.example_user('hamlet')
        result = self.api_post(user, "/api/v1/messages", {"type": "stream",
                                                          "to": "Verona",
                                                          "client": "test suite",
                                                          "content": "Test message",
                                                          "topic": "Test topic"})
        self.assert_json_success(result)

    def test_message_to_stream_with_nonexistent_id(self) -> None:
        cordelia = self.example_user('cordelia')
        bot = self.create_test_bot(
            short_name='whatever',
            user_profile=cordelia,
        )
        result = self.api_post(
            bot, "/api/v1/messages",
            {
                "type": "stream",
                "to": ujson.dumps([99999]),
                "client": "test suite",
                "content": "Stream message by ID.",
                "topic": "Test topic for stream ID message",
            },
        )
        self.assert_json_error(result, "Stream with ID '99999' does not exist")

        msg = self.get_last_message()
        expected = ("Your bot `whatever-bot@zulip.testserver` tried to send a message to "
                    "stream ID 99999, but there is no stream with that ID.")
        self.assertEqual(msg.content, expected)

    def test_message_to_stream_by_id(self) -> None:
        """
        Sending a message to a stream (by stream ID) to which you are
        subscribed is successful.
        """
        self.login('hamlet')
        realm = get_realm('zulip')
        stream = get_stream('Verona', realm)
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": ujson.dumps([stream.id]),
                                                     "client": "test suite",
                                                     "content": "Stream message by ID.",
                                                     "topic": "Test topic for stream ID message"})
        self.assert_json_success(result)
        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "Stream message by ID.")

    def test_sending_message_as_stream_post_policy_admins(self) -> None:
        """
        Sending messages to streams which only the admins can create and post to.
        """
        admin_profile = self.example_user("iago")
        self.login_user(admin_profile)

        stream_name = "Verona"
        stream = get_stream(stream_name, admin_profile.realm)
        do_change_stream_post_policy(stream, Stream.STREAM_POST_POLICY_ADMINS)

        # Admins and their owned bots can send to STREAM_POST_POLICY_ADMINS streams
        self._send_and_verify_message(admin_profile, stream_name)
        admin_owned_bot = self.create_test_bot(
            short_name='whatever1',
            full_name='whatever1',
            user_profile=admin_profile,
        )
        self._send_and_verify_message(admin_owned_bot, stream_name)

        non_admin_profile = self.example_user("hamlet")
        self.login_user(non_admin_profile)

        # Non admins and their owned bots cannot send to STREAM_POST_POLICY_ADMINS streams
        self._send_and_verify_message(non_admin_profile, stream_name,
                                      "Only organization administrators can send to this stream.")
        non_admin_owned_bot = self.create_test_bot(
            short_name='whatever2',
            full_name='whatever2',
            user_profile=non_admin_profile,
        )
        self._send_and_verify_message(non_admin_owned_bot, stream_name,
                                      "Only organization administrators can send to this stream.")

        # Bots without owner (except cross realm bot) cannot send to announcement only streams
        bot_without_owner = do_create_user(
            email='free-bot@zulip.testserver',
            password='',
            realm=non_admin_profile.realm,
            full_name='freebot',
            short_name='freebot',
            bot_type=UserProfile.DEFAULT_BOT,
        )
        self._send_and_verify_message(bot_without_owner, stream_name,
                                      "Only organization administrators can send to this stream.")

        # Cross realm bots should be allowed
        notification_bot = get_system_bot("notification-bot@zulip.com")
        internal_send_stream_message(stream.realm, notification_bot, stream,
                                     'Test topic', 'Test message by notification bot')
        self.assertEqual(self.get_last_message().content, 'Test message by notification bot')

    def test_sending_message_as_stream_post_policy_restrict_new_members(self) -> None:
        """
        Sending messages to streams which new members cannot create and post to.
        """
        admin_profile = self.example_user("iago")
        self.login_user(admin_profile)

        do_set_realm_property(admin_profile.realm, 'waiting_period_threshold', 10)
        admin_profile.date_joined = timezone_now() - datetime.timedelta(days=9)
        admin_profile.save()
        self.assertTrue(admin_profile.is_new_member)
        self.assertTrue(admin_profile.is_realm_admin)

        stream_name = "Verona"
        stream = get_stream(stream_name, admin_profile.realm)
        do_change_stream_post_policy(stream, Stream.STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS)

        # Admins and their owned bots can send to STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS streams,
        # even if the admin is a new user
        self._send_and_verify_message(admin_profile, stream_name)
        admin_owned_bot = self.create_test_bot(
            short_name='whatever1',
            full_name='whatever1',
            user_profile=admin_profile,
        )
        self._send_and_verify_message(admin_owned_bot, stream_name)

        non_admin_profile = self.example_user("hamlet")
        self.login_user(non_admin_profile)

        non_admin_profile.date_joined = timezone_now() - datetime.timedelta(days=9)
        non_admin_profile.save()
        self.assertTrue(non_admin_profile.is_new_member)
        self.assertFalse(non_admin_profile.is_realm_admin)

        # Non admins and their owned bots can send to STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS streams,
        # if the user is not a new member
        self._send_and_verify_message(non_admin_profile, stream_name,
                                      "New members cannot send to this stream.")
        non_admin_owned_bot = self.create_test_bot(
            short_name='whatever2',
            full_name='whatever2',
            user_profile=non_admin_profile,
        )
        self._send_and_verify_message(non_admin_owned_bot, stream_name,
                                      "New members cannot send to this stream.")

        # Bots without owner (except cross realm bot) cannot send to announcement only stream
        bot_without_owner = do_create_user(
            email='free-bot@zulip.testserver',
            password='',
            realm=non_admin_profile.realm,
            full_name='freebot',
            short_name='freebot',
            bot_type=UserProfile.DEFAULT_BOT,
        )
        self._send_and_verify_message(bot_without_owner, stream_name,
                                      "New members cannot send to this stream.")

        # Cross realm bots should be allowed
        notification_bot = get_system_bot("notification-bot@zulip.com")
        internal_send_stream_message(stream.realm, notification_bot, stream,
                                     'Test topic', 'Test message by notification bot')
        self.assertEqual(self.get_last_message().content, 'Test message by notification bot')

    def test_api_message_with_default_to(self) -> None:
        """
        Sending messages without a to field should be sent to the default
        stream for the user_profile.
        """
        user = self.example_user('hamlet')
        user.default_sending_stream_id = get_stream('Verona', user.realm).id
        user.save()
        result = self.api_post(user, "/api/v1/messages", {"type": "stream",
                                                          "client": "test suite",
                                                          "content": "Test message no to",
                                                          "topic": "Test topic"})
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "Test message no to")

    def test_message_to_nonexistent_stream(self) -> None:
        """
        Sending a message to a nonexistent stream fails.
        """
        self.login('hamlet')
        self.assertFalse(Stream.objects.filter(name="nonexistent_stream"))
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "nonexistent_stream",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "topic": "Test topic"})
        self.assert_json_error(result, "Stream 'nonexistent_stream' does not exist")

    def test_message_to_nonexistent_stream_with_bad_characters(self) -> None:
        """
        Nonexistent stream name with bad characters should be escaped properly.
        """
        self.login('hamlet')
        self.assertFalse(Stream.objects.filter(name="""&<"'><non-existent>"""))
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": """&<"'><non-existent>""",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "topic": "Test topic"})
        self.assert_json_error(result, "Stream '&amp;&lt;&quot;&#39;&gt;&lt;non-existent&gt;' does not exist")

    def test_personal_message(self) -> None:
        """
        Sending a personal message to a valid username is successful.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        othello = self.example_user('othello')
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": othello.email})
        self.assert_json_success(result)
        message_id = ujson.loads(result.content.decode())['id']

        recent_conversations = get_recent_private_conversations(user_profile)
        self.assertEqual(len(recent_conversations), 1)
        recent_conversation = list(recent_conversations.values())[0]
        recipient_id = list(recent_conversations.keys())[0]
        self.assertEqual(set(recent_conversation['user_ids']), {othello.id})
        self.assertEqual(recent_conversation['max_message_id'], message_id)

        # Now send a message to yourself and see how that interacts with the data structure
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": user_profile.email})
        self.assert_json_success(result)
        self_message_id = ujson.loads(result.content.decode())['id']

        recent_conversations = get_recent_private_conversations(user_profile)
        self.assertEqual(len(recent_conversations), 2)
        recent_conversation = recent_conversations[recipient_id]
        self.assertEqual(set(recent_conversation['user_ids']), {othello.id})
        self.assertEqual(recent_conversation['max_message_id'], message_id)

        # Now verify we have the appropriate self-pm data structure
        del recent_conversations[recipient_id]
        recent_conversation = list(recent_conversations.values())[0]
        recipient_id = list(recent_conversations.keys())[0]
        self.assertEqual(set(recent_conversation['user_ids']), set())
        self.assertEqual(recent_conversation['max_message_id'], self_message_id)

    def test_personal_message_by_id(self) -> None:
        """
        Sending a personal message to a valid user ID is successful.
        """
        self.login('hamlet')
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "client": "test suite",
                "to": ujson.dumps([self.example_user("othello").id]),
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assertEqual("Test message", msg.content)
        self.assertEqual(msg.recipient_id, self.example_user("othello").id)

    def test_group_personal_message_by_id(self) -> None:
        """
        Sending a personal message to a valid user ID is successful.
        """
        self.login('hamlet')
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "client": "test suite",
                "to": ujson.dumps([self.example_user("othello").id,
                                   self.example_user("cordelia").id]),
            },
        )
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assertEqual("Test message", msg.content)
        self.assertEqual(msg.recipient_id, get_huddle_recipient(
            {self.example_user("hamlet").id,
             self.example_user("othello").id,
             self.example_user("cordelia").id}).id,
        )

    def test_personal_message_copying_self(self) -> None:
        """
        Sending a personal message to yourself plus another user is successful,
        and counts as a message just to that user.
        """
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        self.login_user(hamlet)
        result = self.client_post("/json/messages", {
            "type": "private",
            "content": "Test message",
            "client": "test suite",
            "to": ujson.dumps([hamlet.id, othello.id])})
        self.assert_json_success(result)
        msg = self.get_last_message()
        # Verify that we're not actually on the "recipient list"
        self.assertNotIn("Hamlet", str(msg.recipient))

    def test_personal_message_to_nonexistent_user(self) -> None:
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "nonexistent"})
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_personal_message_to_deactivated_user(self) -> None:
        """
        Sending a personal message to a deactivated user returns error JSON.
        """
        othello = self.example_user('othello')
        cordelia = self.example_user('cordelia')
        do_deactivate_user(othello)
        self.login('hamlet')

        result = self.client_post("/json/messages", {
            "type": "private",
            "content": "Test message",
            "client": "test suite",
            "to": ujson.dumps([othello.id])})
        self.assert_json_error(result, f"'{othello.email}' is no longer using Zulip.")

        result = self.client_post("/json/messages", {
            "type": "private",
            "content": "Test message",
            "client": "test suite",
            "to": ujson.dumps([othello.id, cordelia.id])})
        self.assert_json_error(result, f"'{othello.email}' is no longer using Zulip.")

    def test_invalid_type(self) -> None:
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login('hamlet')
        othello = self.example_user('othello')
        result = self.client_post("/json/messages", {"type": "invalid type",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": othello.email})
        self.assert_json_error(result, "Invalid message type")

    def test_empty_message(self) -> None:
        """
        Sending a message that is empty or only whitespace should fail
        """
        self.login('hamlet')
        othello = self.example_user('othello')
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": " ",
                                                     "client": "test suite",
                                                     "to": othello.email})
        self.assert_json_error(result, "Message must not be empty")

    def test_empty_string_topic(self) -> None:
        """
        Sending a message that has empty string topic should fail
        """
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "topic": ""})
        self.assert_json_error(result, "Topic can't be empty")

    def test_missing_topic(self) -> None:
        """
        Sending a message without topic should fail
        """
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message"})
        self.assert_json_error(result, "Missing topic")

    def test_invalid_message_type(self) -> None:
        """
        Messages other than the type of "private" or "stream" are considered as invalid
        """
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "invalid",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "topic": "Test topic"})
        self.assert_json_error(result, "Invalid message type")

    def test_private_message_without_recipients(self) -> None:
        """
        Sending private message without recipients should fail
        """
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test content",
                                                     "client": "test suite",
                                                     "to": ""})
        self.assert_json_error(result, "Message must have recipients")

    def test_mirrored_huddle(self) -> None:
        """
        Sending a mirrored huddle message works
        """
        result = self.api_post(self.mit_user("starnine"),
                               "/json/messages", {"type": "private",
                                                  "sender": self.mit_email("sipbtest"),
                                                  "content": "Test message",
                                                  "client": "zephyr_mirror",
                                                  "to": ujson.dumps([self.mit_email("starnine"),
                                                                     self.mit_email("espuser")])},
                               subdomain="zephyr")
        self.assert_json_success(result)

    def test_mirrored_personal(self) -> None:
        """
        Sending a mirrored personal message works
        """
        result = self.api_post(self.mit_user("starnine"),
                               "/json/messages", {"type": "private",
                                                  "sender": self.mit_email("sipbtest"),
                                                  "content": "Test message",
                                                  "client": "zephyr_mirror",
                                                  "to": self.mit_email("starnine")},
                               subdomain="zephyr")
        self.assert_json_success(result)

    def test_mirrored_personal_browser(self) -> None:
        """
        Sending a mirrored personal message via the browser should not work.
        """
        user = self.mit_user('starnine')
        self.login_user(user)
        result = self.client_post("/json/messages",
                                  {"type": "private",
                                   "sender": self.mit_email("sipbtest"),
                                   "content": "Test message",
                                   "client": "zephyr_mirror",
                                   "to": self.mit_email("starnine")},
                                  subdomain="zephyr")
        self.assert_json_error(result, "Invalid mirrored message")

    def test_mirrored_personal_to_someone_else(self) -> None:
        """
        Sending a mirrored personal message to someone else is not allowed.
        """
        result = self.api_post(self.mit_user("starnine"), "/api/v1/messages",
                               {"type": "private",
                                "sender": self.mit_email("sipbtest"),
                                "content": "Test message",
                                "client": "zephyr_mirror",
                                "to": self.mit_email("espuser")},
                               subdomain="zephyr")
        self.assert_json_error(result, "User not authorized for this query")

    def test_duplicated_mirrored_huddle(self) -> None:
        """
        Sending two mirrored huddles in the row return the same ID
        """
        msg = {"type": "private",
               "sender": self.mit_email("sipbtest"),
               "content": "Test message",
               "client": "zephyr_mirror",
               "to": ujson.dumps([self.mit_email("espuser"),
                                  self.mit_email("starnine")])}

        with mock.patch('DNS.dnslookup', return_value=[['starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash']]):
            result1 = self.api_post(self.mit_user("starnine"), "/api/v1/messages", msg,
                                    subdomain="zephyr")
            self.assert_json_success(result1)

        with mock.patch('DNS.dnslookup', return_value=[['espuser:*:95494:101:Esp Classroom,,,:/mit/espuser:/bin/athena/bash']]):
            result2 = self.api_post(self.mit_user("espuser"), "/api/v1/messages", msg,
                                    subdomain="zephyr")
            self.assert_json_success(result2)

        self.assertEqual(ujson.loads(result1.content)['id'],
                         ujson.loads(result2.content)['id'])

    def test_message_with_null_bytes(self) -> None:
        """
        A message with null bytes in it is handled.
        """
        self.login('hamlet')
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": "  I like null bytes \x00 in my content", "topic": "Test topic"}
        result = self.client_post("/json/messages", post_data)
        self.assert_json_error(result, "Message must not contain null bytes")

    def test_strip_message(self) -> None:
        """
        A message with mixed whitespace at the end is cleaned up.
        """
        self.login('hamlet')
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": "  I like whitespace at the end! \n\n \n", "topic": "Test topic"}
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)
        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "  I like whitespace at the end!")

    def test_long_message(self) -> None:
        """
        Sending a message longer than the maximum message length succeeds but is
        truncated.
        """
        self.login('hamlet')
        long_message = "A" * (MAX_MESSAGE_LENGTH + 1)
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": long_message, "topic": "Test topic"}
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content,
                         "A" * (MAX_MESSAGE_LENGTH - 20) + "\n[message truncated]")

    def test_long_topic(self) -> None:
        """
        Sending a message with a topic longer than the maximum topic length
        succeeds, but the topic is truncated.
        """
        self.login('hamlet')
        long_topic = "A" * (MAX_TOPIC_NAME_LENGTH + 1)
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": "test content", "topic": long_topic}
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.topic_name(),
                         "A" * (MAX_TOPIC_NAME_LENGTH - 3) + "...")

    def test_send_forged_message_as_not_superuser(self) -> None:
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "topic": "Test topic",
                                                     "forged": "true"})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_not_superuser_to_different_domain(self) -> None:
        self.login('hamlet')
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "topic": "Test topic",
                                                     "realm_str": "mit"})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_superuser_to_domain_that_dont_exist(self) -> None:
        user = self.example_user("default_bot")
        password = "test_password"
        user.set_password(password)
        user.is_api_super_user = True
        user.save()
        result = self.api_post(user,
                               "/api/v1/messages", {"type": "stream",
                                                    "to": "Verona",
                                                    "client": "test suite",
                                                    "content": "Test message",
                                                    "topic": "Test topic",
                                                    "realm_str": "non-existing"})
        user.is_api_super_user = False
        user.save()
        self.assert_json_error(result, "Unknown organization 'non-existing'")

    def test_send_message_when_sender_is_not_set(self) -> None:
        result = self.api_post(self.mit_user("starnine"), "/api/v1/messages",
                               {"type": "private",
                                "content": "Test message",
                                "client": "zephyr_mirror",
                                "to": self.mit_email("starnine")},
                               subdomain="zephyr")
        self.assert_json_error(result, "Missing sender")

    def test_send_message_as_not_superuser_when_type_is_not_private(self) -> None:
        result = self.api_post(self.mit_user("starnine"), "/api/v1/messages",
                               {"type": "not-private",
                                "sender": self.mit_email("sipbtest"),
                                "content": "Test message",
                                "client": "zephyr_mirror",
                                "to": self.mit_email("starnine")},
                               subdomain="zephyr")
        self.assert_json_error(result, "User not authorized for this query")

    @mock.patch("zerver.views.message_send.create_mirrored_message_users")
    def test_send_message_create_mirrored_message_user_returns_invalid_input(
            self, create_mirrored_message_users_mock: Any) -> None:
        create_mirrored_message_users_mock.side_effect = InvalidMirrorInput()
        result = self.api_post(self.mit_user("starnine"), "/api/v1/messages",
                               {"type": "private",
                                "sender": self.mit_email("sipbtest"),
                                "content": "Test message",
                                "client": "zephyr_mirror",
                                "to": self.mit_email("starnine")},
                               subdomain="zephyr")
        self.assert_json_error(result, "Invalid mirrored message")

    @mock.patch("zerver.views.message_send.create_mirrored_message_users")
    def test_send_message_when_client_is_zephyr_mirror_but_string_id_is_not_zephyr(
            self, create_mirrored_message_users_mock: Any) -> None:
        create_mirrored_message_users_mock.return_value = mock.Mock()
        user = self.mit_user("starnine")
        user.realm.string_id = 'notzephyr'
        user.realm.save()
        result = self.api_post(user, "/api/v1/messages",
                               {"type": "private",
                                "sender": self.mit_email("sipbtest"),
                                "content": "Test message",
                                "client": "zephyr_mirror",
                                "to": user.email},
                               subdomain="notzephyr")
        self.assert_json_error(result, "Zephyr mirroring is not allowed in this organization")

    @mock.patch("zerver.views.message_send.create_mirrored_message_users")
    def test_send_message_when_client_is_zephyr_mirror_but_recipient_is_user_id(
            self, create_mirrored_message_users_mock: Any) -> None:
        create_mirrored_message_users_mock.return_value = mock.Mock()
        user = self.mit_user("starnine")
        self.login_user(user)
        result = self.api_post(user, "/api/v1/messages",
                               {"type": "private",
                                "sender": self.mit_email("sipbtest"),
                                "content": "Test message",
                                "client": "zephyr_mirror",
                                "to": ujson.dumps([user.id])},
                               subdomain="zephyr")
        self.assert_json_error(result, "Mirroring not allowed with recipient user IDs")

    def test_send_message_irc_mirror(self) -> None:
        reset_emails_in_zulip_realm()
        self.login('hamlet')
        bot_info = {
            'full_name': 'IRC bot',
            'short_name': 'irc',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        email = "irc-bot@zulip.testserver"
        user = get_user(email, get_realm('zulip'))
        user.is_api_super_user = True
        user.save()
        user = get_user(email, get_realm('zulip'))
        self.subscribe(user, "IRCland")

        # Simulate a mirrored message with a slightly old timestamp.
        fake_date_sent = timezone_now() - datetime.timedelta(minutes=37)
        fake_timestamp = datetime_to_timestamp(fake_date_sent)

        result = self.api_post(user, "/api/v1/messages", {"type": "stream",
                                                          "forged": "true",
                                                          "time": fake_timestamp,
                                                          "sender": "irc-user@irc.zulip.com",
                                                          "content": "Test message",
                                                          "client": "irc_mirror",
                                                          "topic": "from irc",
                                                          "to": "IRCLand"})
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assertEqual(int(datetime_to_timestamp(msg.date_sent)), int(fake_timestamp))

        # Now test again using forged=yes
        fake_date_sent = timezone_now() - datetime.timedelta(minutes=22)
        fake_timestamp = datetime_to_timestamp(fake_date_sent)

        result = self.api_post(user, "/api/v1/messages", {"type": "stream",
                                                          "forged": "yes",
                                                          "time": fake_timestamp,
                                                          "sender": "irc-user@irc.zulip.com",
                                                          "content": "Test message",
                                                          "client": "irc_mirror",
                                                          "topic": "from irc",
                                                          "to": "IRCLand"})
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assertEqual(int(datetime_to_timestamp(msg.date_sent)), int(fake_timestamp))

    def test_unsubscribed_api_super_user(self) -> None:
        reset_emails_in_zulip_realm()

        cordelia = self.example_user('cordelia')
        stream_name = 'private_stream'
        self.make_stream(stream_name, invite_only=True)

        self.unsubscribe(cordelia, stream_name)

        # As long as Cordelia is a super_user, she can send messages
        # to ANY stream, even one she is not unsubscribed to, and
        # she can do it for herself or on behalf of a mirrored user.

        def test_with(sender_email: str, client: str, forged: bool) -> None:
            payload = dict(
                type="stream",
                to=stream_name,
                client=client,
                topic='whatever',
                content='whatever',
                forged=ujson.dumps(forged),
            )

            # Only pass the 'sender' property when doing mirroring behavior.
            if forged:
                payload['sender'] = sender_email

            cordelia.is_api_super_user = False
            cordelia.save()

            result = self.api_post(cordelia, "/api/v1/messages", payload)
            self.assert_json_error_contains(result, 'authorized')

            cordelia.is_api_super_user = True
            cordelia.save()

            result = self.api_post(cordelia, "/api/v1/messages", payload)
            self.assert_json_success(result)

        test_with(
            sender_email=cordelia.email,
            client='test suite',
            forged=False,
        )

        test_with(
            sender_email='irc_person@zulip.com',
            client='irc_mirror',
            forged=True,
        )

    def test_bot_can_send_to_owner_stream(self) -> None:
        cordelia = self.example_user('cordelia')
        bot = self.create_test_bot(
            short_name='whatever',
            user_profile=cordelia,
        )

        stream_name = 'private_stream'
        self.make_stream(stream_name, invite_only=True)

        payload = dict(
            type="stream",
            to=stream_name,
            client='test suite',
            topic='whatever',
            content='whatever',
        )

        result = self.api_post(bot, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, 'Not authorized to send')

        # We subscribe the bot owner! (aka cordelia)
        assert bot.bot_owner is not None
        self.subscribe(bot.bot_owner, stream_name)

        result = self.api_post(bot, "/api/v1/messages", payload)
        self.assert_json_success(result)

    def test_cross_realm_bots_can_use_api_on_own_subdomain(self) -> None:
        # Cross realm bots should use internal_send_*_message, not the API:
        notification_bot = self.notification_bot()
        stream = self.make_stream("notify_channel", get_realm("zulipinternal"))

        result = self.api_post(notification_bot,
                               "/api/v1/messages",
                               {"type": "stream",
                                "to": "notify_channel",
                                "client": "test suite",
                                "content": "Test message",
                                "topic": "Test topic"},
                               subdomain='zulipinternal')

        self.assert_json_success(result)
        message = self.get_last_message()

        self.assertEqual(message.content, "Test message")
        self.assertEqual(message.sender, notification_bot)
        self.assertEqual(message.recipient.type_id, stream.id)

    def test_guest_user(self) -> None:
        sender = self.example_user('polonius')

        stream_name = 'public stream'
        self.make_stream(stream_name, invite_only=False)
        payload = dict(
            type="stream",
            to=stream_name,
            client='test suite',
            topic='whatever',
            content='whatever',
        )

        # Guest user can't send message to unsubscribed public streams
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_error(result, "Not authorized to send to stream 'public stream'")

        self.subscribe(sender, stream_name)
        # Guest user can send message to subscribed public streams
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

class ScheduledMessageTest(ZulipTestCase):

    def last_scheduled_message(self) -> ScheduledMessage:
        return ScheduledMessage.objects.all().order_by('-id')[0]

    def do_schedule_message(self, msg_type: str, to: str, msg: str,
                            defer_until: str='', tz_guess: str='',
                            delivery_type: str='send_later',
                            realm_str: str='zulip') -> HttpResponse:
        self.login('hamlet')

        topic_name = ''
        if msg_type == 'stream':
            topic_name = 'Test topic'

        payload = {"type": msg_type,
                   "to": to,
                   "client": "test suite",
                   "content": msg,
                   "topic": topic_name,
                   "realm_str": realm_str,
                   "delivery_type": delivery_type,
                   "tz_guess": tz_guess}
        if defer_until:
            payload["deliver_at"] = defer_until

        result = self.client_post("/json/messages", payload)
        return result

    def test_schedule_message(self) -> None:
        content = "Test message"
        defer_until = timezone_now().replace(tzinfo=None) + datetime.timedelta(days=1)
        defer_until_str = str(defer_until)

        # Scheduling a message to a stream you are subscribed is successful.
        result = self.do_schedule_message('stream', 'Verona',
                                          content + ' 1', defer_until_str)
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, 'Test message 1')
        self.assertEqual(message.topic_name(), 'Test topic')
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(defer_until))
        self.assertEqual(message.delivery_type, ScheduledMessage.SEND_LATER)
        # Scheduling a message for reminders.
        result = self.do_schedule_message('stream', 'Verona',
                                          content + ' 2', defer_until_str,
                                          delivery_type='remind')
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.delivery_type, ScheduledMessage.REMIND)

        # Scheduling a private message is successful.
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        result = self.do_schedule_message('private', othello.email,
                                          content + ' 3', defer_until_str)
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, 'Test message 3')
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(defer_until))
        self.assertEqual(message.delivery_type, ScheduledMessage.SEND_LATER)

        # Setting a reminder in PM's to other users causes a error.
        result = self.do_schedule_message('private', othello.email,
                                          content + ' 4', defer_until_str,
                                          delivery_type='remind')
        self.assert_json_error(result, 'Reminders can only be set for streams.')

        # Setting a reminder in PM's to ourself is successful.
        # Required by reminders from message actions popover caret feature.
        result = self.do_schedule_message('private', hamlet.email,
                                          content + ' 5', defer_until_str,
                                          delivery_type='remind')
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, 'Test message 5')
        self.assertEqual(message.delivery_type, ScheduledMessage.REMIND)

        # Scheduling a message while guessing timezone.
        tz_guess = 'Asia/Kolkata'
        result = self.do_schedule_message('stream', 'Verona', content + ' 6',
                                          defer_until_str, tz_guess=tz_guess)
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, 'Test message 6')
        local_tz = get_timezone(tz_guess)
        utz_defer_until = local_tz.normalize(local_tz.localize(defer_until))
        self.assertEqual(message.scheduled_timestamp,
                         convert_to_UTC(utz_defer_until))
        self.assertEqual(message.delivery_type, ScheduledMessage.SEND_LATER)

        # Test with users timezone setting as set to some timezone rather than
        # empty. This will help interpret timestamp in users local timezone.
        user = self.example_user("hamlet")
        user.timezone = 'US/Pacific'
        user.save(update_fields=['timezone'])
        result = self.do_schedule_message('stream', 'Verona',
                                          content + ' 7', defer_until_str)
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, 'Test message 7')
        local_tz = get_timezone(user.timezone)
        utz_defer_until = local_tz.normalize(local_tz.localize(defer_until))
        self.assertEqual(message.scheduled_timestamp,
                         convert_to_UTC(utz_defer_until))
        self.assertEqual(message.delivery_type, ScheduledMessage.SEND_LATER)

    def test_scheduling_in_past(self) -> None:
        # Scheduling a message in past should fail.
        content = "Test message"
        defer_until = timezone_now()
        defer_until_str = str(defer_until)

        result = self.do_schedule_message('stream', 'Verona',
                                          content + ' 1', defer_until_str)
        self.assert_json_error(result, 'Time must be in the future.')

    def test_invalid_timestamp(self) -> None:
        # Scheduling a message from which timestamp couldn't be parsed
        # successfully should fail.
        content = "Test message"
        defer_until = 'Missed the timestamp'

        result = self.do_schedule_message('stream', 'Verona',
                                          content + ' 1', defer_until)
        self.assert_json_error(result, 'Invalid time format')

    def test_missing_deliver_at(self) -> None:
        content = "Test message"

        result = self.do_schedule_message('stream', 'Verona',
                                          content + ' 1')
        self.assert_json_error(result, 'Missing deliver_at in a request for delayed message delivery')

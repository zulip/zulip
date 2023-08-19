import datetime
from operator import itemgetter
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from unittest import mock

import orjson
from django.db import IntegrityError
from django.utils.timezone import now as timezone_now

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import (
    check_update_message,
    do_update_message,
    get_mentions_for_message_updates,
)
from zerver.actions.reactions import do_add_reaction
from zerver.actions.realm_settings import do_change_realm_plan_type, do_set_realm_property
from zerver.actions.streams import do_change_stream_post_policy, do_deactivate_stream
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.actions.users import do_change_user_role
from zerver.lib.message import MessageDict, has_message_access, messages_for_ids, truncate_topic
from zerver.lib.test_classes import ZulipTestCase, get_topic_messages
from zerver.lib.test_helpers import queries_captured
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX, TOPIC_NAME
from zerver.lib.url_encoding import near_stream_message_url
from zerver.lib.user_topics import (
    get_users_with_user_topic_visibility_policy,
    set_topic_visibility_policy,
    topic_has_visibility_policy,
)
from zerver.lib.utils import assert_is_not_none
from zerver.models import (
    MAX_TOPIC_NAME_LENGTH,
    Message,
    Realm,
    Stream,
    UserGroup,
    UserMessage,
    UserProfile,
    UserTopic,
    get_realm,
    get_stream,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class EditMessageTestCase(ZulipTestCase):
    def check_topic(self, msg_id: int, topic_name: str) -> None:
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.topic_name(), topic_name)

    def check_message(self, msg_id: int, topic_name: str, content: str) -> None:
        # Make sure we saved the message correctly to the DB.
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.topic_name(), topic_name)
        self.assertEqual(msg.content, content)

        """
        We assume our caller just edited a message.

        Next, we will make sure we properly cached the messages.  We still have
        to do a query to hydrate recipient info, but we won't need to hit the
        zerver_message table.
        """

        with queries_captured(keep_cache_warm=True) as queries:
            (fetch_message_dict,) = messages_for_ids(
                message_ids=[msg.id],
                user_message_flags={msg_id: []},
                search_fields={},
                apply_markdown=False,
                client_gravatar=False,
                allow_edit_history=True,
            )

        self.assert_length(queries, 1)
        for query in queries:
            self.assertNotIn("message", query.sql)

        self.assertEqual(
            fetch_message_dict[TOPIC_NAME],
            msg.topic_name(),
        )
        self.assertEqual(
            fetch_message_dict["content"],
            msg.content,
        )
        self.assertEqual(
            fetch_message_dict["sender_id"],
            msg.sender_id,
        )

        if msg.edit_history:
            self.assertEqual(
                fetch_message_dict["edit_history"],
                orjson.loads(msg.edit_history),
            )

    def prepare_move_topics(
        self,
        user_email: str,
        old_stream: str,
        new_stream: str,
        topic: str,
        language: Optional[str] = None,
    ) -> Tuple[UserProfile, Stream, Stream, int, int]:
        user_profile = self.example_user(user_email)
        if language is not None:
            user_profile.default_language = language
            user_profile.save(update_fields=["default_language"])

        self.login(user_email)
        stream = self.make_stream(old_stream)
        stream_to = self.make_stream(new_stream)
        self.subscribe(user_profile, stream.name)
        self.subscribe(user_profile, stream_to.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name=topic, content="First"
        )
        msg_id_lt = self.send_stream_message(
            user_profile, stream.name, topic_name=topic, content="Second"
        )

        self.send_stream_message(user_profile, stream.name, topic_name=topic, content="third")

        return (user_profile, stream, stream_to, msg_id, msg_id_lt)


class EditMessagePayloadTest(EditMessageTestCase):
    def test_edit_message_no_changes(self) -> None:
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", topic_name="editing", content="before edit"
        )
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {},
        )
        self.assert_json_error(result, "Nothing to change")

    def test_move_message_cant_move_private_message(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        cordelia = self.example_user("cordelia")
        msg_id = self.send_personal_message(hamlet, cordelia)

        verona = get_stream("Verona", hamlet.realm)

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": verona.id,
            },
        )

        self.assert_json_error(result, "Direct messages cannot be moved to streams.")

    def test_private_message_edit_topic(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        cordelia = self.example_user("cordelia")
        msg_id = self.send_personal_message(hamlet, cordelia)

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "Should not exist",
            },
        )

        self.assert_json_error(result, "Direct messages cannot have topics.")

    def test_propagate_invalid(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic1")

        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": "edited",
                "propagate_mode": "invalid",
            },
        )
        self.assert_json_error(result, "Invalid propagate_mode")
        self.check_topic(id1, topic_name="topic1")

        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "content": "edited",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(result, "Invalid propagate_mode without topic edit")
        self.check_topic(id1, topic_name="topic1")

    def test_edit_message_no_topic(self) -> None:
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", topic_name="editing", content="before edit"
        )
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": " ",
            },
        )
        self.assert_json_error(result, "Topic can't be empty!")

    def test_edit_message_invalid_topic(self) -> None:
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", topic_name="editing", content="before edit"
        )
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "editing\nfun",
            },
        )
        self.assert_json_error(result, "Invalid character in topic, at position 8!")

    def test_move_message_to_stream_with_content(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "content": "Not allowed",
            },
        )
        self.assert_json_error(result, "Cannot change message content while changing stream")

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 3)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 0)

    # Right now, we prevent users from editing widgets.
    def test_edit_submessage(self) -> None:
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="/poll Games?\nYES\nNO",
        )
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": "/poll Games?\nYES\nNO\nMaybe",
            },
        )
        self.assert_json_error(result, "Widgets cannot be edited.")


class EditMessageTest(EditMessageTestCase):
    def test_query_count_on_to_dict_uncached(self) -> None:
        # `to_dict_uncached` method is used by the mechanisms
        # tested in this class. Hence, its performance is tested here.
        # Generate 2 messages
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)
        stream_name = "public_stream"
        self.subscribe(user, stream_name)
        message_ids = []
        message_ids.append(self.send_stream_message(user, stream_name, "Message one"))
        user_2 = self.example_user("cordelia")
        self.subscribe(user_2, stream_name)
        message_ids.append(self.send_stream_message(user_2, stream_name, "Message two"))
        self.subscribe(self.notification_bot(realm), stream_name)
        message_ids.append(
            self.send_stream_message(self.notification_bot(realm), stream_name, "Message three")
        )
        messages = [
            Message.objects.select_related(*Message.DEFAULT_SELECT_RELATED).get(id=message_id)
            for message_id in message_ids
        ]

        # Check number of queries performed
        # 1 query for realm_id per message = 3
        # 1 query each for reactions & submessage for all messages = 2
        # 1 query for linkifiers
        # 1 query for display recipients
        with self.assert_database_query_count(7):
            MessageDict.to_dict_uncached(messages)

        realm_id = 2  # Fetched from stream object
        # Check number of queries performed with realm_id
        with self.assert_database_query_count(3):
            MessageDict.to_dict_uncached(messages, realm_id)

    def test_save_message(self) -> None:
        """This is also tested by a client test, but here we can verify
        the cache against the database"""
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", topic_name="editing", content="before edit"
        )
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "after edit",
            },
        )
        self.assert_json_success(result)
        self.check_message(msg_id, topic_name="editing", content="after edit")

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "edited",
            },
        )
        self.assert_json_success(result)
        self.check_topic(msg_id, topic_name="edited")

    def test_fetch_message_from_id(self) -> None:
        self.login("hamlet")
        msg_id = self.send_personal_message(
            from_user=self.example_user("hamlet"),
            to_user=self.example_user("cordelia"),
            content="Personal message",
        )
        result = self.client_get("/json/messages/" + str(msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "Personal message")
        self.assertEqual(response_dict["message"]["id"], msg_id)
        self.assertEqual(response_dict["message"]["flags"], [])

        # Send message to web-public stream where hamlet is not subscribed.
        # This will test case of user having no `UserMessage` but having access
        # to message.
        web_public_stream = self.make_stream("web-public-stream", is_web_public=True)
        self.subscribe(self.example_user("cordelia"), web_public_stream.name)
        web_public_stream_msg_id = self.send_stream_message(
            self.example_user("cordelia"), web_public_stream.name, content="web-public message"
        )
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "web-public message")
        self.assertEqual(response_dict["message"]["id"], web_public_stream_msg_id)
        self.assertEqual(response_dict["message"]["flags"], ["read", "historical"])

        # Spectator should be able to fetch message in web-public stream.
        self.logout()
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "web-public message")
        self.assertEqual(response_dict["message"]["id"], web_public_stream_msg_id)

        # Verify default is apply_markdown=True
        self.assertEqual(response_dict["message"]["content"], "<p>web-public message</p>")

        # Verify apply_markdown=False works correctly.
        result = self.client_get(
            "/json/messages/" + str(web_public_stream_msg_id), {"apply_markdown": "false"}
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "web-public message")
        self.assertEqual(response_dict["message"]["content"], "web-public message")

        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", status_code=401
        )

        # Test error cases
        self.login("hamlet")
        result = self.client_get("/json/messages/999999")
        self.assert_json_error(result, "Invalid message(s)")

        self.login("cordelia")
        result = self.client_get(f"/json/messages/{msg_id}")
        self.assert_json_success(result)

        self.login("othello")
        result = self.client_get(f"/json/messages/{msg_id}")
        self.assert_json_error(result, "Invalid message(s)")

    def test_fetch_raw_message_spectator(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        web_public_stream = self.make_stream("web-public-stream", is_web_public=True)
        self.subscribe(user_profile, web_public_stream.name)

        web_public_stream_msg_id = self.send_stream_message(
            user_profile, web_public_stream.name, content="web-public message"
        )

        non_web_public_stream = self.make_stream("non-web-public-stream")
        self.subscribe(user_profile, non_web_public_stream.name)
        non_web_public_stream_msg_id = self.send_stream_message(
            user_profile, non_web_public_stream.name, content="non-web-public message"
        )

        # Generate a direct message to use in verification.
        private_message_id = self.send_personal_message(user_profile, user_profile)

        invalid_message_id = private_message_id + 1000

        self.logout()

        # Confirm WEB_PUBLIC_STREAMS_ENABLED is enforced.
        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

        do_set_realm_property(
            user_profile.realm, "enable_spectator_access", False, acting_user=None
        )
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )
        do_set_realm_property(user_profile.realm, "enable_spectator_access", True, acting_user=None)

        # Verify success with web-public stream and default SELF_HOSTED plan type.
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "web-public message")
        self.assertEqual(response_dict["message"]["flags"], ["read"])

        # Verify LIMITED plan type does not allow web-public access.
        do_change_realm_plan_type(user_profile.realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

        do_set_realm_property(user_profile.realm, "enable_spectator_access", True, acting_user=None)
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

        # Verify works with STANDARD_FREE plan type too.
        do_change_realm_plan_type(
            user_profile.realm, Realm.PLAN_TYPE_STANDARD_FREE, acting_user=None
        )
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "web-public message")

        # Verify direct messages are rejected.
        result = self.client_get("/json/messages/" + str(private_message_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

        # Verify an actual public stream is required.
        result = self.client_get("/json/messages/" + str(non_web_public_stream_msg_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

        # Verify invalid message IDs are rejected with the same error message.
        result = self.client_get("/json/messages/" + str(invalid_message_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

        # Verify deactivated streams are rejected.  This may change in the future.
        do_deactivate_stream(web_public_stream, acting_user=None)
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

    def test_fetch_raw_message_stream_wrong_realm(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        stream = self.make_stream("public_stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="test"
        )
        result = self.client_get(f"/json/messages/{msg_id}")
        self.assert_json_success(result)

        mit_user = self.mit_user("sipbtest")
        self.login_user(mit_user)
        result = self.client_get(f"/json/messages/{msg_id}", subdomain="zephyr")
        self.assert_json_error(result, "Invalid message(s)")

    def test_fetch_raw_message_private_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        stream = self.make_stream("private_stream", invite_only=True)
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="test"
        )
        result = self.client_get(f"/json/messages/{msg_id}")
        self.assert_json_success(result)
        self.login("othello")
        result = self.client_get(f"/json/messages/{msg_id}")
        self.assert_json_error(result, "Invalid message(s)")

    def test_edit_message_no_permission(self) -> None:
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("iago"), "Denmark", topic_name="editing", content="before edit"
        )
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "content after edit",
            },
        )
        self.assert_json_error(result, "You don't have permission to edit this message")

        self.login("iago")
        realm = get_realm("zulip")
        do_set_realm_property(realm, "allow_message_editing", False, acting_user=None)
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "content after edit",
            },
        )
        self.assert_json_error(result, "Your organization has turned off message editing")

    def test_edit_message_no_content(self) -> None:
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", topic_name="editing", content="before edit"
        )
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": " ",
            },
        )
        self.assert_json_success(result)
        content = Message.objects.filter(id=msg_id).values_list("content", flat=True)[0]
        self.assertEqual(content, "(deleted)")

    def test_edit_message_in_unsubscribed_private_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")

        self.make_stream("privatestream", invite_only=True, history_public_to_subscribers=False)
        self.subscribe(hamlet, "privatestream")
        msg_id = self.send_stream_message(
            hamlet, "privatestream", topic_name="editing", content="before edit"
        )

        # Ensure the user originally could edit the message. This ensures the
        # loss of the ability is caused by unsubscribing, rather than something
        # else wrong with the test's setup/assumptions.
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "test can edit before unsubscribing",
            },
        )
        self.assert_json_success(result)

        self.unsubscribe(hamlet, "privatestream")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "after unsubscribing",
            },
        )
        self.assert_json_error(result, "Invalid message(s)")
        content = Message.objects.get(id=msg_id).content
        self.assertEqual(content, "test can edit before unsubscribing")

    def test_edit_message_guest_in_unsubscribed_public_stream(self) -> None:
        guest_user = self.example_user("polonius")
        self.login("polonius")
        self.assertEqual(guest_user.role, UserProfile.ROLE_GUEST)

        self.make_stream("publicstream", invite_only=False)
        self.subscribe(guest_user, "publicstream")
        msg_id = self.send_stream_message(
            guest_user, "publicstream", topic_name="editing", content="before edit"
        )

        # Ensure the user originally could edit the message.
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "test can edit before unsubscribing",
            },
        )
        self.assert_json_success(result)

        self.unsubscribe(guest_user, "publicstream")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "after unsubscribing",
            },
        )
        self.assert_json_error(result, "Invalid message(s)")
        content = Message.objects.get(id=msg_id).content
        self.assertEqual(content, "test can edit before unsubscribing")

    def test_edit_message_history_disabled(self) -> None:
        user_profile = self.example_user("hamlet")
        do_set_realm_property(user_profile.realm, "allow_edit_history", False, acting_user=None)
        self.login("hamlet")

        # Single-line edit
        msg_id_1 = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="content before edit",
        )

        new_content_1 = "content after edit"
        result_1 = self.client_patch(
            f"/json/messages/{msg_id_1}",
            {
                "content": new_content_1,
            },
        )
        self.assert_json_success(result_1)

        result = self.client_get(f"/json/messages/{msg_id_1}/history")
        self.assert_json_error(result, "Message edit history is disabled in this organization")

        # Now verify that if we fetch the message directly, there's no
        # edit history data attached.
        messages_result = self.client_get(
            "/json/messages", {"anchor": msg_id_1, "num_before": 0, "num_after": 10}
        )
        self.assert_json_success(messages_result)
        json_messages = orjson.loads(messages_result.content)
        for msg in json_messages["messages"]:
            self.assertNotIn("edit_history", msg)

    def test_edit_message_history(self) -> None:
        self.login("hamlet")

        # Single-line edit
        msg_id_1 = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="content before edit",
        )
        new_content_1 = "content after edit"
        result_1 = self.client_patch(
            f"/json/messages/{msg_id_1}",
            {
                "content": new_content_1,
            },
        )
        self.assert_json_success(result_1)

        message_edit_history_1 = self.client_get(f"/json/messages/{msg_id_1}/history")
        json_response_1 = orjson.loads(message_edit_history_1.content)
        message_history_1 = json_response_1["message_history"]

        # Check content of message after edit.
        self.assertEqual(message_history_1[0]["rendered_content"], "<p>content before edit</p>")
        self.assertEqual(message_history_1[1]["rendered_content"], "<p>content after edit</p>")
        self.assertEqual(
            message_history_1[1]["content_html_diff"],
            (
                "<div><p>content "
                '<span class="highlight_text_inserted">after</span> '
                '<span class="highlight_text_deleted">before</span>'
                " edit</p></div>"
            ),
        )
        # Check content of message before edit.
        self.assertEqual(
            message_history_1[1]["prev_rendered_content"], "<p>content before edit</p>"
        )

        # Edits on new lines
        msg_id_2 = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="content before edit, line 1\n\ncontent before edit, line 3",
        )
        new_content_2 = (
            "content before edit, line 1\n"
            "content after edit, line 2\n"
            "content before edit, line 3"
        )
        result_2 = self.client_patch(
            f"/json/messages/{msg_id_2}",
            {
                "content": new_content_2,
            },
        )
        self.assert_json_success(result_2)

        message_edit_history_2 = self.client_get(f"/json/messages/{msg_id_2}/history")
        json_response_2 = orjson.loads(message_edit_history_2.content)
        message_history_2 = json_response_2["message_history"]

        self.assertEqual(
            message_history_2[0]["rendered_content"],
            "<p>content before edit, line 1</p>\n<p>content before edit, line 3</p>",
        )
        self.assertEqual(
            message_history_2[1]["rendered_content"],
            (
                "<p>content before edit, line 1<br>\n"
                "content after edit, line 2<br>\n"
                "content before edit, line 3</p>"
            ),
        )
        self.assertEqual(
            message_history_2[1]["content_html_diff"],
            (
                "<div><p>content before edit, line 1<br> "
                'content <span class="highlight_text_inserted">after edit, line 2<br> '
                "content</span> before edit, line 3</p></div>"
            ),
        )
        self.assertEqual(
            message_history_2[1]["prev_rendered_content"],
            "<p>content before edit, line 1</p>\n<p>content before edit, line 3</p>",
        )

    def test_empty_message_edit(self) -> None:
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="We will edit this to render as empty.",
        )
        # Edit that manually to simulate a rendering bug
        message = Message.objects.get(id=msg_id)
        message.rendered_content = ""
        message.save(update_fields=["rendered_content"])

        self.assert_json_success(
            self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "content": "We will edit this to also render as empty.",
                },
            )
        )
        # And again tweak to simulate a rendering bug
        message = Message.objects.get(id=msg_id)
        message.rendered_content = ""
        message.save(update_fields=["rendered_content"])

        history = self.client_get("/json/messages/" + str(msg_id) + "/history")
        message_history = orjson.loads(history.content)["message_history"]
        self.assertEqual(message_history[0]["rendered_content"], "")
        self.assertEqual(message_history[1]["rendered_content"], "")
        self.assertEqual(message_history[1]["content_html_diff"], "<div></div>")

    def test_edit_link(self) -> None:
        # Link editing
        self.login("hamlet")
        msg_id_1 = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="Here is a link to [zulip](www.zulip.org).",
        )
        new_content_1 = "Here is a link to [zulip](www.zulipchat.com)."
        result_1 = self.client_patch(
            f"/json/messages/{msg_id_1}",
            {
                "content": new_content_1,
            },
        )
        self.assert_json_success(result_1)

        message_edit_history_1 = self.client_get(f"/json/messages/{msg_id_1}/history")
        json_response_1 = orjson.loads(message_edit_history_1.content)
        message_history_1 = json_response_1["message_history"]

        # Check content of message after edit.
        self.assertEqual(
            message_history_1[0]["rendered_content"],
            '<p>Here is a link to <a href="http://www.zulip.org">zulip</a>.</p>',
        )
        self.assertEqual(
            message_history_1[1]["rendered_content"],
            '<p>Here is a link to <a href="http://www.zulipchat.com">zulip</a>.</p>',
        )
        self.assertEqual(
            message_history_1[1]["content_html_diff"],
            (
                '<div><p>Here is a link to <a href="http://www.zulipchat.com"'
                ">zulip "
                '<span class="highlight_text_inserted"> Link: http://www.zulipchat.com .'
                '</span> <span class="highlight_text_deleted"> Link: http://www.zulip.org .'
                "</span> </a></p></div>"
            ),
        )

    def test_edit_history_unedited(self) -> None:
        self.login("hamlet")

        msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="This message has not been edited.",
        )

        result = self.client_get(f"/json/messages/{msg_id}/history")

        message_history = self.assert_json_success(result)["message_history"]
        self.assert_length(message_history, 1)

    def test_mentions_for_message_updates(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        self.login_user(hamlet)
        self.subscribe(hamlet, "Denmark")
        self.subscribe(cordelia, "Denmark")

        msg_id = self.send_stream_message(
            hamlet, "Denmark", content="@**Cordelia, Lear's daughter**"
        )

        mention_user_ids = get_mentions_for_message_updates(msg_id)
        self.assertEqual(mention_user_ids, {cordelia.id})

    def test_edit_cases(self) -> None:
        """This test verifies the accuracy of construction of Zulip's edit
        history data structures."""
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        stream_1 = self.make_stream("stream 1")
        stream_2 = self.make_stream("stream 2")
        stream_3 = self.make_stream("stream 3")
        self.subscribe(hamlet, stream_1.name)
        self.subscribe(hamlet, stream_2.name)
        self.subscribe(hamlet, stream_3.name)
        msg_id = self.send_stream_message(
            self.example_user("hamlet"), "stream 1", topic_name="topic 1", content="content 1"
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "content 2",
            },
        )
        self.assert_json_success(result)
        history = orjson.loads(assert_is_not_none(Message.objects.get(id=msg_id).edit_history))
        self.assertEqual(history[0]["prev_content"], "content 1")
        self.assertEqual(history[0]["user_id"], hamlet.id)
        self.assertEqual(
            set(history[0].keys()),
            {
                "timestamp",
                "prev_content",
                "user_id",
                "prev_rendered_content",
                "prev_rendered_content_version",
            },
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "topic 2",
            },
        )
        self.assert_json_success(result)
        history = orjson.loads(assert_is_not_none(Message.objects.get(id=msg_id).edit_history))
        self.assertEqual(history[0]["prev_topic"], "topic 1")
        self.assertEqual(history[0]["topic"], "topic 2")
        self.assertEqual(history[0]["user_id"], hamlet.id)
        self.assertEqual(
            set(history[0].keys()),
            {"timestamp", "prev_topic", "topic", "user_id"},
        )

        self.login("iago")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": stream_2.id,
            },
        )
        self.assert_json_success(result)
        history = orjson.loads(assert_is_not_none(Message.objects.get(id=msg_id).edit_history))
        self.assertEqual(history[0]["prev_stream"], stream_1.id)
        self.assertEqual(history[0]["stream"], stream_2.id)
        self.assertEqual(history[0]["user_id"], self.example_user("iago").id)
        self.assertEqual(set(history[0].keys()), {"timestamp", "prev_stream", "stream", "user_id"})

        self.login("hamlet")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "content 3",
                "topic": "topic 3",
            },
        )
        self.assert_json_success(result)
        history = orjson.loads(assert_is_not_none(Message.objects.get(id=msg_id).edit_history))
        self.assertEqual(history[0]["prev_content"], "content 2")
        self.assertEqual(history[0]["prev_topic"], "topic 2")
        self.assertEqual(history[0]["topic"], "topic 3")
        self.assertEqual(history[0]["user_id"], hamlet.id)
        self.assertEqual(
            set(history[0].keys()),
            {
                "timestamp",
                "prev_topic",
                "topic",
                "prev_content",
                "user_id",
                "prev_rendered_content",
                "prev_rendered_content_version",
            },
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "content 4",
            },
        )
        self.assert_json_success(result)
        history = orjson.loads(assert_is_not_none(Message.objects.get(id=msg_id).edit_history))
        self.assertEqual(history[0]["prev_content"], "content 3")
        self.assertEqual(history[0]["user_id"], hamlet.id)

        self.login("iago")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "topic 4",
                "stream_id": stream_3.id,
            },
        )
        self.assert_json_success(result)
        history = orjson.loads(assert_is_not_none(Message.objects.get(id=msg_id).edit_history))
        self.assertEqual(history[0]["prev_topic"], "topic 3")
        self.assertEqual(history[0]["topic"], "topic 4")
        self.assertEqual(history[0]["prev_stream"], stream_2.id)
        self.assertEqual(history[0]["stream"], stream_3.id)
        self.assertEqual(history[0]["user_id"], self.example_user("iago").id)
        self.assertEqual(
            set(history[0].keys()),
            {
                "timestamp",
                "prev_topic",
                "topic",
                "prev_stream",
                "stream",
                "user_id",
            },
        )

        # Now, we verify that all of the edits stored in the message.edit_history
        # have the correct data structure
        history = orjson.loads(assert_is_not_none(Message.objects.get(id=msg_id).edit_history))

        self.assertEqual(history[0]["prev_topic"], "topic 3")
        self.assertEqual(history[0]["topic"], "topic 4")
        self.assertEqual(history[0]["stream"], stream_3.id)
        self.assertEqual(history[0]["prev_stream"], stream_2.id)

        self.assertEqual(history[1]["prev_content"], "content 3")

        self.assertEqual(history[2]["prev_topic"], "topic 2")
        self.assertEqual(history[2]["topic"], "topic 3")
        self.assertEqual(history[2]["prev_content"], "content 2")

        self.assertEqual(history[3]["stream"], stream_2.id)
        self.assertEqual(history[3]["prev_stream"], stream_1.id)

        self.assertEqual(history[4]["prev_topic"], "topic 1")
        self.assertEqual(history[4]["topic"], "topic 2")

        self.assertEqual(history[5]["prev_content"], "content 1")

        # Now, we verify that the edit history data sent back has the
        # correct filled-out fields
        message_edit_history = self.client_get(f"/json/messages/{msg_id}/history")

        json_response = orjson.loads(message_edit_history.content)

        # We reverse the message history view output so that the IDs line up with the above.
        message_history = list(reversed(json_response["message_history"]))
        i = 0
        for entry in message_history:
            expected_entries = {"content", "rendered_content", "topic", "timestamp", "user_id"}
            if i in {0, 2, 4}:
                expected_entries.add("prev_topic")
                expected_entries.add("topic")
            if i in {1, 2, 5}:
                expected_entries.add("prev_content")
                expected_entries.add("prev_rendered_content")
                expected_entries.add("content_html_diff")
            if i in {0, 3}:
                expected_entries.add("prev_stream")
                expected_entries.add("stream")
            i += 1
            self.assertEqual(expected_entries, set(entry.keys()))
        self.assert_length(message_history, 7)
        self.assertEqual(message_history[0]["topic"], "topic 4")
        self.assertEqual(message_history[0]["prev_topic"], "topic 3")
        self.assertEqual(message_history[0]["stream"], stream_3.id)
        self.assertEqual(message_history[0]["prev_stream"], stream_2.id)
        self.assertEqual(message_history[0]["content"], "content 4")

        self.assertEqual(message_history[1]["topic"], "topic 3")
        self.assertEqual(message_history[1]["content"], "content 4")
        self.assertEqual(message_history[1]["prev_content"], "content 3")

        self.assertEqual(message_history[2]["topic"], "topic 3")
        self.assertEqual(message_history[2]["prev_topic"], "topic 2")
        self.assertEqual(message_history[2]["content"], "content 3")
        self.assertEqual(message_history[2]["prev_content"], "content 2")

        self.assertEqual(message_history[3]["topic"], "topic 2")
        self.assertEqual(message_history[3]["stream"], stream_2.id)
        self.assertEqual(message_history[3]["prev_stream"], stream_1.id)
        self.assertEqual(message_history[3]["content"], "content 2")

        self.assertEqual(message_history[4]["topic"], "topic 2")
        self.assertEqual(message_history[4]["prev_topic"], "topic 1")
        self.assertEqual(message_history[4]["content"], "content 2")

        self.assertEqual(message_history[5]["topic"], "topic 1")
        self.assertEqual(message_history[5]["content"], "content 2")
        self.assertEqual(message_history[5]["prev_content"], "content 1")

        self.assertEqual(message_history[6]["content"], "content 1")
        self.assertEqual(message_history[6]["topic"], "topic 1")

    def test_edit_message_content_limit(self) -> None:
        def set_message_editing_params(
            allow_message_editing: bool,
            message_content_edit_limit_seconds: Union[int, str],
            edit_topic_policy: int,
        ) -> None:
            result = self.client_patch(
                "/json/realm",
                {
                    "allow_message_editing": orjson.dumps(allow_message_editing).decode(),
                    "message_content_edit_limit_seconds": orjson.dumps(
                        message_content_edit_limit_seconds
                    ).decode(),
                    "edit_topic_policy": edit_topic_policy,
                },
            )
            self.assert_json_success(result)

        def do_edit_message_assert_success(
            id_: int, unique_str: str, topic_only: bool = False
        ) -> None:
            new_topic = "topic" + unique_str
            new_content = "content" + unique_str
            params_dict = {"topic": new_topic}
            if not topic_only:
                params_dict["content"] = new_content
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            self.assert_json_success(result)
            if topic_only:
                self.check_topic(id_, topic_name=new_topic)
            else:
                self.check_message(id_, topic_name=new_topic, content=new_content)

        def do_edit_message_assert_error(
            id_: int, unique_str: str, error: str, topic_only: bool = False
        ) -> None:
            message = Message.objects.get(id=id_)
            old_topic = message.topic_name()
            old_content = message.content
            new_topic = "topic" + unique_str
            new_content = "content" + unique_str
            params_dict = {"topic": new_topic}
            if not topic_only:
                params_dict["content"] = new_content
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            message = Message.objects.get(id=id_)
            self.assert_json_error(result, error)

            msg = Message.objects.get(id=id_)
            self.assertEqual(msg.topic_name(), old_topic)
            self.assertEqual(msg.content, old_content)

        self.login("iago")
        # send a message in the past
        id_ = self.send_stream_message(
            self.example_user("iago"), "Denmark", content="content", topic_name="topic"
        )
        message = Message.objects.get(id=id_)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=180)
        message.save()

        # test the various possible message editing settings
        # high enough time limit, all edits allowed
        set_message_editing_params(True, 240, Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_success(id_, "A")

        # out of time, only topic editing allowed
        set_message_editing_params(True, 120, Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_success(id_, "B", True)
        do_edit_message_assert_error(id_, "C", "The time limit for editing this message has passed")

        # infinite time, all edits allowed
        set_message_editing_params(True, "unlimited", Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_success(id_, "D")

        # without allow_message_editing, editing content is not allowed but
        # editing topic is allowed if topic-edit time limit has not passed
        # irrespective of content-edit time limit.
        set_message_editing_params(False, 240, Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_success(id_, "B", True)

        set_message_editing_params(False, 240, Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_success(id_, "E", True)
        set_message_editing_params(False, 120, Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_success(id_, "F", True)
        set_message_editing_params(False, "unlimited", Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_success(id_, "G", True)

    def test_edit_topic_policy(self) -> None:
        def set_message_editing_params(
            allow_message_editing: bool,
            message_content_edit_limit_seconds: Union[int, str],
            edit_topic_policy: int,
        ) -> None:
            self.login("iago")
            result = self.client_patch(
                "/json/realm",
                {
                    "allow_message_editing": orjson.dumps(allow_message_editing).decode(),
                    "message_content_edit_limit_seconds": orjson.dumps(
                        message_content_edit_limit_seconds
                    ).decode(),
                    "edit_topic_policy": edit_topic_policy,
                },
            )
            self.assert_json_success(result)

        def do_edit_message_assert_success(id_: int, unique_str: str, acting_user: str) -> None:
            self.login(acting_user)
            new_topic = "topic" + unique_str
            params_dict = {"topic": new_topic}
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            self.assert_json_success(result)
            self.check_topic(id_, topic_name=new_topic)

        def do_edit_message_assert_error(
            id_: int, unique_str: str, error: str, acting_user: str
        ) -> None:
            self.login(acting_user)
            message = Message.objects.get(id=id_)
            old_topic = message.topic_name()
            old_content = message.content
            new_topic = "topic" + unique_str
            params_dict = {"topic": new_topic}
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            message = Message.objects.get(id=id_)
            self.assert_json_error(result, error)
            msg = Message.objects.get(id=id_)
            self.assertEqual(msg.topic_name(), old_topic)
            self.assertEqual(msg.content, old_content)

        # send a message in the past
        id_ = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", content="content", topic_name="topic"
        )
        message = Message.objects.get(id=id_)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=180)
        message.save()

        # Guest user must be subscribed to the stream to access the message.
        polonius = self.example_user("polonius")
        self.subscribe(polonius, "Denmark")

        # any user can edit the topic of a message
        set_message_editing_params(True, "unlimited", Realm.POLICY_EVERYONE)
        do_edit_message_assert_success(id_, "A", "polonius")

        # only members can edit topic of a message
        set_message_editing_params(True, "unlimited", Realm.POLICY_MEMBERS_ONLY)
        do_edit_message_assert_error(
            id_, "B", "You don't have permission to edit this message", "polonius"
        )
        do_edit_message_assert_success(id_, "B", "cordelia")

        # only full members can edit topic of a message
        set_message_editing_params(True, "unlimited", Realm.POLICY_FULL_MEMBERS_ONLY)

        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        do_set_realm_property(cordelia.realm, "waiting_period_threshold", 10, acting_user=None)

        cordelia.date_joined = timezone_now() - datetime.timedelta(days=9)
        cordelia.save()
        hamlet.date_joined = timezone_now() - datetime.timedelta(days=9)
        hamlet.save()
        do_edit_message_assert_error(
            id_, "C", "You don't have permission to edit this message", "cordelia"
        )
        # User who sent the message but is not a full member cannot edit
        # the topic
        do_edit_message_assert_error(
            id_, "C", "You don't have permission to edit this message", "hamlet"
        )

        cordelia.date_joined = timezone_now() - datetime.timedelta(days=11)
        cordelia.save()
        hamlet.date_joined = timezone_now() - datetime.timedelta(days=11)
        hamlet.save()
        do_edit_message_assert_success(id_, "C", "cordelia")
        do_edit_message_assert_success(id_, "CD", "hamlet")

        # only moderators can edit topic of a message
        set_message_editing_params(True, "unlimited", Realm.POLICY_MODERATORS_ONLY)
        do_edit_message_assert_error(
            id_, "D", "You don't have permission to edit this message", "cordelia"
        )
        # even user who sent the message but is not a moderator cannot edit the topic.
        do_edit_message_assert_error(
            id_, "D", "You don't have permission to edit this message", "hamlet"
        )
        do_edit_message_assert_success(id_, "D", "shiva")

        # only admins can edit the topics of messages
        set_message_editing_params(True, "unlimited", Realm.POLICY_ADMINS_ONLY)
        do_edit_message_assert_error(
            id_, "E", "You don't have permission to edit this message", "shiva"
        )
        do_edit_message_assert_success(id_, "E", "iago")

        # even owners and admins cannot edit the topics of messages
        set_message_editing_params(True, "unlimited", Realm.POLICY_NOBODY)
        do_edit_message_assert_error(
            id_, "H", "You don't have permission to edit this message", "desdemona"
        )
        do_edit_message_assert_error(
            id_, "H", "You don't have permission to edit this message", "iago"
        )

        # users can edit topics even if allow_message_editing is False
        set_message_editing_params(False, "unlimited", Realm.POLICY_EVERYONE)
        do_edit_message_assert_success(id_, "D", "cordelia")

        # non-admin users cannot edit topics sent > 1 week ago including
        # sender of the message.
        message.date_sent = message.date_sent - datetime.timedelta(seconds=604900)
        message.save()
        set_message_editing_params(True, "unlimited", Realm.POLICY_EVERYONE)
        do_edit_message_assert_success(id_, "E", "iago")
        do_edit_message_assert_success(id_, "F", "shiva")
        do_edit_message_assert_error(
            id_, "G", "The time limit for editing this message's topic has passed.", "cordelia"
        )
        do_edit_message_assert_error(
            id_, "G", "The time limit for editing this message's topic has passed.", "hamlet"
        )

        # topic edit permissions apply on "no topic" messages as well
        message.set_topic_name("(no topic)")
        message.save()
        do_edit_message_assert_error(
            id_, "G", "The time limit for editing this message's topic has passed.", "cordelia"
        )

        # set the topic edit limit to two weeks
        do_set_realm_property(
            hamlet.realm,
            "move_messages_within_stream_limit_seconds",
            604800 * 2,
            acting_user=None,
        )
        do_edit_message_assert_success(id_, "G", "cordelia")
        do_edit_message_assert_success(id_, "H", "hamlet")

    @mock.patch("zerver.actions.message_edit.send_event")
    def test_edit_topic_public_history_stream(self, mock_send_event: mock.MagicMock) -> None:
        stream_name = "Macbeth"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(hamlet, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(hamlet, stream_name, "Where am I?")

        self.login_user(cordelia)
        self.subscribe(cordelia, stream_name)
        message = Message.objects.get(id=message_id)

        def do_update_message_topic_success(
            user_profile: UserProfile,
            message: Message,
            topic_name: str,
            users_to_be_notified: List[Dict[str, Any]],
        ) -> None:
            do_update_message(
                user_profile=user_profile,
                target_message=message,
                new_stream=None,
                topic_name=topic_name,
                propagate_mode="change_later",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
                rendering_result=None,
                prior_mention_user_ids=set(),
                mention_data=None,
            )

            mock_send_event.assert_called_with(mock.ANY, mock.ANY, users_to_be_notified)

        # Returns the users that need to be notified when a message topic is changed
        def notify(user_id: int) -> Dict[str, Any]:
            um = UserMessage.objects.get(message=message_id)
            if um.user_profile_id == user_id:
                return {
                    "id": user_id,
                    "flags": um.flags_list(),
                }

            else:
                return {
                    "id": user_id,
                    "flags": ["read"],
                }

        users_to_be_notified = list(map(notify, [hamlet.id, cordelia.id]))
        # Edit topic of a message sent before Cordelia subscribed the stream
        do_update_message_topic_success(
            cordelia, message, "Othello eats apple", users_to_be_notified
        )

        # If Cordelia is long-term idle, she doesn't get a notification.
        cordelia.long_term_idle = True
        cordelia.save()
        users_to_be_notified = list(map(notify, [hamlet.id]))
        do_update_message_topic_success(
            cordelia, message, "Another topic idle", users_to_be_notified
        )
        cordelia.long_term_idle = False
        cordelia.save()

        # Even if Hamlet unsubscribes the stream, he should be notified when the topic is changed
        # because he has a UserMessage row.
        self.unsubscribe(hamlet, stream_name)
        users_to_be_notified = list(map(notify, [hamlet.id, cordelia.id]))
        do_update_message_topic_success(cordelia, message, "Another topic", users_to_be_notified)

        # Hamlet subscribes to the stream again and Cordelia unsubscribes, then Hamlet changes
        # the message topic. Cordelia won't receive any updates when a message on that stream is
        # changed because she is not a subscriber and doesn't have a UserMessage row.
        self.subscribe(hamlet, stream_name)
        self.unsubscribe(cordelia, stream_name)
        self.login_user(hamlet)
        users_to_be_notified = list(map(notify, [hamlet.id]))
        do_update_message_topic_success(hamlet, message, "Change again", users_to_be_notified)

    @mock.patch("zerver.actions.user_topics.send_event")
    def test_edit_muted_topic(self, mock_send_event: mock.MagicMock) -> None:
        stream_name = "Stream 123"
        stream = self.make_stream(stream_name)
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")
        self.subscribe(hamlet, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(
            hamlet, stream_name, topic_name="Topic1", content="Hello World"
        )

        self.subscribe(cordelia, stream_name)
        self.login_user(cordelia)
        self.subscribe(aaron, stream_name)
        self.login_user(aaron)

        def assert_is_topic_muted(
            user_profile: UserProfile,
            stream_id: int,
            topic_name: str,
            *,
            muted: bool,
        ) -> None:
            if muted:
                self.assertTrue(
                    topic_has_visibility_policy(
                        user_profile, stream_id, topic_name, UserTopic.VisibilityPolicy.MUTED
                    )
                )
            else:
                self.assertFalse(
                    topic_has_visibility_policy(
                        user_profile, stream_id, topic_name, UserTopic.VisibilityPolicy.MUTED
                    )
                )

        already_muted_topic = "Already muted topic"
        muted_topics = [
            [stream_name, "Topic1"],
            [stream_name, "Topic2"],
            [stream_name, already_muted_topic],
        ]
        set_topic_visibility_policy(hamlet, muted_topics, UserTopic.VisibilityPolicy.MUTED)
        set_topic_visibility_policy(cordelia, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        # users that need to be notified by send_event in the case of change-topic-name operation.
        users_to_be_notified_via_muted_topics_event: List[int] = []
        users_to_be_notified_via_user_topic_event: List[int] = []
        for user_topic in get_users_with_user_topic_visibility_policy(stream.id, "Topic1"):
            # We are appending the same data twice because 'user_topic' event notifies
            # the user during delete and create operation.
            users_to_be_notified_via_user_topic_event.append(user_topic.user_profile_id)
            users_to_be_notified_via_user_topic_event.append(user_topic.user_profile_id)
            # 'muted_topics' event notifies the user of muted topics during create
            # operation only.
            users_to_be_notified_via_muted_topics_event.append(user_topic.user_profile_id)

        change_all_topic_name = "Topic 1 edited"
        # Verify how many total database queries are required. We
        # expect 6 queries (4/visibility_policy to update the muted
        # state + 1/user with a UserTopic row for the events data)
        # beyond what is typical were there not UserTopic records to
        # update. Ideally, we'd eliminate the per-user component.
        with self.assert_database_query_count(23):
            check_update_message(
                user_profile=hamlet,
                message_id=message_id,
                stream_id=None,
                topic_name=change_all_topic_name,
                propagate_mode="change_all",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
            )

        # Extract the send_event call where event type is 'user_topic' or 'muted_topics.
        # Here we assert that the expected users are notified properly.
        users_notified_via_muted_topics_event: List[int] = []
        users_notified_via_user_topic_event: List[int] = []
        for call_args in mock_send_event.call_args_list:
            (arg_realm, arg_event, arg_notified_users) = call_args[0]
            if arg_event["type"] == "user_topic":
                users_notified_via_user_topic_event.append(*arg_notified_users)
            elif arg_event["type"] == "muted_topics":
                users_notified_via_muted_topics_event.append(*arg_notified_users)
        self.assertEqual(
            sorted(users_notified_via_muted_topics_event),
            sorted(users_to_be_notified_via_muted_topics_event),
        )
        self.assertEqual(
            sorted(users_notified_via_user_topic_event),
            sorted(users_to_be_notified_via_user_topic_event),
        )

        assert_is_topic_muted(hamlet, stream.id, "Topic1", muted=False)
        assert_is_topic_muted(cordelia, stream.id, "Topic1", muted=False)
        assert_is_topic_muted(aaron, stream.id, "Topic1", muted=False)
        assert_is_topic_muted(hamlet, stream.id, "Topic2", muted=True)
        assert_is_topic_muted(cordelia, stream.id, "Topic2", muted=True)
        assert_is_topic_muted(aaron, stream.id, "Topic2", muted=False)
        assert_is_topic_muted(hamlet, stream.id, change_all_topic_name, muted=True)
        assert_is_topic_muted(cordelia, stream.id, change_all_topic_name, muted=True)
        assert_is_topic_muted(aaron, stream.id, change_all_topic_name, muted=False)

        change_later_topic_name = "Topic 1 edited again"
        check_update_message(
            user_profile=hamlet,
            message_id=message_id,
            stream_id=None,
            topic_name=change_later_topic_name,
            propagate_mode="change_later",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )
        assert_is_topic_muted(hamlet, stream.id, change_all_topic_name, muted=False)
        assert_is_topic_muted(hamlet, stream.id, change_later_topic_name, muted=True)

        # Make sure we safely handle the case of the new topic being already muted.
        check_update_message(
            user_profile=hamlet,
            message_id=message_id,
            stream_id=None,
            topic_name=already_muted_topic,
            propagate_mode="change_all",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )
        assert_is_topic_muted(hamlet, stream.id, change_later_topic_name, muted=False)
        assert_is_topic_muted(hamlet, stream.id, already_muted_topic, muted=True)

        change_one_topic_name = "Topic 1 edited change_one"
        check_update_message(
            user_profile=hamlet,
            message_id=message_id,
            stream_id=None,
            topic_name=change_one_topic_name,
            propagate_mode="change_one",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )
        assert_is_topic_muted(hamlet, stream.id, change_one_topic_name, muted=True)
        assert_is_topic_muted(hamlet, stream.id, change_later_topic_name, muted=False)

        # Move topic between two public streams.
        desdemona = self.example_user("desdemona")
        message_id = self.send_stream_message(
            hamlet, stream_name, topic_name="New topic", content="Hello World"
        )
        new_public_stream = self.make_stream("New public stream")
        self.subscribe(desdemona, new_public_stream.name)
        self.login_user(desdemona)
        muted_topics = [
            [stream_name, "New topic"],
        ]
        set_topic_visibility_policy(desdemona, muted_topics, UserTopic.VisibilityPolicy.MUTED)
        set_topic_visibility_policy(cordelia, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        with self.assert_database_query_count(29):
            check_update_message(
                user_profile=desdemona,
                message_id=message_id,
                stream_id=new_public_stream.id,
                propagate_mode="change_all",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
            )

        assert_is_topic_muted(desdemona, stream.id, "New topic", muted=False)
        assert_is_topic_muted(cordelia, stream.id, "New topic", muted=False)
        assert_is_topic_muted(aaron, stream.id, "New topic", muted=False)
        assert_is_topic_muted(desdemona, new_public_stream.id, "New topic", muted=True)
        assert_is_topic_muted(cordelia, new_public_stream.id, "New topic", muted=True)
        assert_is_topic_muted(aaron, new_public_stream.id, "New topic", muted=False)

        # Move topic to a private stream.
        message_id = self.send_stream_message(
            hamlet, stream_name, topic_name="New topic", content="Hello World"
        )
        new_private_stream = self.make_stream("New private stream", invite_only=True)
        self.subscribe(desdemona, new_private_stream.name)
        self.login_user(desdemona)
        muted_topics = [
            [stream_name, "New topic"],
        ]
        set_topic_visibility_policy(desdemona, muted_topics, UserTopic.VisibilityPolicy.MUTED)
        set_topic_visibility_policy(cordelia, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        with self.assert_database_query_count(34):
            check_update_message(
                user_profile=desdemona,
                message_id=message_id,
                stream_id=new_private_stream.id,
                propagate_mode="change_all",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
            )

        # Cordelia is not subscribed to the private stream, so
        # Cordelia should have had the topic unmuted, while Desdemona
        # should have had her muted topic record moved.
        assert_is_topic_muted(desdemona, stream.id, "New topic", muted=False)
        assert_is_topic_muted(cordelia, stream.id, "New topic", muted=False)
        assert_is_topic_muted(aaron, stream.id, "New topic", muted=False)
        assert_is_topic_muted(desdemona, new_private_stream.id, "New topic", muted=True)
        assert_is_topic_muted(cordelia, new_private_stream.id, "New topic", muted=False)
        assert_is_topic_muted(aaron, new_private_stream.id, "New topic", muted=False)

        # Move topic between two public streams with change in topic name.
        desdemona = self.example_user("desdemona")
        message_id = self.send_stream_message(
            hamlet, stream_name, topic_name="New topic 2", content="Hello World"
        )
        self.login_user(desdemona)
        muted_topics = [
            [stream_name, "New topic 2"],
        ]
        set_topic_visibility_policy(desdemona, muted_topics, UserTopic.VisibilityPolicy.MUTED)
        set_topic_visibility_policy(cordelia, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        with self.assert_database_query_count(29):
            check_update_message(
                user_profile=desdemona,
                message_id=message_id,
                stream_id=new_public_stream.id,
                topic_name="changed topic name",
                propagate_mode="change_all",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
            )

        assert_is_topic_muted(desdemona, stream.id, "New topic 2", muted=False)
        assert_is_topic_muted(cordelia, stream.id, "New topic 2", muted=False)
        assert_is_topic_muted(aaron, stream.id, "New topic 2", muted=False)
        assert_is_topic_muted(desdemona, new_public_stream.id, "changed topic name", muted=True)
        assert_is_topic_muted(cordelia, new_public_stream.id, "changed topic name", muted=True)
        assert_is_topic_muted(aaron, new_public_stream.id, "changed topic name", muted=False)

        # Moving only half the messages doesn't move UserTopic records.
        second_message_id = self.send_stream_message(
            hamlet, stream_name, topic_name="changed topic name", content="Second message"
        )
        with self.assert_database_query_count(25):
            check_update_message(
                user_profile=desdemona,
                message_id=second_message_id,
                stream_id=new_public_stream.id,
                topic_name="final topic name",
                propagate_mode="change_later",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
            )

        assert_is_topic_muted(desdemona, new_public_stream.id, "changed topic name", muted=True)
        assert_is_topic_muted(cordelia, new_public_stream.id, "changed topic name", muted=True)
        assert_is_topic_muted(aaron, new_public_stream.id, "changed topic name", muted=False)
        assert_is_topic_muted(desdemona, new_public_stream.id, "final topic name", muted=False)
        assert_is_topic_muted(cordelia, new_public_stream.id, "final topic name", muted=False)
        assert_is_topic_muted(aaron, new_public_stream.id, "final topic name", muted=False)

    @mock.patch("zerver.actions.user_topics.send_event")
    def test_edit_unmuted_topic(self, mock_send_event: mock.MagicMock) -> None:
        stream_name = "Stream 123"
        stream = self.make_stream(stream_name)

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")
        othello = self.example_user("othello")

        def assert_has_visibility_policy(
            user_profile: UserProfile,
            topic_name: str,
            visibility_policy: int,
            *,
            expected: bool,
        ) -> None:
            if expected:
                self.assertTrue(
                    topic_has_visibility_policy(
                        user_profile, stream.id, topic_name, visibility_policy
                    )
                )
            else:
                self.assertFalse(
                    topic_has_visibility_policy(
                        user_profile, stream.id, topic_name, visibility_policy
                    )
                )

        self.subscribe(hamlet, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(
            hamlet, stream_name, topic_name="Topic1", content="Hello World"
        )

        self.subscribe(cordelia, stream_name)
        self.login_user(cordelia)
        self.subscribe(aaron, stream_name)
        self.login_user(aaron)
        self.subscribe(othello, stream_name)
        self.login_user(othello)

        # Initially, hamlet and othello set visibility_policy as UNMUTED for 'Topic1' and 'Topic2',
        # cordelia sets visibility_policy as MUTED for 'Topic1' and 'Topic2', while
        # aaron doesn't have a visibility_policy set for 'Topic1' or 'Topic2'.
        #
        # After moving messages from 'Topic1' to 'Topic 1 edited', the expected behaviour is:
        # hamlet and othello have UNMUTED 'Topic 1 edited' and no visibility_policy set for 'Topic1'
        # cordelia has MUTED 'Topic 1 edited' and no visibility_policy set for 'Topic1'
        #
        # There is no change in visibility_policy configurations for 'Topic2', i.e.
        # hamlet and othello have UNMUTED 'Topic2' + cordelia has MUTED 'Topic2'
        # aaron still doesn't have visibility_policy set for any topic.
        #
        # Note: We have used two users with UNMUTED 'Topic1' to verify that the query count
        # doesn't increase (in order to update UserTopic records) with an increase in users.
        # (We are using bulk database operations.)
        # 1 query/user is added in order to send muted_topics event.(which will be deprecated)
        topics = [
            [stream_name, "Topic1"],
            [stream_name, "Topic2"],
        ]
        set_topic_visibility_policy(hamlet, topics, UserTopic.VisibilityPolicy.UNMUTED)
        set_topic_visibility_policy(cordelia, topics, UserTopic.VisibilityPolicy.MUTED)
        set_topic_visibility_policy(othello, topics, UserTopic.VisibilityPolicy.UNMUTED)

        # users that need to be notified by send_event in the case of change-topic-name operation.
        users_to_be_notified_via_muted_topics_event: List[int] = []
        users_to_be_notified_via_user_topic_event: List[int] = []
        for user_topic in get_users_with_user_topic_visibility_policy(stream.id, "Topic1"):
            # We are appending the same data twice because 'user_topic' event notifies
            # the user during delete and create operation.
            users_to_be_notified_via_user_topic_event.append(user_topic.user_profile_id)
            users_to_be_notified_via_user_topic_event.append(user_topic.user_profile_id)
            # 'muted_topics' event notifies the user of muted topics during create
            # operation only.
            users_to_be_notified_via_muted_topics_event.append(user_topic.user_profile_id)

        change_all_topic_name = "Topic 1 edited"
        with self.assert_database_query_count(28):
            check_update_message(
                user_profile=hamlet,
                message_id=message_id,
                stream_id=None,
                topic_name=change_all_topic_name,
                propagate_mode="change_all",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
            )

        # Extract the send_event call where event type is 'user_topic' or 'muted_topics.
        # Here we assert that the expected users are notified properly.
        users_notified_via_muted_topics_event: List[int] = []
        users_notified_via_user_topic_event: List[int] = []
        for call_args in mock_send_event.call_args_list:
            (arg_realm, arg_event, arg_notified_users) = call_args[0]
            if arg_event["type"] == "user_topic":
                users_notified_via_user_topic_event.append(*arg_notified_users)
            elif arg_event["type"] == "muted_topics":
                users_notified_via_muted_topics_event.append(*arg_notified_users)
        self.assertEqual(
            sorted(users_notified_via_muted_topics_event),
            sorted(users_to_be_notified_via_muted_topics_event),
        )
        self.assertEqual(
            sorted(users_notified_via_user_topic_event),
            sorted(users_to_be_notified_via_user_topic_event),
        )

        # No visibility_policy set for 'Topic1'
        assert_has_visibility_policy(
            hamlet, "Topic1", UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        assert_has_visibility_policy(
            cordelia, "Topic1", UserTopic.VisibilityPolicy.MUTED, expected=False
        )
        assert_has_visibility_policy(
            othello, "Topic1", UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        assert_has_visibility_policy(
            aaron, "Topic1", UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        # No change in visibility_policy configurations for 'Topic2'
        assert_has_visibility_policy(
            hamlet, "Topic2", UserTopic.VisibilityPolicy.UNMUTED, expected=True
        )
        assert_has_visibility_policy(
            cordelia, "Topic2", UserTopic.VisibilityPolicy.MUTED, expected=True
        )
        assert_has_visibility_policy(
            othello, "Topic2", UserTopic.VisibilityPolicy.UNMUTED, expected=True
        )
        assert_has_visibility_policy(
            aaron, "Topic2", UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        # UserTopic records moved to 'Topic 1 edited' after move-topic operation.
        assert_has_visibility_policy(
            hamlet, change_all_topic_name, UserTopic.VisibilityPolicy.UNMUTED, expected=True
        )
        assert_has_visibility_policy(
            cordelia, change_all_topic_name, UserTopic.VisibilityPolicy.MUTED, expected=True
        )
        assert_has_visibility_policy(
            othello, change_all_topic_name, UserTopic.VisibilityPolicy.UNMUTED, expected=True
        )
        assert_has_visibility_policy(
            aaron, change_all_topic_name, UserTopic.VisibilityPolicy.MUTED, expected=False
        )

    def test_merge_user_topic_states_on_move_messages(self) -> None:
        stream_name = "Stream 123"
        stream = self.make_stream(stream_name)

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")

        def assert_has_visibility_policy(
            user_profile: UserProfile,
            topic_name: str,
            visibility_policy: int,
        ) -> None:
            self.assertTrue(
                topic_has_visibility_policy(user_profile, stream.id, topic_name, visibility_policy)
            )

        self.subscribe(hamlet, stream_name)
        self.login_user(hamlet)
        self.subscribe(cordelia, stream_name)
        self.login_user(cordelia)
        self.subscribe(aaron, stream_name)
        self.login_user(aaron)

        # Test the following cases:
        #
        #  orig_topic | target_topic | final behaviour
        #   INHERIT       INHERIT       INHERIT
        #   INHERIT        MUTED        INHERIT
        #   INHERIT       UNMUTED       UNMUTED
        orig_topic = "Topic1"
        target_topic = "Topic1 edited"
        orig_message_id = self.send_stream_message(
            hamlet, stream_name, topic_name=orig_topic, content="Hello World"
        )
        self.send_stream_message(
            hamlet, stream_name, topic_name=target_topic, content="Hello World 2"
        )

        # By default:
        # visibility_policy of 'hamlet', 'cordelia', 'aaron' for 'orig_topic': INHERIT
        # visibility_policy of 'hamlet' for 'target_topic': INHERIT
        #
        # So we don't need to manually set visibility_policy to INHERIT whenever required,
        # here and later in this test.
        do_set_user_topic_visibility_policy(
            cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )

        check_update_message(
            user_profile=hamlet,
            message_id=orig_message_id,
            stream_id=None,
            topic_name=target_topic,
            propagate_mode="change_all",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )

        assert_has_visibility_policy(hamlet, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(cordelia, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(aaron, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(hamlet, target_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(cordelia, target_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(aaron, target_topic, UserTopic.VisibilityPolicy.UNMUTED)

        # Test the following cases:
        #
        #  orig_topic | target_topic | final behaviour
        #     MUTED       INHERIT        INHERIT
        #     MUTED        MUTED          MUTED
        #     MUTED       UNMUTED        UNMUTED
        orig_topic = "Topic2"
        target_topic = "Topic2 edited"
        orig_message_id = self.send_stream_message(
            hamlet, stream_name, topic_name=orig_topic, content="Hello World"
        )
        self.send_stream_message(
            hamlet, stream_name, topic_name=target_topic, content="Hello World 2"
        )

        do_set_user_topic_visibility_policy(
            hamlet, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )

        check_update_message(
            user_profile=hamlet,
            message_id=orig_message_id,
            stream_id=None,
            topic_name=target_topic,
            propagate_mode="change_all",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )

        assert_has_visibility_policy(hamlet, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(cordelia, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(aaron, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(hamlet, target_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(cordelia, target_topic, UserTopic.VisibilityPolicy.MUTED)
        assert_has_visibility_policy(aaron, target_topic, UserTopic.VisibilityPolicy.UNMUTED)

        # Test the following cases:
        #
        #  orig_topic | target_topic | final behaviour
        #    UNMUTED       INHERIT        UNMUTED
        #    UNMUTED        MUTED         UNMUTED
        #    UNMUTED       UNMUTED        UNMUTED
        orig_topic = "Topic3"
        target_topic = "Topic3 edited"
        orig_message_id = self.send_stream_message(
            hamlet, stream_name, topic_name=orig_topic, content="Hello World"
        )
        self.send_stream_message(
            hamlet, stream_name, topic_name=target_topic, content="Hello World 2"
        )

        do_set_user_topic_visibility_policy(
            hamlet, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )

        check_update_message(
            user_profile=hamlet,
            message_id=orig_message_id,
            stream_id=None,
            topic_name=target_topic,
            propagate_mode="change_all",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )

        assert_has_visibility_policy(hamlet, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(cordelia, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(aaron, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(hamlet, target_topic, UserTopic.VisibilityPolicy.UNMUTED)
        assert_has_visibility_policy(cordelia, target_topic, UserTopic.VisibilityPolicy.UNMUTED)
        assert_has_visibility_policy(aaron, target_topic, UserTopic.VisibilityPolicy.UNMUTED)

    def test_user_topic_states_on_moving_to_topic_with_no_messages(self) -> None:
        stream_name = "Stream 123"
        stream = self.make_stream(stream_name)

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")

        self.subscribe(hamlet, stream_name)
        self.subscribe(cordelia, stream_name)
        self.subscribe(aaron, stream_name)

        def assert_has_visibility_policy(
            user_profile: UserProfile,
            topic_name: str,
            visibility_policy: int,
        ) -> None:
            self.assertTrue(
                topic_has_visibility_policy(user_profile, stream.id, topic_name, visibility_policy)
            )

        # Test the case where target topic has no messages:
        #
        #  orig_topic | final behaviour
        #    INHERIT       INHERIT
        #    UNMUTED       UNMUTED
        #    MUTED         MUTED

        orig_topic = "Topic1"
        target_topic = "Topic1 edited"
        orig_message_id = self.send_stream_message(
            hamlet, stream_name, topic_name=orig_topic, content="Hello World"
        )

        do_set_user_topic_visibility_policy(
            hamlet, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )

        check_update_message(
            user_profile=hamlet,
            message_id=orig_message_id,
            stream_id=None,
            topic_name=target_topic,
            propagate_mode="change_all",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )

        assert_has_visibility_policy(hamlet, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(cordelia, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(aaron, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
        assert_has_visibility_policy(hamlet, target_topic, UserTopic.VisibilityPolicy.UNMUTED)
        assert_has_visibility_policy(cordelia, target_topic, UserTopic.VisibilityPolicy.MUTED)
        assert_has_visibility_policy(aaron, target_topic, UserTopic.VisibilityPolicy.INHERIT)

        def test_user_topic_state_for_messages_deleted_from_target_topic(
            orig_topic: str, target_topic: str, original_topic_state: int
        ) -> None:
            # Test the case where target topic has no messages but has UserTopic row
            # due to messages being deleted from the target topic.
            orig_message_id = self.send_stream_message(
                hamlet, stream_name, topic_name=orig_topic, content="Hello World"
            )
            target_message_id = self.send_stream_message(
                hamlet, stream_name, topic_name=target_topic, content="Hello World"
            )

            if original_topic_state != UserTopic.VisibilityPolicy.INHERIT:
                users = [hamlet, cordelia, aaron]
                for user in users:
                    do_set_user_topic_visibility_policy(
                        user, stream, orig_topic, visibility_policy=original_topic_state
                    )

            do_set_user_topic_visibility_policy(
                hamlet, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
            )
            do_set_user_topic_visibility_policy(
                cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
            )

            # Delete the message in target topic to make it empty.
            self.login("hamlet")
            do_set_realm_property(
                hamlet.realm,
                "delete_own_message_policy",
                Realm.POLICY_MEMBERS_ONLY,
                acting_user=None,
            )
            self.client_delete(f"/json/messages/{target_message_id}")

            check_update_message(
                user_profile=hamlet,
                message_id=orig_message_id,
                stream_id=None,
                topic_name=target_topic,
                propagate_mode="change_all",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
            )

            assert_has_visibility_policy(hamlet, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
            assert_has_visibility_policy(cordelia, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
            assert_has_visibility_policy(aaron, orig_topic, UserTopic.VisibilityPolicy.INHERIT)
            assert_has_visibility_policy(hamlet, target_topic, original_topic_state)
            assert_has_visibility_policy(cordelia, target_topic, original_topic_state)
            assert_has_visibility_policy(aaron, target_topic, original_topic_state)

        # orig_topic | target_topic | final behaviour
        #   INHERIT      INHERIT         INHERIT
        #   INHERIT      UNMUTED         INHERIT
        #   INHERIT      MUTED           INHERIT
        test_user_topic_state_for_messages_deleted_from_target_topic(
            orig_topic="Topic2",
            target_topic="Topic2 edited",
            original_topic_state=UserTopic.VisibilityPolicy.INHERIT,
        )

        # orig_topic | target_topic | final behaviour
        #   MUTED      INHERIT         MUTED
        #   MUTED      UNMUTED         MUTED
        #   MUTED      MUTED           MUTED
        test_user_topic_state_for_messages_deleted_from_target_topic(
            orig_topic="Topic3",
            target_topic="Topic3 edited",
            original_topic_state=UserTopic.VisibilityPolicy.MUTED,
        )

        # orig_topic | target_topic | final behaviour
        #   UNMUTED     INHERIT         UNMUTED
        #   UNMUTED     UNMUTED         UNMUTED
        #   UNMUTED     MUTED           UNMUTED
        test_user_topic_state_for_messages_deleted_from_target_topic(
            orig_topic="Topic4",
            target_topic="Topic4 edited",
            original_topic_state=UserTopic.VisibilityPolicy.UNMUTED,
        )

    @mock.patch("zerver.actions.message_edit.send_event")
    def test_topic_wildcard_mention_in_followed_topic(
        self, mock_send_event: mock.MagicMock
    ) -> None:
        stream_name = "Macbeth"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(hamlet, stream_name)
        self.subscribe(cordelia, stream_name)
        self.login_user(hamlet)

        do_set_user_topic_visibility_policy(
            user_profile=hamlet,
            stream=get_stream(stream_name, cordelia.realm),
            topic="test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        message_id = self.send_stream_message(hamlet, stream_name, "Hello everyone")

        users_to_be_notified = sorted(
            [
                {
                    "id": hamlet.id,
                    "flags": ["wildcard_mentioned"],
                },
                {
                    "id": cordelia.id,
                    "flags": [],
                },
            ],
            key=itemgetter("id"),
        )
        result = self.client_patch(
            f"/json/messages/{message_id}",
            {
                "content": "Hello @**topic**",
            },
        )
        self.assert_json_success(result)

        # Extract the send_event call where event type is 'update_message'.
        # Here we assert 'topic_wildcard_mention_in_followed_topic_user_ids'
        # has been set properly.
        called = False
        for call_args in mock_send_event.call_args_list:
            (arg_realm, arg_event, arg_notified_users) = call_args[0]
            if arg_event["type"] == "update_message":
                self.assertEqual(arg_event["type"], "update_message")
                self.assertEqual(
                    arg_event["topic_wildcard_mention_in_followed_topic_user_ids"], [hamlet.id]
                )
                self.assertEqual(
                    sorted(arg_notified_users, key=itemgetter("id")), users_to_be_notified
                )
                called = True
        self.assertTrue(called)

    @mock.patch("zerver.actions.message_edit.send_event")
    def test_stream_wildcard_mention_in_followed_topic(
        self, mock_send_event: mock.MagicMock
    ) -> None:
        stream_name = "Macbeth"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(hamlet, stream_name)
        self.subscribe(cordelia, stream_name)
        self.login_user(hamlet)

        do_set_user_topic_visibility_policy(
            user_profile=hamlet,
            stream=get_stream(stream_name, cordelia.realm),
            topic="test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        message_id = self.send_stream_message(hamlet, stream_name, "Hello everyone")

        def notify(user_id: int) -> Dict[str, Any]:
            return {
                "id": user_id,
                "flags": ["wildcard_mentioned"],
            }

        users_to_be_notified = sorted(map(notify, [cordelia.id, hamlet.id]), key=itemgetter("id"))
        result = self.client_patch(
            f"/json/messages/{message_id}",
            {
                "content": "Hello @**all**",
            },
        )
        self.assert_json_success(result)

        # Extract the send_event call where event type is 'update_message'.
        # Here we assert 'stream_wildcard_mention_in_followed_topic_user_ids'
        # has been set properly.
        called = False
        for call_args in mock_send_event.call_args_list:
            (arg_realm, arg_event, arg_notified_users) = call_args[0]
            if arg_event["type"] == "update_message":
                self.assertEqual(arg_event["type"], "update_message")
                self.assertEqual(
                    arg_event["stream_wildcard_mention_in_followed_topic_user_ids"], [hamlet.id]
                )
                self.assertEqual(
                    sorted(arg_notified_users, key=itemgetter("id")), users_to_be_notified
                )
                called = True
        self.assertTrue(called)

    @mock.patch("zerver.actions.message_edit.send_event")
    def test_topic_wildcard_mention(self, mock_send_event: mock.MagicMock) -> None:
        stream_name = "Macbeth"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(hamlet, stream_name)
        self.subscribe(cordelia, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(hamlet, stream_name, "Hello everyone")

        users_to_be_notified = sorted(
            [
                {
                    "id": hamlet.id,
                    "flags": ["wildcard_mentioned"],
                },
                {
                    "id": cordelia.id,
                    "flags": [],
                },
            ],
            key=itemgetter("id"),
        )
        result = self.client_patch(
            f"/json/messages/{message_id}",
            {
                "content": "Hello @**topic**",
            },
        )
        self.assert_json_success(result)

        # Extract the send_event call where event type is 'update_message'.
        # Here we assert topic_wildcard_mention_user_ids has been set properly.
        called = False
        for call_args in mock_send_event.call_args_list:
            (arg_realm, arg_event, arg_notified_users) = call_args[0]
            if arg_event["type"] == "update_message":
                self.assertEqual(arg_event["type"], "update_message")
                self.assertEqual(arg_event["topic_wildcard_mention_user_ids"], [hamlet.id])
                self.assertEqual(
                    sorted(arg_notified_users, key=itemgetter("id")), users_to_be_notified
                )
                called = True
        self.assertTrue(called)

    def test_topic_wildcard_mention_restrictions_when_editing(self) -> None:
        cordelia = self.example_user("cordelia")
        shiva = self.example_user("shiva")
        self.login("cordelia")
        stream_name = "Macbeth"
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(cordelia, stream_name)
        self.subscribe(shiva, stream_name)
        message_id = self.send_stream_message(cordelia, stream_name, "Hello everyone")

        realm = cordelia.realm
        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_MODERATORS,
            acting_user=None,
        )

        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=17):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**topic**",
                },
            )
        self.assert_json_error(
            result, "You do not have permission to use wildcard mentions in this stream."
        )

        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=14):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**topic**",
                },
            )
        self.assert_json_success(result)

        self.login("shiva")
        message_id = self.send_stream_message(shiva, stream_name, "Hi everyone")
        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=17):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**topic**",
                },
            )
        self.assert_json_success(result)

    @mock.patch("zerver.actions.message_edit.send_event")
    def test_stream_wildcard_mention(self, mock_send_event: mock.MagicMock) -> None:
        stream_name = "Macbeth"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(hamlet, stream_name)
        self.subscribe(cordelia, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(hamlet, stream_name, "Hello everyone")

        def notify(user_id: int) -> Dict[str, Any]:
            return {
                "id": user_id,
                "flags": ["wildcard_mentioned"],
            }

        users_to_be_notified = sorted(map(notify, [cordelia.id, hamlet.id]), key=itemgetter("id"))
        result = self.client_patch(
            f"/json/messages/{message_id}",
            {
                "content": "Hello @**everyone**",
            },
        )
        self.assert_json_success(result)

        # Extract the send_event call where event type is 'update_message'.
        # Here we assert 'stream_wildcard_mention_user_ids' has been set properly.
        called = False
        for call_args in mock_send_event.call_args_list:
            (arg_realm, arg_event, arg_notified_users) = call_args[0]
            if arg_event["type"] == "update_message":
                self.assertEqual(arg_event["type"], "update_message")
                self.assertEqual(
                    arg_event["stream_wildcard_mention_user_ids"], [cordelia.id, hamlet.id]
                )
                self.assertEqual(
                    sorted(arg_notified_users, key=itemgetter("id")), users_to_be_notified
                )
                called = True
        self.assertTrue(called)

    def test_stream_wildcard_mention_restrictions_when_editing(self) -> None:
        cordelia = self.example_user("cordelia")
        shiva = self.example_user("shiva")
        self.login("cordelia")
        stream_name = "Macbeth"
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(cordelia, stream_name)
        self.subscribe(shiva, stream_name)
        message_id = self.send_stream_message(cordelia, stream_name, "Hello everyone")

        realm = cordelia.realm
        do_set_realm_property(
            realm,
            "wildcard_mention_policy",
            Realm.WILDCARD_MENTION_POLICY_MODERATORS,
            acting_user=None,
        )

        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=17):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**everyone**",
                },
            )
        self.assert_json_error(
            result, "You do not have permission to use wildcard mentions in this stream."
        )

        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=14):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**everyone**",
                },
            )
        self.assert_json_success(result)

        self.login("shiva")
        message_id = self.send_stream_message(shiva, stream_name, "Hi everyone")
        with mock.patch("zerver.lib.message.num_subscribers_for_stream_id", return_value=17):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**everyone**",
                },
            )
        self.assert_json_success(result)

    def test_user_group_mention_restrictions_while_editing(self) -> None:
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

        moderators_system_group = UserGroup.objects.get(
            realm=iago.realm, name=UserGroup.MODERATORS_GROUP_NAME, is_system_group=True
        )

        self.login("cordelia")
        msg_id = self.send_stream_message(cordelia, "test_stream", "Test message")
        content = "Edited test message @*leadership*"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

        leadership.can_mention_group = moderators_system_group
        leadership.save()

        msg_id = self.send_stream_message(cordelia, "test_stream", "Test message")
        content = "Edited test message @*leadership*"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_error(
            result,
            f"You are not allowed to mention user group '{leadership.name}'. You must be a member of '{moderators_system_group.name}' to mention this group.",
        )

        # The restriction does not apply on silent mention.
        msg_id = self.send_stream_message(cordelia, "test_stream", "Test message")
        content = "Edited test message @_*leadership*"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

        self.login("shiva")
        content = "Edited test message @*leadership*"
        msg_id = self.send_stream_message(shiva, "test_stream", "Test message")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

        self.login("iago")
        msg_id = self.send_stream_message(iago, "test_stream", "Test message")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

        test = check_add_user_group(shiva.realm, "test", [shiva], acting_user=None)
        add_subgroups_to_user_group(leadership, [test], acting_user=None)
        support.can_mention_group = leadership
        support.save()

        content = "Test mentioning user group @*support*"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_error(
            result,
            f"You are not allowed to mention user group '{support.name}'. You must be a member of '{leadership.name}' to mention this group.",
        )

        msg_id = self.send_stream_message(othello, "test_stream", "Test message")
        self.login("othello")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

        msg_id = self.send_stream_message(shiva, "test_stream", "Test message")
        self.login("shiva")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

        msg_id = self.send_stream_message(iago, "test_stream", "Test message")
        content = "Test mentioning user group @*support* @*leadership*"

        self.login("iago")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_error(
            result,
            f"You are not allowed to mention user group '{support.name}'. You must be a member of '{leadership.name}' to mention this group.",
        )

        msg_id = self.send_stream_message(othello, "test_stream", "Test message")
        self.login("othello")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_error(
            result,
            f"You are not allowed to mention user group '{leadership.name}'. You must be a member of '{moderators_system_group.name}' to mention this group.",
        )

        msg_id = self.send_stream_message(shiva, "test_stream", "Test message")
        self.login("shiva")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

    def test_topic_edit_history_saved_in_all_message(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Verona", topic_name="topic1")
        id4 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic2")
        id5 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic1")

        def verify_edit_history(new_topic: str, len_edit_history: int) -> None:
            for msg_id in [id1, id2, id5]:
                msg = Message.objects.get(id=msg_id)

                self.assertEqual(
                    new_topic,
                    msg.topic_name(),
                )
                # Since edit history is being generated by do_update_message,
                # it's contents can vary over time; So, to keep this test
                # future proof, we only verify it's length.
                self.assert_length(
                    orjson.loads(assert_is_not_none(msg.edit_history)), len_edit_history
                )

            for msg_id in [id3, id4]:
                msg = Message.objects.get(id=msg_id)
                self.assertEqual(msg.edit_history, None)

        new_topic = "edited"
        result = self.client_patch(
            f"/json/messages/{id1}",
            {
                "topic": new_topic,
                "propagate_mode": "change_later",
            },
        )

        self.assert_json_success(result)
        verify_edit_history(new_topic, 1)

        new_topic = "edited2"
        result = self.client_patch(
            f"/json/messages/{id1}",
            {
                "topic": new_topic,
                "propagate_mode": "change_later",
            },
        )

        self.assert_json_success(result)
        verify_edit_history(new_topic, 2)

    def test_topic_and_content_edit(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", "message 1", "topic")
        id2 = self.send_stream_message(self.example_user("iago"), "Denmark", "message 2", "topic")
        id3 = self.send_stream_message(self.example_user("hamlet"), "Denmark", "message 3", "topic")

        new_topic = "edited"
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": new_topic,
                "propagate_mode": "change_later",
                "content": "edited message",
            },
        )

        self.assert_json_success(result)

        # Content change of only id1 should come in edit history
        # and topic change should be present in all the messages.
        msg1 = Message.objects.get(id=id1)
        msg2 = Message.objects.get(id=id2)
        msg3 = Message.objects.get(id=id3)

        msg1_edit_history = orjson.loads(assert_is_not_none(msg1.edit_history))
        self.assertTrue("prev_content" in msg1_edit_history[0])

        for msg in [msg2, msg3]:
            self.assertFalse(
                "prev_content" in orjson.loads(assert_is_not_none(msg.edit_history))[0]
            )

        for msg in [msg1, msg2, msg3]:
            self.assertEqual(
                new_topic,
                msg.topic_name(),
            )
            self.assert_length(orjson.loads(assert_is_not_none(msg.edit_history)), 1)

    def test_propagate_topic_forward(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Verona", topic_name="topic1")
        id4 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic2")
        id5 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic1")

        result = self.client_patch(
            f"/json/messages/{id1}",
            {
                "topic": "edited",
                "propagate_mode": "change_later",
            },
        )
        self.assert_json_success(result)

        self.check_topic(id1, topic_name="edited")
        self.check_topic(id2, topic_name="edited")
        self.check_topic(id3, topic_name="topic1")
        self.check_topic(id4, topic_name="topic2")
        self.check_topic(id5, topic_name="edited")

    def test_propagate_all_topics(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Verona", topic_name="topic1")
        id4 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic2")
        id5 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic1")
        id6 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic3")

        result = self.client_patch(
            f"/json/messages/{id2}",
            {
                "topic": "edited",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        self.check_topic(id1, topic_name="edited")
        self.check_topic(id2, topic_name="edited")
        self.check_topic(id3, topic_name="topic1")
        self.check_topic(id4, topic_name="topic2")
        self.check_topic(id5, topic_name="edited")
        self.check_topic(id6, topic_name="topic3")

    def test_propagate_all_topics_with_different_uppercase_letters(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="Topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Verona", topic_name="topiC1")
        id4 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="toPic1")

        result = self.client_patch(
            f"/json/messages/{id2}",
            {
                "topic": "edited",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        self.check_topic(id1, topic_name="edited")
        self.check_topic(id2, topic_name="edited")
        self.check_topic(id3, topic_name="topiC1")
        self.check_topic(id4, topic_name="edited")

    def test_change_all_propagate_mode_for_moving_old_messages(self) -> None:
        user_profile = self.example_user("hamlet")
        id1 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        id2 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        id3 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        id4 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        self.send_stream_message(user_profile, "Denmark", topic_name="topic1")

        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )

        message = Message.objects.get(id=id1)
        message.date_sent = message.date_sent - datetime.timedelta(days=10)
        message.save()

        message = Message.objects.get(id=id2)
        message.date_sent = message.date_sent - datetime.timedelta(days=8)
        message.save()

        message = Message.objects.get(id=id3)
        message.date_sent = message.date_sent - datetime.timedelta(days=5)
        message.save()

        verona = get_stream("Verona", user_profile.realm)
        denmark = get_stream("Denmark", user_profile.realm)
        old_topic = "topic1"
        old_stream = denmark

        def test_moving_all_topic_messages(
            new_topic: Optional[str] = None, new_stream: Optional[Stream] = None
        ) -> None:
            self.login("hamlet")
            params_dict: Dict[str, Union[str, int]] = {
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            }

            if new_topic is not None:
                params_dict["topic"] = new_topic
            else:
                new_topic = old_topic

            if new_stream is not None:
                params_dict["stream_id"] = new_stream.id
            else:
                new_stream = old_stream

            result = self.client_patch(
                f"/json/messages/{id4}",
                params_dict,
            )
            self.assert_json_error(
                result,
                "You only have permission to move the 3/5 most recent messages in this topic.",
            )
            # Check message count in old topic and/or stream.
            messages = get_topic_messages(user_profile, old_stream, old_topic)
            self.assert_length(messages, 5)

            # Check message count in new topic and/or stream.
            messages = get_topic_messages(user_profile, new_stream, new_topic)
            self.assert_length(messages, 0)

            json = orjson.loads(result.content)
            first_message_id_allowed_to_move = json["first_message_id_allowed_to_move"]

            params_dict["propagate_mode"] = "change_later"
            result = self.client_patch(
                f"/json/messages/{first_message_id_allowed_to_move}",
                params_dict,
            )
            self.assert_json_success(result)

            # Check message count in old topic and/or stream.
            messages = get_topic_messages(user_profile, old_stream, old_topic)
            self.assert_length(messages, 2)

            # Check message count in new topic and/or stream.
            messages = get_topic_messages(user_profile, new_stream, new_topic)
            self.assert_length(messages, 3)

            self.login("shiva")
            # Move these messages to the original topic and stream, to test the case
            # when user is moderator.
            result = self.client_patch(
                f"/json/messages/{id4}",
                {
                    "topic": old_topic,
                    "stream_id": old_stream.id,
                    "propagate_mode": "change_all",
                    "send_notification_to_new_thread": "false",
                },
            )

            params_dict["propagate_mode"] = "change_all"
            result = self.client_patch(
                f"/json/messages/{id4}",
                params_dict,
            )
            self.assert_json_success(result)

            # Check message count in old topic and/or stream.
            messages = get_topic_messages(user_profile, old_stream, old_topic)
            self.assert_length(messages, 0)

            # Check message count in new topic and/or stream.
            messages = get_topic_messages(user_profile, new_stream, new_topic)
            self.assert_length(messages, 5)

        # Test only topic editing case.
        test_moving_all_topic_messages(new_topic="topic edited")

        # Move these messages to the original topic to test the next case.
        self.client_patch(
            f"/json/messages/{id4}",
            {
                "topic": old_topic,
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            },
        )

        # Test only stream editing case
        test_moving_all_topic_messages(new_stream=verona)

        # Move these messages to the original stream to test the next case.
        self.client_patch(
            f"/json/messages/{id4}",
            {
                "stream_id": denmark.id,
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            },
        )

        # Set time limit for moving messages between streams to 2 weeks.
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_limit_seconds",
            604800 * 2,
            acting_user=None,
        )

        # Test editing both topic and stream together.
        test_moving_all_topic_messages(new_topic="edited", new_stream=verona)

        # Move these messages to the original stream and topic to test the next case.
        self.client_patch(
            f"/json/messages/{id4}",
            {
                "stream_id": denmark.id,
                "topic": old_topic,
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            },
        )

        # Test editing both topic and stream with no limit set.
        self.login("hamlet")
        do_set_realm_property(
            user_profile.realm,
            "move_messages_within_stream_limit_seconds",
            None,
            acting_user=None,
        )
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_limit_seconds",
            None,
            acting_user=None,
        )

        new_stream = verona
        new_topic = "edited"
        result = self.client_patch(
            f"/json/messages/{id4}",
            {
                "topic": new_topic,
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            },
        )
        self.assert_json_success(result)
        # Check message count in old topic and/or stream.
        messages = get_topic_messages(user_profile, old_stream, old_topic)
        self.assert_length(messages, 0)

        # Check message count in new topic and/or stream.
        messages = get_topic_messages(user_profile, new_stream, new_topic)
        self.assert_length(messages, 5)

    def test_change_all_propagate_mode_for_moving_from_stream_with_restricted_history(self) -> None:
        self.make_stream("privatestream", invite_only=True, history_public_to_subscribers=False)
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        self.subscribe(iago, "privatestream")
        self.subscribe(cordelia, "privatestream")
        id1 = self.send_stream_message(iago, "privatestream", topic_name="topic1")
        id2 = self.send_stream_message(iago, "privatestream", topic_name="topic1")

        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "privatestream")
        id3 = self.send_stream_message(iago, "privatestream", topic_name="topic1")
        id4 = self.send_stream_message(hamlet, "privatestream", topic_name="topic1")
        self.send_stream_message(hamlet, "privatestream", topic_name="topic1")

        message = Message.objects.get(id=id1)
        message.date_sent = message.date_sent - datetime.timedelta(days=10)
        message.save()

        message = Message.objects.get(id=id2)
        message.date_sent = message.date_sent - datetime.timedelta(days=9)
        message.save()

        message = Message.objects.get(id=id3)
        message.date_sent = message.date_sent - datetime.timedelta(days=8)
        message.save()

        message = Message.objects.get(id=id4)
        message.date_sent = message.date_sent - datetime.timedelta(days=6)
        message.save()

        self.login("hamlet")
        result = self.client_patch(
            f"/json/messages/{id4}",
            {
                "topic": "edited",
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            },
        )
        self.assert_json_error(
            result,
            "You only have permission to move the 2/3 most recent messages in this topic.",
        )

        self.login("cordelia")
        result = self.client_patch(
            f"/json/messages/{id4}",
            {
                "topic": "edited",
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            },
        )
        self.assert_json_error(
            result,
            "You only have permission to move the 2/5 most recent messages in this topic.",
        )

    def test_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago",
            "test move stream",
            "new stream",
            "test",
            # Set the user's translation language to German to test that
            # it is overridden by the realm's default language.
            "de",
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "true",
            },
            HTTP_ACCEPT_LANGUAGE="de",
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_preexisting_topic(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago",
            "test move stream",
            "new stream",
            "test",
            # Set the user's translation language to German to test that
            # it is overridden by the realm's default language.
            "de",
        )

        self.send_stream_message(
            sender=self.example_user("iago"),
            stream_name="new stream",
            topic_name="test",
            content="Always here",
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "true",
            },
            HTTP_ACCEPT_LANGUAGE="de",
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 5)
        self.assertEqual(
            messages[4].content,
            f"3 messages were moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_realm_admin_cant_move_to_another_realm(self) -> None:
        user_profile = self.example_user("iago")
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("iago")

        lear_realm = get_realm("lear")
        new_stream = self.make_stream("new", lear_realm)

        msg_id = self.send_stream_message(user_profile, "Verona", topic_name="test123")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_error(result, "Invalid stream ID")

    def test_move_message_realm_admin_cant_move_to_private_stream_without_subscription(
        self,
    ) -> None:
        user_profile = self.example_user("iago")
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("iago")

        new_stream = self.make_stream("new", invite_only=True)
        msg_id = self.send_stream_message(user_profile, "Verona", topic_name="test123")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_error(result, "Invalid stream ID")

    def test_move_message_realm_admin_cant_move_from_private_stream_without_subscription(
        self,
    ) -> None:
        user_profile = self.example_user("iago")
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("iago")

        self.make_stream("privatestream", invite_only=True)
        self.subscribe(user_profile, "privatestream")
        msg_id = self.send_stream_message(user_profile, "privatestream", topic_name="test123")
        self.unsubscribe(user_profile, "privatestream")

        verona = get_stream("Verona", user_profile.realm)

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": verona.id,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_error(
            result,
            "Invalid message(s)",
        )

    def test_move_message_from_private_stream_message_access_checks(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        user_profile = self.example_user("iago")
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("iago")

        private_stream = self.make_stream(
            "privatestream", invite_only=True, history_public_to_subscribers=False
        )
        self.subscribe(hamlet, "privatestream")
        original_msg_id = self.send_stream_message(hamlet, "privatestream", topic_name="test123")
        self.subscribe(user_profile, "privatestream")
        new_msg_id = self.send_stream_message(user_profile, "privatestream", topic_name="test123")

        # Now we unsub and hamlet sends a new message (we won't have access to it even after re-subbing!)
        self.unsubscribe(user_profile, "privatestream")
        new_inaccessible_msg_id = self.send_stream_message(
            hamlet, "privatestream", topic_name="test123"
        )

        # Re-subscribe and send another message:
        self.subscribe(user_profile, "privatestream")
        newest_msg_id = self.send_stream_message(
            user_profile, "privatestream", topic_name="test123"
        )

        verona = get_stream("Verona", user_profile.realm)

        result = self.client_patch(
            "/json/messages/" + str(new_msg_id),
            {
                "stream_id": verona.id,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_success(result)
        self.assertEqual(Message.objects.get(id=new_msg_id).recipient_id, verona.recipient_id)
        self.assertEqual(Message.objects.get(id=newest_msg_id).recipient_id, verona.recipient_id)
        # The original message and the new, inaccessible message weren't moved,
        # because user_profile doesn't have access to them.
        self.assertEqual(
            Message.objects.get(id=original_msg_id).recipient_id, private_stream.recipient_id
        )
        self.assertEqual(
            Message.objects.get(id=new_inaccessible_msg_id).recipient_id,
            private_stream.recipient_id,
        )

    def test_move_message_to_stream_change_later(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            f"/json/messages/{msg_id_later}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_later",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[1].content,
            f"2 messages were moved from this topic to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 3)
        self.assertEqual(messages[0].id, msg_id_later)
        self.assertEqual(
            messages[2].content,
            f"2 messages were moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_preexisting_topic_change_later(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        self.send_stream_message(
            sender=self.example_user("iago"),
            stream_name="new stream",
            topic_name="test",
            content="Always here",
        )

        result = self.client_patch(
            f"/json/messages/{msg_id_later}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_later",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[1].content,
            f"2 messages were moved from this topic to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 4)
        self.assertEqual(messages[0].id, msg_id_later)
        self.assertEqual(
            messages[3].content,
            f"2 messages were moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_stream_change_later_all_moved(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_later",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 4)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_preexisting_topic_change_later_all_moved(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        self.send_stream_message(
            sender=self.example_user("iago"),
            stream_name="new stream",
            topic_name="test",
            content="Always here",
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_later",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 5)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[4].content,
            f"3 messages were moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_stream_change_one(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            "/json/messages/" + str(msg_id_later),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_one",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 3)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[2].content,
            f"A message was moved from this topic to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        message = {
            "id": msg_id_later,
            "stream_id": new_stream.id,
            "display_recipient": new_stream.name,
            "topic": "test",
        }
        moved_message_link = near_stream_message_url(messages[1].realm, message)
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].id, msg_id_later)
        self.assertEqual(
            messages[1].content,
            f"[A message]({moved_message_link}) was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_preexisting_topic_change_one(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        self.send_stream_message(
            sender=self.example_user("iago"),
            stream_name="new stream",
            topic_name="test",
            content="Always here",
        )

        result = self.client_patch(
            "/json/messages/" + str(msg_id_later),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_one",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 3)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[2].content,
            f"A message was moved from this topic to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        message = {
            "id": msg_id_later,
            "stream_id": new_stream.id,
            "display_recipient": new_stream.name,
            "topic": "test",
        }
        moved_message_link = near_stream_message_url(messages[2].realm, message)
        self.assert_length(messages, 3)
        self.assertEqual(messages[0].id, msg_id_later)
        self.assertEqual(
            messages[2].content,
            f"[A message]({moved_message_link}) was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_stream_change_all(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            "/json/messages/" + str(msg_id_later),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 4)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_to_preexisting_topic_change_all(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        self.send_stream_message(
            sender=self.example_user("iago"),
            stream_name="new stream",
            topic_name="test",
            content="Always here",
        )

        result = self.client_patch(
            "/json/messages/" + str(msg_id_later),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "true",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 5)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(
            messages[4].content,
            f"3 messages were moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_move_message_between_streams_policy_setting(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_1", "new_stream_1", "test"
        )

        def check_move_message_according_to_policy(role: int, expect_fail: bool = False) -> None:
            do_change_user_role(user_profile, role, acting_user=None)

            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "stream_id": new_stream.id,
                    "propagate_mode": "change_all",
                },
            )

            if expect_fail:
                self.assert_json_error(result, "You don't have permission to move this message")
                messages = get_topic_messages(user_profile, old_stream, "test")
                self.assert_length(messages, 3)
                messages = get_topic_messages(user_profile, new_stream, "test")
                self.assert_length(messages, 0)
            else:
                self.assert_json_success(result)
                messages = get_topic_messages(user_profile, old_stream, "test")
                self.assert_length(messages, 0)
                messages = get_topic_messages(user_profile, new_stream, "test")
                self.assert_length(messages, 4)

        # Check sending messages when policy is Realm.POLICY_NOBODY.
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_NOBODY,
            acting_user=None,
        )
        check_move_message_according_to_policy(UserProfile.ROLE_REALM_OWNER, expect_fail=True)
        check_move_message_according_to_policy(
            UserProfile.ROLE_REALM_ADMINISTRATOR, expect_fail=True
        )

        # Check sending messages when policy is Realm.POLICY_ADMINS_ONLY.
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_ADMINS_ONLY,
            acting_user=None,
        )
        check_move_message_according_to_policy(UserProfile.ROLE_MODERATOR, expect_fail=True)
        check_move_message_according_to_policy(UserProfile.ROLE_REALM_ADMINISTRATOR)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_2", "new_stream_2", "test"
        )
        # Check sending messages when policy is Realm.POLICY_MODERATORS_ONLY.
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_MODERATORS_ONLY,
            acting_user=None,
        )
        check_move_message_according_to_policy(UserProfile.ROLE_MEMBER, expect_fail=True)
        check_move_message_according_to_policy(UserProfile.ROLE_MODERATOR)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_3", "new_stream_3", "test"
        )
        # Check sending messages when policy is Realm.POLICY_FULL_MEMBERS_ONLY.
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_FULL_MEMBERS_ONLY,
            acting_user=None,
        )
        do_set_realm_property(
            user_profile.realm, "waiting_period_threshold", 100000, acting_user=None
        )
        check_move_message_according_to_policy(UserProfile.ROLE_MEMBER, expect_fail=True)

        do_set_realm_property(user_profile.realm, "waiting_period_threshold", 0, acting_user=None)
        check_move_message_according_to_policy(UserProfile.ROLE_MEMBER)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_4", "new_stream_4", "test"
        )
        # Check sending messages when policy is Realm.POLICY_MEMBERS_ONLY.
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )
        check_move_message_according_to_policy(UserProfile.ROLE_GUEST, expect_fail=True)
        check_move_message_according_to_policy(UserProfile.ROLE_MEMBER)

    def test_move_message_to_stream_time_limit(self) -> None:
        shiva = self.example_user("shiva")
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")

        test_stream_1 = self.make_stream("test_stream_1")
        test_stream_2 = self.make_stream("test_stream_2")

        self.subscribe(shiva, test_stream_1.name)
        self.subscribe(iago, test_stream_1.name)
        self.subscribe(cordelia, test_stream_1.name)
        self.subscribe(shiva, test_stream_2.name)
        self.subscribe(iago, test_stream_2.name)
        self.subscribe(cordelia, test_stream_2.name)

        msg_id = self.send_stream_message(
            cordelia, test_stream_1.name, topic_name="test", content="First"
        )
        self.send_stream_message(cordelia, test_stream_1.name, topic_name="test", content="Second")

        self.send_stream_message(cordelia, test_stream_1.name, topic_name="test", content="third")

        do_set_realm_property(
            cordelia.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )

        def check_move_message_to_stream(
            user: UserProfile,
            old_stream: Stream,
            new_stream: Stream,
            *,
            expect_error_message: Optional[str] = None,
        ) -> None:
            self.login_user(user)
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "stream_id": new_stream.id,
                    "propagate_mode": "change_all",
                    "send_notification_to_new_thread": orjson.dumps(False).decode(),
                },
            )

            if expect_error_message is not None:
                self.assert_json_error(result, expect_error_message)
                messages = get_topic_messages(user, old_stream, "test")
                self.assert_length(messages, 3)
                messages = get_topic_messages(user, new_stream, "test")
                self.assert_length(messages, 0)
            else:
                self.assert_json_success(result)
                messages = get_topic_messages(user, old_stream, "test")
                self.assert_length(messages, 0)
                messages = get_topic_messages(user, new_stream, "test")
                self.assert_length(messages, 3)

        # non-admin and non-moderator users cannot move messages sent > 1 week ago
        # including sender of the message.
        message = Message.objects.get(id=msg_id)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=604900)
        message.save()
        check_move_message_to_stream(
            cordelia,
            test_stream_1,
            test_stream_2,
            expect_error_message="The time limit for editing this message's stream has passed",
        )

        # admins and moderators can move messages irrespective of time limit.
        check_move_message_to_stream(shiva, test_stream_1, test_stream_2, expect_error_message=None)
        check_move_message_to_stream(iago, test_stream_2, test_stream_1, expect_error_message=None)

        # set the topic edit limit to two weeks
        do_set_realm_property(
            cordelia.realm,
            "move_messages_between_streams_limit_seconds",
            604800 * 2,
            acting_user=None,
        )
        check_move_message_to_stream(
            cordelia, test_stream_1, test_stream_2, expect_error_message=None
        )

    def test_move_message_to_stream_based_on_stream_post_policy(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_1", "new_stream_1", "test"
        )
        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )

        def check_move_message_to_stream(role: int, error_msg: Optional[str] = None) -> None:
            do_change_user_role(user_profile, role, acting_user=None)

            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "stream_id": new_stream.id,
                    "propagate_mode": "change_all",
                },
            )

            if error_msg is not None:
                self.assert_json_error(result, error_msg)
                messages = get_topic_messages(user_profile, old_stream, "test")
                self.assert_length(messages, 3)
                messages = get_topic_messages(user_profile, new_stream, "test")
                self.assert_length(messages, 0)
            else:
                self.assert_json_success(result)
                messages = get_topic_messages(user_profile, old_stream, "test")
                self.assert_length(messages, 0)
                messages = get_topic_messages(user_profile, new_stream, "test")
                self.assert_length(messages, 4)

        # Check when stream_post_policy is STREAM_POST_POLICY_ADMINS.
        do_change_stream_post_policy(
            new_stream, Stream.STREAM_POST_POLICY_ADMINS, acting_user=user_profile
        )
        error_msg = "Only organization administrators can send to this stream."
        check_move_message_to_stream(UserProfile.ROLE_MODERATOR, error_msg)
        check_move_message_to_stream(UserProfile.ROLE_REALM_ADMINISTRATOR)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_2", "new_stream_2", "test"
        )

        # Check when stream_post_policy is STREAM_POST_POLICY_MODERATORS.
        do_change_stream_post_policy(
            new_stream, Stream.STREAM_POST_POLICY_MODERATORS, acting_user=user_profile
        )
        error_msg = "Only organization administrators and moderators can send to this stream."
        check_move_message_to_stream(UserProfile.ROLE_MEMBER, error_msg)
        check_move_message_to_stream(UserProfile.ROLE_MODERATOR)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_3", "new_stream_3", "test"
        )

        # Check when stream_post_policy is STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS.
        do_change_stream_post_policy(
            new_stream, Stream.STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS, acting_user=user_profile
        )
        error_msg = "New members cannot send to this stream."

        do_set_realm_property(
            user_profile.realm, "waiting_period_threshold", 100000, acting_user=None
        )
        check_move_message_to_stream(UserProfile.ROLE_MEMBER, error_msg)

        do_set_realm_property(user_profile.realm, "waiting_period_threshold", 0, acting_user=None)
        check_move_message_to_stream(UserProfile.ROLE_MEMBER)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_4", "new_stream_4", "test"
        )

        # Check when stream_post_policy is STREAM_POST_POLICY_EVERYONE.
        # In this case also, guest is not allowed as we do not allow guest to move
        # messages between streams in any case, so stream_post_policy of new stream does
        # not matter.
        do_change_stream_post_policy(
            new_stream, Stream.STREAM_POST_POLICY_EVERYONE, acting_user=user_profile
        )
        do_set_realm_property(
            user_profile.realm, "waiting_period_threshold", 100000, acting_user=None
        )
        check_move_message_to_stream(
            UserProfile.ROLE_GUEST, "You don't have permission to move this message"
        )
        check_move_message_to_stream(UserProfile.ROLE_MEMBER)

    def test_move_message_to_stream_with_topic_editing_not_allowed(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_1", "new_stream_1", "test"
        )

        realm = user_profile.realm
        realm.edit_topic_policy = Realm.POLICY_ADMINS_ONLY
        realm.save()
        self.login("cordelia")

        do_set_realm_property(
            user_profile.realm,
            "move_messages_between_streams_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "topic": "new topic",
            },
        )
        self.assert_json_error(result, "You don't have permission to edit this message")

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 0)
        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 4)

    def test_move_message_to_stream_and_topic(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        with self.assert_database_query_count(56), self.assert_memcached_count(14):
            result = self.client_patch(
                f"/json/messages/{msg_id}",
                {
                    "propagate_mode": "change_all",
                    "send_notification_to_old_thread": "true",
                    "stream_id": new_stream.id,
                    "topic": "new topic",
                },
            )

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>new topic** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "new topic")
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )
        self.assert_json_success(result)

    def test_inaccessible_msg_after_stream_change(self) -> None:
        """Simulates the case where message is moved to a stream where user is not a subscribed"""
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        guest_user = self.example_user("polonius")
        non_guest_user = self.example_user("hamlet")
        self.subscribe(guest_user, old_stream.name)
        self.subscribe(non_guest_user, old_stream.name)

        msg_id_to_test_acesss = self.send_stream_message(
            user_profile, old_stream.name, topic_name="test", content="fourth"
        )

        self.assertEqual(
            has_message_access(
                guest_user, Message.objects.get(id=msg_id_to_test_acesss), has_user_message=False
            ),
            True,
        )
        self.assertEqual(
            has_message_access(
                guest_user,
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
                stream=old_stream,
            ),
            True,
        )
        self.assertEqual(
            has_message_access(
                non_guest_user,
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
            ),
            True,
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "topic": "new topic",
            },
        )
        self.assert_json_success(result)

        self.assertEqual(
            has_message_access(
                guest_user,
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
            ),
            False,
        )
        self.assertEqual(
            has_message_access(
                non_guest_user,
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
            ),
            True,
        )
        self.assertEqual(
            # If the guest user were subscribed to the new stream,
            # they'd have access; has_message_access does not validate
            # the is_subscribed parameter.
            has_message_access(
                guest_user,
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
                stream=new_stream,
                is_subscribed=True,
            ),
            True,
        )

        self.assertEqual(
            has_message_access(
                guest_user,
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
                stream=new_stream,
            ),
            False,
        )
        with self.assertRaises(AssertionError):
            # Raises assertion if you pass an invalid stream.
            has_message_access(
                guest_user,
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
                stream=old_stream,
            )

        self.assertEqual(
            UserMessage.objects.filter(
                user_profile_id=non_guest_user.id,
                message_id=msg_id_to_test_acesss,
            ).count(),
            0,
        )
        self.assertEqual(
            has_message_access(
                self.example_user("iago"),
                Message.objects.get(id=msg_id_to_test_acesss),
                has_user_message=False,
            ),
            True,
        )

    def test_no_notify_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "false",
                "send_notification_to_new_thread": "false",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 0)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 3)

    def test_notify_new_thread_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "false",
                "send_notification_to_new_thread": "true",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 0)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_notify_old_thread_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "true",
                "send_notification_to_new_thread": "false",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**new stream>test** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 3)

    def test_notify_new_topic(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "false",
                "send_notification_to_new_thread": "true",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 0)

        messages = get_topic_messages(user_profile, stream, "edited")
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**public stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_notify_old_topic(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "true",
                "send_notification_to_new_thread": "false",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**public stream>edited** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, stream, "edited")
        self.assert_length(messages, 3)

    def test_notify_both_topics(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "true",
                "send_notification_to_new_thread": "true",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 1)
        self.assertEqual(
            messages[0].content,
            f"This topic was moved to #**public stream>edited** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, stream, "edited")
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**public stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_notify_no_topic(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_all",
                "send_notification_to_old_thread": "false",
                "send_notification_to_new_thread": "false",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 0)

        messages = get_topic_messages(user_profile, stream, "edited")
        self.assert_length(messages, 3)

    def test_notify_new_topics_after_message_move(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_one",
                "send_notification_to_old_thread": "false",
                "send_notification_to_new_thread": "true",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].content, "Second")
        self.assertEqual(messages[1].content, "Third")

        messages = get_topic_messages(user_profile, stream, "edited")
        message = {
            "id": msg_id,
            "stream_id": stream.id,
            "display_recipient": stream.name,
            "topic": "edited",
        }
        moved_message_link = near_stream_message_url(messages[1].realm, message)
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].content, "First")
        self.assertEqual(
            messages[1].content,
            f"[A message]({moved_message_link}) was moved here from #**public stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_notify_old_topics_after_message_move(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_one",
                "send_notification_to_old_thread": "true",
                "send_notification_to_new_thread": "false",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 3)
        self.assertEqual(messages[0].content, "Second")
        self.assertEqual(messages[1].content, "Third")
        self.assertEqual(
            messages[2].content,
            f"A message was moved from this topic to #**public stream>edited** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, stream, "edited")
        self.assert_length(messages, 1)
        self.assertEqual(messages[0].content, "First")

    def test_notify_both_topics_after_message_move(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_one",
                "send_notification_to_old_thread": "true",
                "send_notification_to_new_thread": "true",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 3)
        self.assertEqual(messages[0].content, "Second")
        self.assertEqual(messages[1].content, "Third")
        self.assertEqual(
            messages[2].content,
            f"A message was moved from this topic to #**public stream>edited** by @_**Iago|{user_profile.id}**.",
        )

        messages = get_topic_messages(user_profile, stream, "edited")
        message = {
            "id": msg_id,
            "stream_id": stream.id,
            "display_recipient": stream.name,
            "topic": "edited",
        }
        moved_message_link = near_stream_message_url(messages[0].realm, message)
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].content, "First")
        self.assertEqual(
            messages[1].content,
            f"[A message]({moved_message_link}) was moved here from #**public stream>test** by @_**Iago|{user_profile.id}**.",
        )

    def test_notify_no_topic_after_message_move(self) -> None:
        user_profile = self.example_user("iago")
        self.login("iago")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Second")
        self.send_stream_message(user_profile, stream.name, topic_name="test", content="Third")

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": "edited",
                "propagate_mode": "change_one",
                "send_notification_to_old_thread": "false",
                "send_notification_to_new_thread": "false",
            },
        )

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, "test")
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].content, "Second")
        self.assertEqual(messages[1].content, "Third")

        messages = get_topic_messages(user_profile, stream, "edited")
        self.assert_length(messages, 1)
        self.assertEqual(messages[0].content, "First")

    def test_notify_resolve_topic_long_name(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login("hamlet")
        stream = self.make_stream("public stream")
        self.subscribe(user_profile, stream.name)
        # Marking topics with a long name as resolved causes the new topic name to be truncated.
        # We want to avoid having code paths believing that the topic is "moved" instead of
        # "resolved" in this edge case.
        topic_name = "a" * MAX_TOPIC_NAME_LENGTH
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name=topic_name, content="First"
        )

        resolved_topic = RESOLVED_TOPIC_PREFIX + topic_name
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": resolved_topic,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        new_topic_name = truncate_topic(resolved_topic)
        messages = get_topic_messages(user_profile, stream, new_topic_name)
        self.assert_length(messages, 2)
        self.assertEqual(messages[0].content, "First")
        self.assertEqual(
            messages[1].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as resolved.",
        )

        # Note that we are removing the prefix from the already truncated topic,
        # so unresolved_topic_name will not be the same as the original topic_name
        unresolved_topic_name = new_topic_name.replace(RESOLVED_TOPIC_PREFIX, "")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": unresolved_topic_name,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, unresolved_topic_name)
        self.assert_length(messages, 3)
        self.assertEqual(
            messages[2].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as unresolved.",
        )

    def test_notify_resolve_and_move_topic(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login("hamlet")
        stream = self.make_stream("public stream")
        topic = "test"
        self.subscribe(user_profile, stream.name)

        # Resolve a topic normally first
        msg_id = self.send_stream_message(user_profile, stream.name, "foo", topic_name=topic)
        resolved_topic = RESOLVED_TOPIC_PREFIX + topic
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": resolved_topic,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, resolved_topic)
        self.assert_length(messages, 2)
        self.assertEqual(
            messages[1].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as resolved.",
        )

        # Test unresolving a topic while moving it (✔ test -> bar)
        new_topic = "bar"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": new_topic,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, stream, new_topic)
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[2].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as unresolved.",
        )
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**public stream>✔ test** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

        # Now test moving the topic while also resolving it (bar -> ✔ baz)
        new_resolved_topic = RESOLVED_TOPIC_PREFIX + "baz"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": new_resolved_topic,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, stream, new_resolved_topic)
        self.assert_length(messages, 6)
        self.assertEqual(
            messages[4].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as resolved.",
        )
        self.assertEqual(
            messages[5].content,
            f"This topic was moved here from #**public stream>{new_topic}** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

    def test_notify_resolve_topic_and_move_stream(self) -> None:
        (
            user_profile,
            first_stream,
            second_stream,
            msg_id,
            msg_id_later,
        ) = self.prepare_move_topics("iago", "first stream", "second stream", "test")

        # 'prepare_move_topics' sends 3 messages in the first_stream
        messages = get_topic_messages(user_profile, first_stream, "test")
        self.assert_length(messages, 3)

        # Test resolving a topic (test ->  ✔ test) while changing stream (first_stream -> second_stream)
        new_topic = "✔ test"
        new_stream = second_stream
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "topic": new_topic,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, new_stream, new_topic)
        self.assert_length(messages, 5)
        self.assertEqual(
            messages[3].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as resolved.",
        )
        self.assertEqual(
            messages[4].content,
            f"This topic was moved here from #**{first_stream.name}>test** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

        # Test unresolving a topic (✔ test -> test) while changing stream (second_stream -> first_stream)
        new_topic = "test"
        new_stream = first_stream
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "topic": new_topic,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, new_stream, new_topic)
        self.assert_length(messages, 7)
        self.assertEqual(
            messages[5].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as unresolved.",
        )
        self.assertEqual(
            messages[6].content,
            f"This topic was moved here from #**{second_stream.name}>✔ test** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

    def parameterized_test_move_message_involving_private_stream(
        self,
        from_invite_only: bool,
        history_public_to_subscribers: bool,
        user_messages_created: bool,
        to_invite_only: bool = True,
    ) -> None:
        admin_user = self.example_user("iago")
        user_losing_access = self.example_user("cordelia")
        user_gaining_access = self.example_user("hamlet")

        self.login("iago")
        old_stream = self.make_stream("test move stream", invite_only=from_invite_only)
        new_stream = self.make_stream(
            "new stream",
            invite_only=to_invite_only,
            history_public_to_subscribers=history_public_to_subscribers,
        )

        self.subscribe(admin_user, old_stream.name)
        self.subscribe(user_losing_access, old_stream.name)

        self.subscribe(admin_user, new_stream.name)
        self.subscribe(user_gaining_access, new_stream.name)

        msg_id = self.send_stream_message(
            admin_user, old_stream.name, topic_name="test", content="First"
        )
        self.send_stream_message(admin_user, old_stream.name, topic_name="test", content="Second")

        self.assertEqual(
            UserMessage.objects.filter(
                user_profile_id=user_losing_access.id,
                message_id=msg_id,
            ).count(),
            1,
        )
        self.assertEqual(
            UserMessage.objects.filter(
                user_profile_id=user_gaining_access.id,
                message_id=msg_id,
            ).count(),
            0,
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        messages = get_topic_messages(admin_user, old_stream, "test")
        self.assert_length(messages, 0)

        messages = get_topic_messages(admin_user, new_stream, "test")
        self.assert_length(messages, 3)

        self.assertEqual(
            UserMessage.objects.filter(
                user_profile_id=user_losing_access.id,
                message_id=msg_id,
            ).count(),
            0,
        )
        # When the history is shared, UserMessage is not created for the user but the user
        # can see the message.
        self.assertEqual(
            UserMessage.objects.filter(
                user_profile_id=user_gaining_access.id,
                message_id=msg_id,
            ).count(),
            1 if user_messages_created else 0,
        )

    def test_move_message_from_public_to_private_stream_not_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=False,
            history_public_to_subscribers=False,
            user_messages_created=True,
        )

    def test_move_message_from_public_to_private_stream_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=False,
            history_public_to_subscribers=True,
            user_messages_created=False,
        )

    def test_move_message_from_private_to_private_stream_not_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=True,
            history_public_to_subscribers=False,
            user_messages_created=True,
        )

    def test_move_message_from_private_to_private_stream_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=True,
            history_public_to_subscribers=True,
            user_messages_created=False,
        )

    def test_move_message_from_private_to_public(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=True,
            history_public_to_subscribers=True,
            user_messages_created=False,
            to_invite_only=False,
        )

    def test_can_move_messages_between_streams(self) -> None:
        def validation_func(user_profile: UserProfile) -> bool:
            return user_profile.can_move_messages_between_streams()

        self.check_has_permission_policies("move_messages_between_streams_policy", validation_func)

    def test_mark_topic_as_resolved(self) -> None:
        self.login("iago")
        admin_user = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")

        # Set the user's translation language to German to test that
        # it is overridden by the realm's default language.
        admin_user.default_language = "de"
        admin_user.save()
        stream = self.make_stream("new")
        self.subscribe(admin_user, stream.name)
        self.subscribe(hamlet, stream.name)
        self.subscribe(cordelia, stream.name)
        self.subscribe(aaron, stream.name)

        original_topic = "topic 1"
        id1 = self.send_stream_message(hamlet, "new", topic_name=original_topic)
        id2 = self.send_stream_message(admin_user, "new", topic_name=original_topic)

        msg1 = Message.objects.get(id=id1)
        do_add_reaction(aaron, msg1, "tada", "1f389", "unicode_emoji")

        # Check that we don't incorrectly send "unresolve topic"
        # notifications when asking the preserve the current topic.
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": original_topic,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(result, "Nothing to change")

        resolved_topic = RESOLVED_TOPIC_PREFIX + original_topic
        result = self.resolve_topic_containing_message(
            admin_user,
            id1,
            HTTP_ACCEPT_LANGUAGE="de",
        )

        self.assert_json_success(result)
        for msg_id in [id1, id2]:
            msg = Message.objects.get(id=msg_id)
            self.assertEqual(
                resolved_topic,
                msg.topic_name(),
            )

        messages = get_topic_messages(admin_user, stream, resolved_topic)
        self.assert_length(messages, 3)
        self.assertEqual(
            messages[2].content,
            f"@_**Iago|{admin_user.id}** has marked this topic as resolved.",
        )

        # Check topic resolved notification message is only unread for participants.
        assert (
            UserMessage.objects.filter(
                user_profile__in=[admin_user, hamlet, aaron], message__id=messages[2].id
            )
            .extra(where=[UserMessage.where_unread()])
            .count()
            == 3
        )

        assert (
            not UserMessage.objects.filter(user_profile=cordelia, message__id=messages[2].id)
            .extra(where=[UserMessage.where_unread()])
            .exists()
        )

        # Now move to a weird state and confirm we get the normal topic moved message.
        weird_topic = "✔ ✔✔" + original_topic
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": weird_topic,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_success(result)
        for msg_id in [id1, id2]:
            msg = Message.objects.get(id=msg_id)
            self.assertEqual(
                weird_topic,
                msg.topic_name(),
            )

        messages = get_topic_messages(admin_user, stream, weird_topic)
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[2].content,
            f"@_**Iago|{admin_user.id}** has marked this topic as resolved.",
        )
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**new>✔ topic 1** by @_**Iago|{admin_user.id}**.",
        )

        unresolved_topic = original_topic
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": unresolved_topic,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_success(result)
        for msg_id in [id1, id2]:
            msg = Message.objects.get(id=msg_id)
            self.assertEqual(
                unresolved_topic,
                msg.topic_name(),
            )

        messages = get_topic_messages(admin_user, stream, unresolved_topic)
        self.assert_length(messages, 5)
        self.assertEqual(
            messages[2].content, f"@_**Iago|{admin_user.id}** has marked this topic as resolved."
        )
        self.assertEqual(
            messages[4].content,
            f"@_**Iago|{admin_user.id}** has marked this topic as unresolved.",
        )

        # Check topic unresolved notification message is only unread for participants.
        assert (
            UserMessage.objects.filter(
                user_profile__in=[admin_user, hamlet, aaron], message__id=messages[4].id
            )
            .extra(where=[UserMessage.where_unread()])
            .count()
            == 3
        )

        assert (
            not UserMessage.objects.filter(user_profile=cordelia, message__id=messages[4].id)
            .extra(where=[UserMessage.where_unread()])
            .exists()
        )


class DeleteMessageTest(ZulipTestCase):
    def test_delete_message_invalid_request_format(self) -> None:
        self.login("iago")
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Denmark")
        result = self.client_delete(f"/json/messages/{msg_id + 1}", {"message_id": msg_id})
        self.assert_json_error(result, "Invalid message(s)")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_success(result)

    def test_delete_message_by_user(self) -> None:
        def set_message_deleting_params(
            delete_own_message_policy: int, message_content_delete_limit_seconds: Union[int, str]
        ) -> None:
            self.login("iago")
            result = self.client_patch(
                "/json/realm",
                {
                    "delete_own_message_policy": delete_own_message_policy,
                    "message_content_delete_limit_seconds": orjson.dumps(
                        message_content_delete_limit_seconds
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def test_delete_message_by_admin(msg_id: int) -> "TestHttpResponse":
            self.login("iago")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_owner(msg_id: int) -> "TestHttpResponse":
            self.login("hamlet")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_other_user(msg_id: int) -> "TestHttpResponse":
            self.login("cordelia")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        # Test if message deleting is not allowed(default).
        set_message_deleting_params(Realm.POLICY_ADMINS_ONLY, "unlimited")
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        msg_id = self.send_stream_message(hamlet, "Denmark")

        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_admin(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if message deleting is allowed.
        # Test if time limit is None(no limit).
        set_message_deleting_params(Realm.POLICY_EVERYONE, "unlimited")
        msg_id = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=600)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if time limit is non-zero.
        set_message_deleting_params(Realm.POLICY_EVERYONE, 240)
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_1)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=120)
        message.save()

        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_2)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=360)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_owner(msg_id=msg_id_1)
        self.assert_json_success(result)
        result = test_delete_message_by_owner(msg_id=msg_id_2)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        # No limit for admin.
        result = test_delete_message_by_admin(msg_id=msg_id_2)
        self.assert_json_success(result)

        # Test multiple delete requests with no latency issues
        msg_id = self.send_stream_message(hamlet, "Denmark")
        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_success(result)
        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Test handling of 500 error caused by multiple delete requests due to latency.
        # see issue #11219.
        with mock.patch("zerver.views.message_edit.do_delete_messages") as m, mock.patch(
            "zerver.views.message_edit.validate_can_delete_message", return_value=None
        ), mock.patch("zerver.views.message_edit.access_message", return_value=(None, None)):
            m.side_effect = IntegrityError()
            result = test_delete_message_by_owner(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")
            m.side_effect = Message.DoesNotExist()
            result = test_delete_message_by_owner(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")

    def test_delete_message_according_to_delete_own_message_policy(self) -> None:
        def check_delete_message_by_sender(
            sender_name: str, error_msg: Optional[str] = None
        ) -> None:
            sender = self.example_user(sender_name)
            msg_id = self.send_stream_message(sender, "Verona")
            self.login_user(sender)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_ADMINS_ONLY, acting_user=None
        )
        check_delete_message_by_sender("shiva", "You don't have permission to delete this message")
        check_delete_message_by_sender("iago")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_MODERATORS_ONLY, acting_user=None
        )
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("shiva")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_MEMBERS_ONLY, acting_user=None
        )
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("cordelia")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_FULL_MEMBERS_ONLY, acting_user=None
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        cordelia = self.example_user("cordelia")
        cordelia.date_joined = timezone_now() - datetime.timedelta(days=9)
        cordelia.save()
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        cordelia.date_joined = timezone_now() - datetime.timedelta(days=11)
        cordelia.save()
        check_delete_message_by_sender("cordelia")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_EVERYONE, acting_user=None
        )
        check_delete_message_by_sender("cordelia")
        check_delete_message_by_sender("polonius")

    def test_delete_event_sent_after_transaction_commits(self) -> None:
        """
        Tests that `send_event` is hooked to `transaction.on_commit`. This is important, because
        we don't want to end up holding locks on message rows for too long if the event queue runs
        into a problem.
        """
        hamlet = self.example_user("hamlet")
        self.send_stream_message(hamlet, "Denmark")
        message = self.get_last_message()

        with self.capture_send_event_calls(expected_num_events=1):
            with mock.patch("zerver.tornado.django_api.queue_json_publish") as m:
                m.side_effect = AssertionError(
                    "Events should be sent only after the transaction commits."
                )
                do_delete_messages(hamlet.realm, [message])

    def test_delete_message_in_unsubscribed_private_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.assertEqual(iago.role, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("hamlet")

        self.make_stream("privatestream", invite_only=True, history_public_to_subscribers=False)
        self.subscribe(hamlet, "privatestream")
        self.subscribe(iago, "privatestream")
        msg_id = self.send_stream_message(
            hamlet, "privatestream", topic_name="editing", content="before edit"
        )
        self.unsubscribe(iago, "privatestream")
        self.logout()
        self.login("iago")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_error(result, "Invalid message(s)")
        self.assertTrue(Message.objects.filter(id=msg_id).exists())

        # Ensure iago can delete the message after resubscribing, to be certain
        # it's the subscribed/unsubscribed status that's the decisive factor in the
        # permission to do so.
        self.subscribe(iago, "privatestream")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_success(result)
        self.assertFalse(Message.objects.filter(id=msg_id).exists())

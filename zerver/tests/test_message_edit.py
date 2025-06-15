from datetime import timedelta
from operator import itemgetter
from unittest import mock

import orjson
import time_machine
from django.utils.timezone import now as timezone_now

from zerver.actions.message_edit import get_mentions_for_message_updates
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_change_realm_plan_type,
    do_set_realm_property,
)
from zerver.actions.streams import do_change_stream_group_based_setting, do_deactivate_stream
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib import utils
from zerver.lib.message import messages_for_ids
from zerver.lib.message_cache import MessageDict
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message, queries_captured
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.utils import assert_is_not_none
from zerver.models import Attachment, Message, NamedUserGroup, Realm, UserProfile, UserTopic
from zerver.models.groups import SystemGroups
from zerver.models.messages import UserMessage
from zerver.models.realms import MessageEditHistoryVisibilityPolicyEnum, get_realm
from zerver.models.streams import get_stream


class EditMessageTest(ZulipTestCase):
    def check_message(self, msg_id: int, topic_name: str, content: str) -> None:
        # Make sure we saved the message correctly to the DB.
        msg = Message.objects.select_related("realm").get(id=msg_id)
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
                allow_empty_topic_name=True,
                message_edit_history_visibility_policy=MessageEditHistoryVisibilityPolicyEnum.all.value,
                user_profile=None,
                realm=msg.realm,
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
            message_edit_history = orjson.loads(msg.edit_history)
            for item in message_edit_history:
                if "prev_rendered_content_version" in item:
                    del item["prev_rendered_content_version"]

            self.assertEqual(
                fetch_message_dict["edit_history"],
                message_edit_history,
            )

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

    def test_query_count_on_messages_to_encoded_cache(self) -> None:
        # `messages_to_encoded_cache` method is used by the mechanisms
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
            MessageDict.messages_to_encoded_cache(messages)

        realm_id = 2  # Fetched from stream object
        # Check number of queries performed with realm_id
        with self.assert_database_query_count(3):
            MessageDict.messages_to_encoded_cache(messages, realm_id)

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
        self.assertEqual(Message.objects.get(id=msg_id).topic_name(), "edited")

    def test_fetch_message_from_id(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login_user(hamlet)

        msg_id = self.send_personal_message(
            from_user=hamlet, to_user=cordelia, content="Outgoing direct message"
        )
        result = self.client_get("/json/messages/" + str(msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "Outgoing direct message")
        self.assertEqual(response_dict["message"]["id"], msg_id)
        self.assertEqual(response_dict["message"]["recipient_id"], cordelia.recipient_id)
        self.assertEqual(response_dict["message"]["flags"], ["read"])

        msg_id = self.send_personal_message(
            from_user=cordelia, to_user=hamlet, content="Incoming direct message"
        )
        result = self.client_get("/json/messages/" + str(msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "Incoming direct message")
        self.assertEqual(response_dict["message"]["id"], msg_id)
        # Incoming DMs show the recipient_id that outgoing DMs would.
        self.assertEqual(response_dict["message"]["recipient_id"], cordelia.recipient_id)
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

        # Verify success with deactivated streams.
        do_deactivate_stream(web_public_stream, acting_user=None)
        result = self.client_get("/json/messages/" + str(web_public_stream_msg_id))
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["raw_content"], "web-public message")
        self.assertEqual(response_dict["message"]["flags"], ["read"])

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
        # Check message edit in stream for no content.
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

        # Check message edit in DMs for no content.
        msg_id = self.send_personal_message(
            from_user=self.example_user("hamlet"), to_user=self.example_user("cordelia")
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

        stream = self.make_stream(
            "privatestream", invite_only=True, history_public_to_subscribers=False
        )
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

        hamlet_group = check_add_user_group(
            hamlet.realm,
            "prospero_group",
            [hamlet],
            acting_user=hamlet,
        )
        do_change_stream_group_based_setting(
            stream,
            "can_add_subscribers_group",
            hamlet_group,
            acting_user=hamlet,
        )
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "having content access after unsubscribing",
            },
        )
        self.assert_json_success(result)
        content = Message.objects.get(id=msg_id).content
        self.assertEqual(content, "having content access after unsubscribing")

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
        do_set_realm_property(
            user_profile.realm,
            "message_edit_history_visibility_policy",
            MessageEditHistoryVisibilityPolicyEnum.none,
            acting_user=None,
        )
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
        message_fetch_result = self.client_get(
            f"/json/messages/{msg_id_1}",
        )
        self.assert_json_success(message_fetch_result)
        message_dict = orjson.loads(message_fetch_result.content)["message"]
        self.assertNotIn("edit_history", message_dict)
        # We still have a last edit timestamp present.
        self.assertIn("last_edit_timestamp", message_dict)

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
            "content before edit, line 1\ncontent after edit, line 2\ncontent before edit, line 3"
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
        message = Message.objects.get(id=msg_id)

        mention_user_ids = get_mentions_for_message_updates(message)
        self.assertEqual(mention_user_ids, {cordelia.id})

    def test_edit_and_moved_timestamps(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        stream_1 = self.make_stream("stream 1")
        stream_2 = self.make_stream("stream 2")
        self.subscribe(hamlet, stream_1.name)
        self.subscribe(hamlet, stream_2.name)
        time_zero = timezone_now().replace(microsecond=0)

        with time_machine.travel(time_zero, tick=False):
            first_message_id = self.send_stream_message(
                self.example_user("hamlet"),
                "stream 1",
                topic_name="topic 1",
                content="content 1",
            )

        first_message_edit_time = time_zero + timedelta(seconds=1)
        with time_machine.travel(first_message_edit_time, tick=False):
            result = self.client_patch(
                f"/json/messages/{first_message_id}",
                {
                    "content": "content 2",
                },
            )
            self.assert_json_success(result)
            message_fetch_result = self.client_get(
                f"/json/messages/{first_message_id}",
            )
            self.assert_json_success(message_fetch_result)
            message_dict = orjson.loads(message_fetch_result.content)["message"]
            self.assertEqual(
                message_dict["last_edit_timestamp"], datetime_to_timestamp(first_message_edit_time)
            )
            self.assertNotIn("last_moved_timestamp", message_dict)

        first_message_move_time = time_zero + timedelta(seconds=2)
        with time_machine.travel(first_message_move_time, tick=False):
            result = self.client_patch(
                f"/json/messages/{first_message_id}",
                {
                    "topic": "topic 2",
                },
            )
            self.assert_json_success(result)
            message_fetch_result = self.client_get(
                f"/json/messages/{first_message_id}",
            )
            self.assert_json_success(message_fetch_result)
            message_dict = orjson.loads(message_fetch_result.content)["message"]
            self.assertEqual(
                message_dict["last_edit_timestamp"], datetime_to_timestamp(first_message_edit_time)
            )
            self.assertEqual(
                message_dict["last_moved_timestamp"], datetime_to_timestamp(first_message_move_time)
            )

        with time_machine.travel(time_zero, tick=False):
            second_message_id = self.send_stream_message(
                self.example_user("hamlet"),
                "stream 2",
                topic_name="topic 2",
                content="content 2",
            )

        second_message_move_time = time_zero + timedelta(minutes=1)
        with time_machine.travel(second_message_move_time, tick=False):
            result = self.client_patch(
                f"/json/messages/{second_message_id}",
                {
                    "stream_id": stream_1.id,
                },
            )
            message_fetch_result = self.client_get(
                f"/json/messages/{second_message_id}",
            )
            self.assert_json_success(message_fetch_result)
            message_dict = orjson.loads(message_fetch_result.content)["message"]
            self.assert_json_success(result)
            self.assertNotIn("last_edit_timestamp", message_dict)
            self.assertEqual(
                message_dict["last_moved_timestamp"],
                datetime_to_timestamp(second_message_move_time),
            )

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
        for i, entry in enumerate(message_history):
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

    def test_visible_edit_history_for_message(self) -> None:
        user = self.example_user("hamlet")
        self.login("hamlet")
        stream_1 = self.make_stream("stream 1")
        stream_2 = self.make_stream("stream 2")
        stream_3 = self.make_stream("stream 3")
        self.subscribe(user, stream_1.name)
        self.subscribe(user, stream_2.name)
        msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            "stream 1",
            topic_name="topic 1",
            content="content 1",
        )

        result_1 = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "content 2",
            },
        )
        self.assert_json_success(result_1)

        result_2 = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "topic 2",
            },
        )
        self.assert_json_success(result_2)

        result_3 = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": stream_2.id,
            },
        )
        self.assert_json_success(result_3)

        result_4 = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "topic 3",
                "content": "content 3",
            },
        )
        self.assert_json_success(result_4)

        result_5 = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "topic 4",
                "stream_id": stream_3.id,
            },
        )
        self.assert_json_success(result_5)

        do_set_realm_property(
            user.realm,
            "message_edit_history_visibility_policy",
            MessageEditHistoryVisibilityPolicyEnum.none,
            acting_user=None,
        )
        result_message_edit_history_none = self.client_get(f"/json/messages/{msg_id}/history")
        self.assert_json_error(
            result_message_edit_history_none,
            "Message edit history is disabled in this organization",
        )

        do_set_realm_property(
            user.realm,
            "message_edit_history_visibility_policy",
            MessageEditHistoryVisibilityPolicyEnum.moves,
            acting_user=None,
        )
        result_message_edit_history_moves_only = self.client_get(f"/json/messages/{msg_id}/history")
        json_response = orjson.loads(result_message_edit_history_moves_only.content)
        message_edit_history_moves_only = json_response["message_history"]

        for edit_history_entry in message_edit_history_moves_only:
            self.assertNotIn("prev_content", edit_history_entry)
            self.assertNotIn("prev_rendered_content", edit_history_entry)
            self.assertNotIn("content_html_diff", edit_history_entry)

        self.assert_length(message_edit_history_moves_only, 5)
        self.assertEqual(message_edit_history_moves_only[0]["content"], "content 1")
        self.assertEqual(message_edit_history_moves_only[0]["topic"], "topic 1")

        self.assertEqual(message_edit_history_moves_only[1]["content"], "content 2")
        self.assertEqual(message_edit_history_moves_only[1]["topic"], "topic 2")
        self.assertEqual(message_edit_history_moves_only[1]["prev_topic"], "topic 1")

        self.assertEqual(message_edit_history_moves_only[2]["content"], "content 2")
        self.assertEqual(message_edit_history_moves_only[2]["topic"], "topic 2")
        self.assertEqual(message_edit_history_moves_only[2]["stream"], stream_2.id)
        self.assertEqual(message_edit_history_moves_only[2]["prev_stream"], stream_1.id)

        self.assertEqual(message_edit_history_moves_only[3]["content"], "content 3")
        self.assertEqual(message_edit_history_moves_only[3]["topic"], "topic 3")
        self.assertEqual(message_edit_history_moves_only[3]["prev_topic"], "topic 2")

        self.assertEqual(message_edit_history_moves_only[4]["content"], "content 3")
        self.assertEqual(message_edit_history_moves_only[4]["topic"], "topic 4")
        self.assertEqual(message_edit_history_moves_only[4]["prev_topic"], "topic 3")
        self.assertEqual(message_edit_history_moves_only[4]["stream"], stream_3.id)
        self.assertEqual(message_edit_history_moves_only[4]["prev_stream"], stream_2.id)

        do_set_realm_property(
            user.realm,
            "message_edit_history_visibility_policy",
            MessageEditHistoryVisibilityPolicyEnum.all,
            acting_user=None,
        )
        result_message_edit_history_all = self.client_get(f"/json/messages/{msg_id}/history")
        json_response = orjson.loads(result_message_edit_history_all.content)
        message_edit_history_all = json_response["message_history"]

        self.assert_length(message_edit_history_all, 6)
        self.assertEqual(message_edit_history_all[0]["content"], "content 1")
        self.assertEqual(message_edit_history_all[0]["topic"], "topic 1")

        self.assertEqual(message_edit_history_all[1]["content"], "content 2")
        self.assertEqual(message_edit_history_all[1]["prev_content"], "content 1")
        self.assertEqual(message_edit_history_all[1]["topic"], "topic 1")

        self.assertEqual(message_edit_history_all[2]["content"], "content 2")
        self.assertEqual(message_edit_history_all[2]["topic"], "topic 2")
        self.assertEqual(message_edit_history_all[2]["prev_topic"], "topic 1")

        self.assertEqual(message_edit_history_all[3]["content"], "content 2")
        self.assertEqual(message_edit_history_all[3]["topic"], "topic 2")
        self.assertEqual(message_edit_history_all[3]["stream"], stream_2.id)
        self.assertEqual(message_edit_history_all[3]["prev_stream"], stream_1.id)

        self.assertEqual(message_edit_history_all[4]["content"], "content 3")
        self.assertEqual(message_edit_history_all[4]["prev_content"], "content 2")
        self.assertEqual(message_edit_history_all[4]["topic"], "topic 3")
        self.assertEqual(message_edit_history_all[4]["prev_topic"], "topic 2")

        self.assertEqual(message_edit_history_all[5]["content"], "content 3")
        self.assertEqual(message_edit_history_all[5]["topic"], "topic 4")
        self.assertEqual(message_edit_history_all[5]["prev_topic"], "topic 3")
        self.assertEqual(message_edit_history_all[5]["stream"], stream_3.id)
        self.assertEqual(message_edit_history_all[5]["prev_stream"], stream_2.id)

    def test_edit_message_content_limit(self) -> None:
        def set_message_editing_params(
            allow_message_editing: bool,
            message_content_edit_limit_seconds: int | str,
            can_move_messages_between_topics_group: NamedUserGroup,
        ) -> None:
            result = self.client_patch(
                "/json/realm",
                {
                    "allow_message_editing": orjson.dumps(allow_message_editing).decode(),
                    "message_content_edit_limit_seconds": orjson.dumps(
                        message_content_edit_limit_seconds
                    ).decode(),
                    "can_move_messages_between_topics_group": orjson.dumps(
                        {
                            "new": can_move_messages_between_topics_group.id,
                        }
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def do_edit_message_assert_success(
            id_: int, unique_str: str, topic_only: bool = False
        ) -> None:
            new_topic_name = "topic" + unique_str
            new_content = "content" + unique_str
            params_dict = {"topic": new_topic_name}
            if not topic_only:
                params_dict["content"] = new_content
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            self.assert_json_success(result)
            if topic_only:
                self.assertEqual(Message.objects.get(id=id_).topic_name(), new_topic_name)
            else:
                self.check_message(id_, topic_name=new_topic_name, content=new_content)

        def do_edit_message_assert_error(
            id_: int, unique_str: str, error: str, topic_only: bool = False
        ) -> None:
            message = Message.objects.get(id=id_)
            old_topic_name = message.topic_name()
            old_content = message.content
            new_topic_name = "topic" + unique_str
            new_content = "content" + unique_str
            params_dict = {"topic": new_topic_name}
            if not topic_only:
                params_dict["content"] = new_content
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            message = Message.objects.get(id=id_)
            self.assert_json_error(result, error)

            msg = Message.objects.get(id=id_)
            self.assertEqual(msg.topic_name(), old_topic_name)
            self.assertEqual(msg.content, old_content)

        self.login("iago")
        # send a message in the past
        id_ = self.send_stream_message(
            self.example_user("iago"), "Denmark", content="content", topic_name="topic"
        )
        message = Message.objects.get(id=id_)
        message.date_sent -= timedelta(seconds=180)
        message.save()

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=get_realm("zulip"), is_system_group=True
        )

        # test the various possible message editing settings
        # high enough time limit, all edits allowed
        set_message_editing_params(True, 240, administrators_system_group)
        do_edit_message_assert_success(id_, "A")

        # out of time, only topic editing allowed
        set_message_editing_params(True, 120, administrators_system_group)
        do_edit_message_assert_success(id_, "B", True)
        do_edit_message_assert_error(id_, "C", "The time limit for editing this message has passed")

        # infinite time, all edits allowed
        set_message_editing_params(True, "unlimited", administrators_system_group)
        do_edit_message_assert_success(id_, "D")

        # without allow_message_editing, editing content is not allowed but
        # editing topic is allowed if topic-edit time limit has not passed
        # irrespective of content-edit time limit.
        set_message_editing_params(False, 240, administrators_system_group)
        do_edit_message_assert_success(id_, "B", True)

        set_message_editing_params(False, 240, administrators_system_group)
        do_edit_message_assert_success(id_, "E", True)
        set_message_editing_params(False, 120, administrators_system_group)
        do_edit_message_assert_success(id_, "F", True)
        set_message_editing_params(False, "unlimited", administrators_system_group)
        do_edit_message_assert_success(id_, "G", True)

    def test_edit_message_in_archived_stream(self) -> None:
        user = self.example_user("hamlet")
        self.login("hamlet")
        stream_name = "archived stream"
        archived_stream = self.make_stream(stream_name)
        self.subscribe(user, stream_name)
        msg_id = self.send_stream_message(
            user, "archived stream", topic_name="editing", content="before edit"
        )
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "content after edit",
            },
        )
        self.assert_json_success(result)

        do_deactivate_stream(archived_stream, acting_user=None)

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "editing second time",
            },
        )
        self.assert_json_error(result, "Invalid message(s)")

    def test_can_move_messages_between_topics_group(self) -> None:
        def set_message_editing_params(
            allow_message_editing: bool,
            message_content_edit_limit_seconds: int | str,
            can_move_messages_between_topics_group: NamedUserGroup,
        ) -> None:
            self.login("iago")
            result = self.client_patch(
                "/json/realm",
                {
                    "allow_message_editing": orjson.dumps(allow_message_editing).decode(),
                    "message_content_edit_limit_seconds": orjson.dumps(
                        message_content_edit_limit_seconds
                    ).decode(),
                    "can_move_messages_between_topics_group": orjson.dumps(
                        {
                            "new": can_move_messages_between_topics_group.id,
                        }
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def do_edit_message_assert_success(id_: int, unique_str: str, acting_user: str) -> None:
            self.login(acting_user)
            new_topic_name = "topic" + unique_str
            params_dict = {"topic": new_topic_name}
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            self.assert_json_success(result)
            self.assertEqual(Message.objects.get(id=id_).topic_name(), new_topic_name)

        def do_edit_message_assert_error(
            id_: int, unique_str: str, error: str, acting_user: str
        ) -> None:
            self.login(acting_user)
            message = Message.objects.get(id=id_)
            old_topic_name = message.topic_name()
            old_content = message.content
            new_topic_name = "topic" + unique_str
            params_dict = {"topic": new_topic_name}
            result = self.client_patch(f"/json/messages/{id_}", params_dict)
            message = Message.objects.get(id=id_)
            self.assert_json_error(result, error)
            msg = Message.objects.get(id=id_)
            self.assertEqual(msg.topic_name(), old_topic_name)
            self.assertEqual(msg.content, old_content)

        # send a message in the past
        id_ = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", content="content", topic_name="topic"
        )
        message = Message.objects.get(id=id_)
        message.date_sent -= timedelta(seconds=180)
        message.save()

        # Guest user must be subscribed to the stream to access the message.
        polonius = self.example_user("polonius")
        realm = polonius.realm
        self.subscribe(polonius, "Denmark")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        full_members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )
        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        # any user can edit the topic of a message
        set_message_editing_params(True, "unlimited", everyone_system_group)
        do_edit_message_assert_success(id_, "A", "polonius")

        # only members can edit topic of a message
        set_message_editing_params(True, "unlimited", members_system_group)
        do_edit_message_assert_error(
            id_, "B", "You don't have permission to edit this message", "polonius"
        )
        do_edit_message_assert_success(id_, "B", "cordelia")

        # only full members can edit topic of a message
        set_message_editing_params(True, "unlimited", full_members_system_group)

        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        cordelia.date_joined = timezone_now() - timedelta(days=9)
        cordelia.save()
        hamlet.date_joined = timezone_now() - timedelta(days=9)
        hamlet.save()

        do_set_realm_property(cordelia.realm, "waiting_period_threshold", 10, acting_user=None)
        do_edit_message_assert_error(
            id_, "C", "You don't have permission to edit this message", "cordelia"
        )
        # User who sent the message but is not a full member cannot edit
        # the topic
        do_edit_message_assert_error(
            id_, "C", "You don't have permission to edit this message", "hamlet"
        )

        do_set_realm_property(cordelia.realm, "waiting_period_threshold", 8, acting_user=None)
        do_edit_message_assert_success(id_, "C", "cordelia")
        do_edit_message_assert_success(id_, "CD", "hamlet")

        # only moderators can edit topic of a message
        set_message_editing_params(True, "unlimited", moderators_system_group)
        do_edit_message_assert_error(
            id_, "D", "You don't have permission to edit this message", "cordelia"
        )
        # even user who sent the message but is not a moderator cannot edit the topic.
        do_edit_message_assert_error(
            id_, "D", "You don't have permission to edit this message", "hamlet"
        )
        do_edit_message_assert_success(id_, "D", "shiva")

        # only admins can edit the topics of messages
        set_message_editing_params(True, "unlimited", administrators_system_group)
        do_edit_message_assert_error(
            id_, "E", "You don't have permission to edit this message", "shiva"
        )
        do_edit_message_assert_success(id_, "E", "iago")

        set_message_editing_params(True, "unlimited", nobody_system_group)
        # owners and admins are allowed to edit the topics via channel-level
        # `can_move_messages_within_channel_group` permission
        do_edit_message_assert_success(id_, "H", "desdemona")
        do_edit_message_assert_success(id_, "I", "iago")
        do_edit_message_assert_error(
            id_, "E", "You don't have permission to edit this message", "shiva"
        )

        # users can edit topics even if allow_message_editing is False
        set_message_editing_params(False, "unlimited", everyone_system_group)
        do_edit_message_assert_success(id_, "D", "cordelia")

        # non-admin users cannot edit topics sent > 1 week ago including
        # sender of the message.
        message.date_sent -= timedelta(seconds=604900)
        message.save()
        set_message_editing_params(True, "unlimited", everyone_system_group)
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

        # Test for checking setting for non-system user group.
        user_group = check_add_user_group(
            realm, "new_group", [polonius, cordelia], acting_user=cordelia
        )
        set_message_editing_params(True, "unlimited", user_group)
        # Polonius and Cordelia are in the allowed user group, so can move messages.
        do_edit_message_assert_success(id_, "I", "polonius")
        do_edit_message_assert_success(id_, "J", "cordelia")
        # Hamlet is not in the allowed user group, so cannot move messages.
        do_edit_message_assert_error(
            id_, "K", "You don't have permission to edit this message", "hamlet"
        )

        # Test for checking the setting for anonymous user group.
        anonymous_user_group = self.create_or_update_anonymous_group_for_setting(
            [cordelia],
            [administrators_system_group],
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_topics_group",
            anonymous_user_group,
            acting_user=None,
        )
        # Cordelia is the direct member of the anonymous user group, so can move messages.
        do_edit_message_assert_success(id_, "K", "cordelia")
        # Iago is in the `administrators_system_group` subgroup, so can move messages.
        do_edit_message_assert_success(id_, "L", "iago")
        # Shiva is not in the anonymous user group, so cannot move messages.
        do_edit_message_assert_error(
            id_, "M", "You don't have permission to edit this message", "shiva"
        )

    @mock.patch("zerver.actions.message_edit.send_event_on_commit")
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
            topic_name="test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        message_id = self.send_stream_message(hamlet, stream_name, "Hello everyone")

        users_to_be_notified = sorted(
            [
                {
                    "id": hamlet.id,
                    "flags": ["read", "topic_wildcard_mentioned"],
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

    @mock.patch("zerver.actions.message_edit.send_event_on_commit")
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
            topic_name="test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        message_id = self.send_stream_message(hamlet, stream_name, "Hello everyone")

        users_to_be_notified = sorted(
            [
                {
                    "id": hamlet.id,
                    "flags": ["read", "stream_wildcard_mentioned"],
                },
                {
                    "id": cordelia.id,
                    "flags": ["stream_wildcard_mentioned"],
                },
            ],
            key=itemgetter("id"),
        )
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

    @mock.patch("zerver.actions.message_edit.send_event_on_commit")
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
                    "flags": ["read", "topic_wildcard_mentioned"],
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

        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_mention_many_users_group",
            moderators_system_group,
            acting_user=None,
        )

        # Less than 'Realm.WILDCARD_MENTION_THRESHOLD' participants
        participants_user_ids = set(range(1, 10))
        with mock.patch(
            "zerver.actions.message_edit.participants_for_topic", return_value=participants_user_ids
        ):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**topic**",
                },
            )
        self.assert_json_success(result)

        # More than 'Realm.WILDCARD_MENTION_THRESHOLD' participants.
        participants_user_ids = set(range(1, 20))
        with mock.patch(
            "zerver.actions.message_edit.participants_for_topic", return_value=participants_user_ids
        ):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**topic**",
                },
            )
        self.assert_json_error(
            result, "You do not have permission to use topic wildcard mentions in this topic."
        )

        # Shiva is moderator
        self.login("shiva")
        message_id = self.send_stream_message(shiva, stream_name, "Hi everyone")
        with mock.patch(
            "zerver.actions.message_edit.participants_for_topic", return_value=participants_user_ids
        ):
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                {
                    "content": "Hello @**topic**",
                },
            )
        self.assert_json_success(result)

    @mock.patch("zerver.actions.message_edit.send_event_on_commit")
    def test_stream_wildcard_mention(self, mock_send_event: mock.MagicMock) -> None:
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
                    "flags": ["read", "stream_wildcard_mentioned"],
                },
                {
                    "id": cordelia.id,
                    "flags": ["stream_wildcard_mentioned"],
                },
            ],
            key=itemgetter("id"),
        )
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

        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_mention_many_users_group",
            moderators_system_group,
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
            result, "You do not have permission to use channel wildcard mentions in this channel."
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

    def test_user_group_mentions_via_subgroup_when_editing(self) -> None:
        user_profile = self.example_user("iago")
        self.login("hamlet")
        self.subscribe(user_profile, "Denmark")
        my_group = check_add_user_group(
            user_profile.realm, "my_group", [user_profile], acting_user=user_profile
        )
        my_group_via_subgroup = check_add_user_group(
            user_profile.realm, "my_group_via_subgroup", [], acting_user=user_profile
        )
        add_subgroups_to_user_group(my_group_via_subgroup, [my_group], acting_user=None)

        self.send_stream_message(
            self.example_user("hamlet"), "Denmark", content="there is no mention"
        )

        message = most_recent_message(user_profile)
        assert (
            UserMessage.objects.get(
                user_profile=user_profile, message=message
            ).flags.mentioned.is_set
            is False
        )

        result = self.client_patch(
            "/json/messages/" + str(message.id),
            {
                "content": "test @*my_group_via_subgroup* mention",
            },
        )
        self.assert_json_success(result)

        assert UserMessage.objects.get(
            user_profile=user_profile, message=message
        ).flags.mentioned.is_set

    def test_user_group_mention_restrictions_while_editing(self) -> None:
        iago = self.example_user("iago")
        shiva = self.example_user("shiva")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.subscribe(iago, "test_stream")
        self.subscribe(shiva, "test_stream")
        self.subscribe(othello, "test_stream")
        self.subscribe(cordelia, "test_stream")

        leadership = check_add_user_group(
            othello.realm, "leadership", [othello], acting_user=othello
        )
        support = check_add_user_group(othello.realm, "support", [othello], acting_user=othello)

        moderators_system_group = NamedUserGroup.objects.get(
            realm=iago.realm, name=SystemGroups.MODERATORS, is_system_group=True
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
            f"You are not allowed to mention user group '{leadership.name}'.",
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

        test = check_add_user_group(shiva.realm, "test", [shiva], acting_user=shiva)
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
            f"You are not allowed to mention user group '{support.name}'.",
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
            f"You are not allowed to mention user group '{support.name}'.",
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
            f"You are not allowed to mention user group '{leadership.name}'.",
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

        # Test all the cases when can_mention_group is not a named user group.
        content = "Test mentioning user group @*leadership*"
        user_group = self.create_or_update_anonymous_group_for_setting(
            [othello], [moderators_system_group]
        )
        leadership.can_mention_group = user_group
        leadership.save()

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
        self.login("iago")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

        msg_id = self.send_stream_message(cordelia, "test_stream", "Test message")
        self.login("cordelia")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_error(
            result, f"You are not allowed to mention user group '{leadership.name}'."
        )

        content = "Test mentioning user group @_*leadership*"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": content,
            },
        )
        self.assert_json_success(result)

    def test_remove_attachment_while_editing(self) -> None:
        # Try editing a message and removing an linked attachment that's
        # uploaded by us. Users should be able to detach their own attachments
        CONST_UPLOAD_PATH_PREFIX = "/user_uploads/"
        user_profile = self.example_user("hamlet")
        file1 = self.create_attachment_helper(user_profile)

        content = f"Init message [attachment1.txt]({file1})"
        self.login("hamlet")

        # Create two messages referencing the same attachment.
        original_msg_id = self.send_stream_message(
            user_profile,
            "Denmark",
            topic_name="editing",
            content=content,
        )

        attachments = Attachment.objects.filter(messages__in=[original_msg_id])
        self.assert_length(attachments, 1)
        path_id_set = CONST_UPLOAD_PATH_PREFIX + attachments[0].path_id
        self.assertEqual(path_id_set, file1)

        msg_id = self.send_stream_message(
            user_profile,
            "Denmark",
            topic_name="editing",
            content=content,
        )

        attachments = Attachment.objects.filter(messages__in=[msg_id])
        self.assert_length(attachments, 1)
        path_id_set = CONST_UPLOAD_PATH_PREFIX + attachments[0].path_id
        self.assertEqual(path_id_set, file1)

        # Try editing first message and removing one reference to the attachment.
        result = self.client_patch(
            f"/json/messages/{original_msg_id}",
            {
                "content": "Try editing a message with an attachment",
            },
        )
        result_content = orjson.loads(result.content)
        self.assertEqual(result_content["result"], "success")
        self.assert_length(result_content["detached_uploads"], 0)

        # Try editing second message, the only reference to the attachment now
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "Try editing a message with an attachment",
            },
        )
        result_content = orjson.loads(result.content)
        self.assertEqual(result_content["result"], "success")
        self.assert_length(result_content["detached_uploads"], 1)
        actual_path_id_set = (
            CONST_UPLOAD_PATH_PREFIX + result_content["detached_uploads"][0]["path_id"]
        )

        self.assertEqual(actual_path_id_set, file1)

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "Try editing a message with no attachments",
            },
        )
        result_content = orjson.loads(result.content)
        self.assertEqual(result_content["result"], "success")
        self.assert_length(result_content["detached_uploads"], 0)

    def test_remove_another_user_attachment_while_editing(self) -> None:
        # Try editing a message and removing an linked attachment that's
        # uploaded by another user. Users should not be able to detach another
        # user's attachments.

        user_profile = self.example_user("hamlet")
        file1 = self.create_attachment_helper(user_profile)

        content = f"Init message [attachment1.txt]({file1})"

        # Send a message with attachment using another user profile.
        msg_id = self.send_stream_message(
            user_profile,
            "Denmark",
            topic_name="editing",
            content=content,
        )
        self.check_message(msg_id, topic_name="editing", content=content)
        attachments = Attachment.objects.filter(messages__in=[msg_id])
        self.assert_length(attachments, 1)

        # Send a message referencing to the attachment uploaded by another user.
        self.login("iago")
        msg_id = self.send_stream_message(
            self.example_user("iago"),
            "Denmark",
            topic_name="editing",
            content=content,
        )
        self.check_message(msg_id, topic_name="editing", content=content)
        attachments = Attachment.objects.filter(messages__in=[msg_id])
        self.assert_length(attachments, 1)

        # Try editing the message and removing the reference to the attachment.
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "Try editing a message with an attachment uploaded by another user",
            },
        )
        result_content = orjson.loads(result.content)
        self.assertEqual(result_content["result"], "success")
        self.assert_length(result_content["detached_uploads"], 0)

    def test_remove_another_user_deleted_attachment_while_editing(self) -> None:
        # Try editing a message and removing an linked attachment that's been
        # uploaded and deleted by the original user. Users should not be able
        # to detach another user's attachments.

        user_profile = self.example_user("hamlet")
        file1 = self.create_attachment_helper(user_profile)

        content = f"Init message [attachment1.txt]({file1})"

        # Send messages with the attachment on both users
        original_msg_id = self.send_stream_message(
            user_profile,
            "Denmark",
            topic_name="editing",
            content=content,
        )
        self.check_message(original_msg_id, topic_name="editing", content=content)
        attachments = Attachment.objects.filter(messages__in=[original_msg_id])
        self.assert_length(attachments, 1)

        msg_id = self.send_stream_message(
            self.example_user("iago"),
            "Denmark",
            topic_name="editing",
            content=content,
        )
        self.check_message(msg_id, topic_name="editing", content=content)
        attachments = Attachment.objects.filter(messages__in=[msg_id])
        self.assert_length(attachments, 1)

        # Delete the message reference from the attachment uploader
        self.login("hamlet")
        result = self.client_delete(f"/json/messages/{original_msg_id}")
        result_content = orjson.loads(result.content)
        self.assertEqual(result_content["result"], "success")

        # Try editing the message and removing the reference of the now deleted attachment.
        self.login("iago")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "Try editing a message with an attachment uploaded by another user",
            },
        )
        result_content = orjson.loads(result.content)
        self.assertEqual(result_content["result"], "success")
        self.assert_length(result_content["detached_uploads"], 0)

    def test_edit_message_race_condition(self) -> None:
        # If two users try to edit the same message at the same time,
        # one of them should get an error message, as the `prev_content`
        # parameter passed to the PATCH call would be outdated and not
        # match.

        # If `prev_content` does not match the expected value, this means
        # the edit request is stale and should be rejected. We simulate
        # that here.
        self.login("hamlet")
        msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="editing",
            content="Init message",
        )
        init_msg = utils.sha256_hash("Init message")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "First user edit",
                "prev_content_sha256": init_msg,
            },
        )
        self.assert_json_success(result)
        self.check_message(msg_id, topic_name="editing", content="First user edit")

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "content": "Second user edit",
                "prev_content_sha256": init_msg,
            },
        )
        self.assert_json_error(
            result,
            "'prev_content_sha256' value does not match the expected value.",
        )
        self.check_message(msg_id, topic_name="editing", content="First user edit")

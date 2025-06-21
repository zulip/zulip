from datetime import timedelta
from unittest import mock

import orjson
from django.utils.timezone import now as timezone_now

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_set_realm_property,
)
from zerver.actions.streams import do_change_stream_group_based_setting, do_change_stream_permission
from zerver.actions.user_groups import check_add_user_group
from zerver.lib.message import has_message_access
from zerver.lib.streams import (
    can_access_stream_metadata_user_ids,
    update_stream_active_status_for_realm,
)
from zerver.lib.test_classes import ZulipTestCase, get_topic_messages
from zerver.lib.test_helpers import queries_captured
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX
from zerver.lib.types import UserGroupMembersData
from zerver.lib.url_encoding import near_stream_message_url
from zerver.lib.user_groups import UserGroupMembershipDetails
from zerver.models import Message, NamedUserGroup, Stream, UserMessage, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.tornado.django_api import send_event_on_commit


class MessageMoveStreamTest(ZulipTestCase):
    def assert_has_usermessage(self, user_profile_id: int, message_id: int) -> None:
        self.assertEqual(
            UserMessage.objects.filter(
                user_profile_id=user_profile_id, message_id=message_id
            ).exists(),
            True,
        )

    def assert_lacks_usermessage(self, user_profile_id: int, message_id: int) -> None:
        self.assertEqual(
            UserMessage.objects.filter(
                user_profile_id=user_profile_id, message_id=message_id
            ).exists(),
            False,
        )

    def assert_move_message(
        self,
        user: str,
        orig_stream: Stream,
        stream_id: int | None = None,
        topic_name: str | None = None,
        expected_error: str | None = None,
    ) -> None:
        user_profile = self.example_user(user)
        self.subscribe(user_profile, orig_stream.name)
        message_id = self.send_stream_message(user_profile, orig_stream.name)

        params_dict: dict[str, str | int] = {}
        if stream_id is not None:
            params_dict["stream_id"] = stream_id
        if topic_name is not None:
            params_dict["topic"] = topic_name

        result = self.api_patch(
            user_profile,
            "/api/v1/messages/" + str(message_id),
            params_dict,
        )
        if expected_error is not None:
            self.assert_json_error(result, expected_error)
        else:
            self.assert_json_success(result)

    def prepare_move_topics(
        self,
        user_email: str,
        old_stream: str,
        new_stream: str,
        topic_name: str,
        language: str | None = None,
    ) -> tuple[UserProfile, Stream, Stream, int, int]:
        user_profile = self.example_user(user_email)
        if language is not None:
            user_profile.default_language = language
            user_profile.save(update_fields=["default_language"])

        self.login(user_email)
        try:
            stream = get_stream(old_stream, user_profile.realm)
            messages = get_topic_messages(user_profile, stream, "test")
            do_delete_messages(user_profile.realm, messages, acting_user=None)
        except Stream.DoesNotExist:
            stream = self.make_stream(old_stream)
        try:
            stream_to = get_stream(new_stream, user_profile.realm)
            messages = get_topic_messages(user_profile, stream_to, "test")
            do_delete_messages(user_profile.realm, messages, acting_user=None)
        except Stream.DoesNotExist:
            stream_to = self.make_stream(new_stream)
        self.subscribe(user_profile, stream.name)
        self.subscribe(user_profile, stream_to.name)
        msg_id = self.send_stream_message(
            user_profile, stream.name, topic_name=topic_name, content="First"
        )
        msg_id_lt = self.send_stream_message(
            user_profile, stream.name, topic_name=topic_name, content="Second"
        )

        self.send_stream_message(user_profile, stream.name, topic_name=topic_name, content="third")

        return (user_profile, stream, stream_to, msg_id, msg_id_lt)

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

        self.assert_json_error(result, "Direct messages cannot be moved to channels.")

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
        self.assert_json_error(result, "Cannot change message content while changing channel")

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assert_length(messages, 3)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assert_length(messages, 0)

    def test_change_all_propagate_mode_for_moving_old_messages(self) -> None:
        user_profile = self.example_user("hamlet")
        realm = user_profile.realm
        id1 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        id2 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        id3 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        id4 = self.send_stream_message(user_profile, "Denmark", topic_name="topic1")
        self.send_stream_message(user_profile, "Denmark", topic_name="topic1")

        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            members_system_group,
            acting_user=None,
        )

        message = Message.objects.get(id=id1)
        message.date_sent -= timedelta(days=10)
        message.save()

        message = Message.objects.get(id=id2)
        message.date_sent -= timedelta(days=8)
        message.save()

        message = Message.objects.get(id=id3)
        message.date_sent -= timedelta(days=5)
        message.save()

        verona = get_stream("Verona", user_profile.realm)
        denmark = get_stream("Denmark", user_profile.realm)
        old_topic_name = "topic1"
        old_stream = denmark

        def test_moving_all_topic_messages(
            new_topic_name: str | None = None, new_stream: Stream | None = None
        ) -> None:
            self.login("hamlet")
            params_dict: dict[str, str | int] = {
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            }

            if new_topic_name is not None:
                params_dict["topic"] = new_topic_name
            else:
                new_topic_name = old_topic_name

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
            messages = get_topic_messages(user_profile, old_stream, old_topic_name)
            self.assert_length(messages, 5)

            # Check message count in new topic and/or stream.
            messages = get_topic_messages(user_profile, new_stream, new_topic_name)
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
            messages = get_topic_messages(user_profile, old_stream, old_topic_name)
            self.assert_length(messages, 2)

            # Check message count in new topic and/or stream.
            messages = get_topic_messages(user_profile, new_stream, new_topic_name)
            self.assert_length(messages, 3)

            self.login("shiva")
            # Move these messages to the original topic and stream, to test the case
            # when user is moderator.
            result = self.client_patch(
                f"/json/messages/{id4}",
                {
                    "topic": old_topic_name,
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
            messages = get_topic_messages(user_profile, old_stream, old_topic_name)
            self.assert_length(messages, 0)

            # Check message count in new topic and/or stream.
            messages = get_topic_messages(user_profile, new_stream, new_topic_name)
            self.assert_length(messages, 5)

        # Test only topic editing case.
        test_moving_all_topic_messages(new_topic_name="topic edited")

        # Move these messages to the original topic to test the next case.
        self.client_patch(
            f"/json/messages/{id4}",
            {
                "topic": old_topic_name,
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
        test_moving_all_topic_messages(new_topic_name="edited", new_stream=verona)

        # Move these messages to the original stream and topic to test the next case.
        self.client_patch(
            f"/json/messages/{id4}",
            {
                "stream_id": denmark.id,
                "topic": old_topic_name,
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
        new_topic_name = "edited"
        result = self.client_patch(
            f"/json/messages/{id4}",
            {
                "topic": new_topic_name,
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "send_notification_to_new_thread": "false",
            },
        )
        self.assert_json_success(result)
        # Check message count in old topic and/or stream.
        messages = get_topic_messages(user_profile, old_stream, old_topic_name)
        self.assert_length(messages, 0)

        # Check message count in new topic and/or stream.
        messages = get_topic_messages(user_profile, new_stream, new_topic_name)
        self.assert_length(messages, 5)

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

        self.assert_json_error(result, "Invalid channel ID")

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

        self.assert_json_error(result, "Invalid channel ID")

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
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        realm = othello.realm

        def check_move_message_according_to_permission(
            username: str, expect_fail: bool = False
        ) -> None:
            (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
                username, "old_stream", "new_stream", "test"
            )
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
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        # Check sending messages when nobody is allowed to move messages.
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            nobody_system_group,
            acting_user=None,
        )
        check_move_message_according_to_permission("shiva", expect_fail=True)
        # Iago can move messages between channels via channel-level
        # `can_move_messages_out_of_channel_group` permission.
        check_move_message_according_to_permission("iago")

        # Check sending messages when only administrators are allowed.
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            administrators_system_group,
            acting_user=None,
        )
        check_move_message_according_to_permission("shiva", expect_fail=True)
        check_move_message_according_to_permission("iago")

        # Check sending messages when only moderators are allowed.
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            moderators_system_group,
            acting_user=None,
        )
        check_move_message_according_to_permission("cordelia", expect_fail=True)
        check_move_message_according_to_permission("shiva")

        # Check sending messages when full members are allowed.
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            full_members_system_group,
            acting_user=None,
        )
        do_set_realm_property(othello.realm, "waiting_period_threshold", 100000, acting_user=None)
        check_move_message_according_to_permission("othello", expect_fail=True)

        do_set_realm_property(realm, "waiting_period_threshold", 0, acting_user=None)
        check_move_message_according_to_permission("cordelia")

        # Check sending messages when members are allowed.
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            members_system_group,
            acting_user=None,
        )
        check_move_message_according_to_permission("polonius", expect_fail=True)
        check_move_message_according_to_permission("cordelia")

        # Test for checking setting for non-system user group.
        user_group = check_add_user_group(
            realm, "new_group", [othello, cordelia], acting_user=othello
        )
        do_change_realm_permission_group_setting(
            realm, "can_move_messages_between_channels_group", user_group, acting_user=None
        )

        # Othello and Cordelia are in the allowed user group, so can move messages.
        check_move_message_according_to_permission("othello")
        check_move_message_according_to_permission("cordelia")

        # Shiva is not in the allowed user group, so cannot move messages.
        check_move_message_according_to_permission("shiva", expect_fail=True)

        # Test for checking the setting for anonymous user group.
        anonymous_user_group = self.create_or_update_anonymous_group_for_setting(
            [othello],
            [administrators_system_group],
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            anonymous_user_group,
            acting_user=None,
        )

        # Othello is the direct member of the anonymous user group, so can move messages.
        check_move_message_according_to_permission("othello")
        # Iago is in the `administrators_system_group` subgroup, so can move messages.
        check_move_message_according_to_permission("iago")

        # Shiva is not in the anonymous user group, so cannot move messages.
        check_move_message_according_to_permission("shiva", expect_fail=True)

    def test_move_message_to_stream_time_limit(self) -> None:
        shiva = self.example_user("shiva")
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")

        realm = cordelia.realm

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

        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            members_system_group,
            acting_user=None,
        )

        def check_move_message_to_stream(
            user: UserProfile,
            old_stream: Stream,
            new_stream: Stream,
            *,
            expect_error_message: str | None = None,
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
        message.date_sent -= timedelta(seconds=604900)
        message.save()
        check_move_message_to_stream(
            cordelia,
            test_stream_1,
            test_stream_2,
            expect_error_message="The time limit for editing this message's channel has passed",
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

    def test_move_message_to_stream_based_on_can_send_message_group(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream", "new_stream", "test"
        )
        realm = user_profile.realm

        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            members_system_group,
            acting_user=None,
        )

        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        polonius = self.example_user("polonius")

        def check_move_message_to_stream(
            user: UserProfile,
            expect_fail: bool = False,
            error_msg: str = "You do not have permission to post in this channel.",
        ) -> None:
            result = self.api_patch(
                user,
                "/api/v1/messages/" + str(msg_id),
                {
                    "stream_id": new_stream.id,
                    "propagate_mode": "change_all",
                },
            )

            if expect_fail:
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

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            new_stream, "can_send_message_group", nobody_group, acting_user=desdemona
        )

        check_move_message_to_stream(desdemona, expect_fail=True)
        check_move_message_to_stream(iago, expect_fail=True)

        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            new_stream, "can_send_message_group", owners_group, acting_user=desdemona
        )

        check_move_message_to_stream(iago, expect_fail=True)
        check_move_message_to_stream(desdemona)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream", "new_stream", "test"
        )

        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)
        do_change_stream_group_based_setting(
            new_stream, "can_send_message_group", hamletcharacters_group, acting_user=desdemona
        )

        check_move_message_to_stream(desdemona, expect_fail=True)
        check_move_message_to_stream(iago, expect_fail=True)
        check_move_message_to_stream(hamlet)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream", "new_stream", "test"
        )

        setting_group_member_dict = UserGroupMembersData(
            direct_members=[othello.id], direct_subgroups=[owners_group.id]
        )
        do_change_stream_group_based_setting(
            new_stream, "can_send_message_group", setting_group_member_dict, acting_user=desdemona
        )

        check_move_message_to_stream(iago, expect_fail=True)
        check_move_message_to_stream(hamlet, expect_fail=True)
        check_move_message_to_stream(desdemona)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream", "new_stream", "test"
        )
        check_move_message_to_stream(othello)

        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "polonius", "old_stream", "new_stream", "test"
        )
        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            new_stream, "can_send_message_group", everyone_group, acting_user=desdemona
        )
        check_move_message_to_stream(
            polonius, expect_fail=True, error_msg="You don't have permission to move this message"
        )
        check_move_message_to_stream(hamlet)

    def test_can_move_messages_out_of_channel_group(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        realm = hamlet.realm

        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        expected_error = "You don't have permission to move this message"

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_topics_group",
            nobody_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            nobody_system_group,
            acting_user=None,
        )

        stream_1 = get_stream("Denmark", realm)
        stream_2 = get_stream("Verona", realm)

        # Nobody is allowed to move messages.
        self.assert_move_message(
            "hamlet", stream_1, stream_id=stream_2.id, expected_error=expected_error
        )
        # Realm admin can always move messages out of the channel.
        self.assert_move_message("iago", stream_1, stream_id=stream_2.id)

        do_change_stream_group_based_setting(
            stream_1,
            "can_move_messages_out_of_channel_group",
            members_system_group,
            acting_user=iago,
        )
        # Only members are allowed to move messages out of the channel.
        self.assert_move_message("hamlet", stream_1, stream_id=stream_2.id)
        self.assert_move_message("cordelia", stream_1, stream_id=stream_2.id)
        # Guests are not allowed.
        self.assert_move_message(
            "polonius", stream_1, stream_id=stream_2.id, expected_error=expected_error
        )

        # Nobody is allowed to edit the topics when moving messages between the channels.
        self.assert_move_message(
            "hamlet",
            stream_1,
            stream_id=stream_2.id,
            topic_name="new topic",
            expected_error="You don't have permission to edit this message",
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_topics_group",
            members_system_group,
            acting_user=None,
        )
        # Now Hamlet is in `can_move_messages_between_topics_group`, so can edit topics.
        self.assert_move_message("hamlet", stream_1, stream_id=stream_2.id, topic_name="new topic")

        user_group = check_add_user_group(
            realm, "new_group", [hamlet, cordelia], acting_user=hamlet
        )
        do_change_stream_group_based_setting(
            stream_1, "can_move_messages_out_of_channel_group", user_group, acting_user=iago
        )

        # Hamlet and Cordelia are in the `can_move_messages_out_of_channel_group`,
        # so they can move messages out of the channel.
        self.assert_move_message("cordelia", stream_1, stream_id=stream_2.id)
        self.assert_move_message("hamlet", stream_1, stream_id=stream_2.id)
        # But Shiva is not, so he can't.
        self.assert_move_message(
            "shiva", stream_1, stream_id=stream_2.id, expected_error=expected_error
        )

        do_change_stream_group_based_setting(
            stream_1, "can_administer_channel_group", members_system_group, acting_user=iago
        )
        # Channel administrators with content access can always move messages out of
        # the channel even if they are not in `can_move_messages_out_of_channel_group`.
        self.assert_move_message("shiva", stream_1, stream_id=stream_2.id)

    def test_move_message_to_stream_with_topic_editing_not_allowed(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "othello", "old_stream_1", "new_stream_1", "test"
        )
        realm = user_profile.realm

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_topics_group",
            administrators_system_group,
            acting_user=None,
        )

        self.login("cordelia")

        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            members_system_group,
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

        with self.assert_database_query_count(59), self.assert_memcached_count(14):
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

    def test_move_many_messages_to_stream_and_topic(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "first origin stream", "first destination stream", "first topic"
        )

        with queries_captured() as queries:
            result = self.client_patch(
                f"/json/messages/{msg_id}",
                {
                    "propagate_mode": "change_all",
                    "send_notification_to_old_thread": "true",
                    "stream_id": new_stream.id,
                    "topic": "first topic",
                },
            )
            self.assert_json_success(result)

        # Adding more messages should not increase the number of
        # queries
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "second origin stream", "second destination stream", "second topic"
        )
        for i in range(1, 5):
            self.send_stream_message(
                user_profile,
                "second origin stream",
                topic_name="second topic",
                content=f"Extra message {i}",
            )
        with self.assert_database_query_count(len(queries)):
            result = self.client_patch(
                f"/json/messages/{msg_id}",
                {
                    "propagate_mode": "change_all",
                    "send_notification_to_old_thread": "true",
                    "stream_id": new_stream.id,
                    "topic": "second topic",
                },
            )
            self.assert_json_success(result)

    def test_inaccessible_msg_after_stream_change(self) -> None:
        """Simulates the case where message is moved to a stream where user is not a subscribed"""
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        # Iago is set up, above, to be sub'd to both streams
        iago = self.example_user("iago")

        # These are only sub'd to the old (public) stream
        guest_user = self.example_user("polonius")
        non_guest_user = self.example_user("hamlet")
        self.subscribe(guest_user, old_stream.name)
        self.subscribe(non_guest_user, old_stream.name)

        msg_id_to_test_acesss = self.send_stream_message(
            user_profile, old_stream.name, topic_name="test", content="fourth"
        )

        def check_user_access(
            user: UserProfile,
            *,
            has_user_message: bool,
            has_access: bool,
            stream: Stream | None = None,
            is_subscribed: bool | None = None,
        ) -> None:
            self.assertEqual(
                UserMessage.objects.filter(
                    message_id=msg_id_to_test_acesss, user_profile_id=user.id
                ).exists(),
                has_user_message,
            )
            self.assertEqual(
                has_message_access(
                    user,
                    Message.objects.get(id=msg_id_to_test_acesss),
                    has_user_message=lambda: has_user_message,
                    stream=stream,
                    is_subscribed=is_subscribed,
                    user_group_membership_details=UserGroupMembershipDetails(
                        user_recursive_group_ids=None
                    ),
                    is_modifying_message=False,
                ),
                has_access,
            )

        check_user_access(iago, has_user_message=True, has_access=True)
        check_user_access(guest_user, has_user_message=True, has_access=True, stream=old_stream)
        check_user_access(non_guest_user, has_user_message=True, has_access=True)

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
                "topic": "new topic",
            },
        )
        self.assert_json_success(result)

        check_user_access(iago, has_user_message=True, has_access=True)
        check_user_access(guest_user, has_user_message=False, has_access=False)
        check_user_access(non_guest_user, has_user_message=False, has_access=True)

        # If the guest user were subscribed to the new stream,
        # they'd have access; has_message_access does not validate
        # the is_subscribed parameter.
        check_user_access(
            guest_user,
            has_user_message=False,
            has_access=True,
            is_subscribed=True,
            stream=new_stream,
        )
        check_user_access(guest_user, has_user_message=False, has_access=False, stream=new_stream)
        with self.assertRaises(AssertionError):
            # Raises assertion if you pass an invalid stream.
            check_user_access(
                guest_user, has_user_message=False, has_access=False, stream=old_stream
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

    def test_notify_resolve_topic_and_move_stream(self) -> None:
        (
            user_profile,
            first_stream,
            second_stream,
            msg_id,
            msg_id_later,
        ) = self.prepare_move_topics("shiva", "first stream", "second stream", "test")

        # 'prepare_move_topics' sends 3 messages in the first_stream
        messages = get_topic_messages(user_profile, first_stream, "test")
        self.assert_length(messages, 3)
        realm = messages[0].realm

        # Test resolving a topic (test ->  ✔ test) while changing stream (first_stream -> second_stream)
        new_topic_name = "✔ test"
        new_stream = second_stream
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "topic": new_topic_name,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, new_stream, new_topic_name)
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**{first_stream.name}>test** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

        # Test unresolving a topic (✔ test -> test) while changing stream (second_stream -> first_stream)
        new_topic_name = "test"
        new_stream = first_stream
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "topic": new_topic_name,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, new_stream, new_topic_name)
        self.assert_length(messages, 5)
        self.assertEqual(
            messages[4].content,
            f"This topic was moved here from #**{second_stream.name}>✔ test** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

        # Test resolving a topic (test ->  ✔ test) while changing stream (first_stream -> second_stream) with no moving messages
        # between channels permission.
        new_topic_name = RESOLVED_TOPIC_PREFIX + " test"
        new_stream = second_stream

        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            nobody_system_group,
            acting_user=None,
        )

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "topic": new_topic_name,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(result, "You don't have permission to move this message")

    def parameterized_test_move_message_involving_private_stream(
        self,
        from_invite_only: bool,
        history_public_to_subscribers: bool,
        user_messages_created: bool,
        to_invite_only: bool = True,
        propagate_mode: str = "change_all",
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

        self.assert_length(get_topic_messages(admin_user, old_stream, "test"), 2)
        self.assert_length(get_topic_messages(admin_user, new_stream, "test"), 0)

        self.assert_has_usermessage(user_losing_access.id, msg_id)
        self.assert_lacks_usermessage(user_gaining_access.id, msg_id)

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": propagate_mode,
            },
        )
        self.assert_json_success(result)

        # We gain one more message than we moved because of a notification-bot message.
        if propagate_mode == "change_one":
            self.assert_length(get_topic_messages(admin_user, old_stream, "test"), 1)
            self.assert_length(get_topic_messages(admin_user, new_stream, "test"), 2)
        else:
            self.assert_length(get_topic_messages(admin_user, old_stream, "test"), 0)
            self.assert_length(get_topic_messages(admin_user, new_stream, "test"), 3)

        self.assert_lacks_usermessage(user_losing_access.id, msg_id)
        # When the history is shared, UserMessage is not created for the user but the user
        # can see the message.
        if user_messages_created:
            self.assert_has_usermessage(user_gaining_access.id, msg_id)
        else:
            self.assert_lacks_usermessage(user_gaining_access.id, msg_id)

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

    def test_move_one_message_from_public_to_private_stream_not_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=False,
            history_public_to_subscribers=False,
            user_messages_created=True,
            propagate_mode="change_one",
        )

    def test_move_one_message_from_public_to_private_stream_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=False,
            history_public_to_subscribers=True,
            user_messages_created=False,
            propagate_mode="change_one",
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

    def test_move_message_from_private_to_private_with_old_member(self) -> None:
        admin_user = self.example_user("iago")
        user_losing_access = self.example_user("cordelia")

        self.login("iago")
        old_stream = self.make_stream("test move stream", invite_only=True)
        new_stream = self.make_stream("new stream", invite_only=True)

        self.subscribe(admin_user, old_stream.name)
        self.subscribe(user_losing_access, old_stream.name)

        self.subscribe(admin_user, new_stream.name)

        msg_id = self.send_stream_message(
            admin_user, old_stream.name, topic_name="test", content="First"
        )

        self.assert_has_usermessage(user_losing_access.id, msg_id)
        self.assertEqual(
            has_message_access(
                user_losing_access,
                Message.objects.get(id=msg_id),
                has_user_message=lambda: True,
                stream=old_stream,
                is_subscribed=True,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            True,
        )

        # Unsubscribe the user_losing_access; they will keep their
        # UserMessage row, but lose access to the message; their
        # Subscription row remains, but is inactive.
        self.unsubscribe(user_losing_access, old_stream.name)
        self.assert_has_usermessage(user_losing_access.id, msg_id)
        self.assertEqual(
            has_message_access(
                user_losing_access,
                Message.objects.get(id=msg_id),
                has_user_message=lambda: True,
                stream=old_stream,
                is_subscribed=False,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            False,
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        # They should no longer have a UserMessage row, so we preserve
        # the invariant that users without subscriptions never have
        # UserMessage rows -- and definitely do not have access.
        self.assert_lacks_usermessage(user_losing_access.id, msg_id)
        self.assertEqual(
            has_message_access(
                user_losing_access,
                Message.objects.get(id=msg_id),
                has_user_message=lambda: True,
                stream=new_stream,
                is_subscribed=False,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            False,
        )

    def test_move_message_to_private_hidden_history_with_old_member(self) -> None:
        admin_user = self.example_user("iago")
        user = self.example_user("cordelia")

        self.login("iago")
        old_stream = self.make_stream("test move stream", invite_only=True)
        new_stream = self.make_stream(
            "new stream", invite_only=True, history_public_to_subscribers=False
        )

        self.subscribe(admin_user, old_stream.name)
        self.subscribe(user, old_stream.name)

        self.subscribe(admin_user, new_stream.name)
        self.subscribe(user, new_stream.name)

        # Cordelia is subscribed to both streams when this first
        # message is sent
        first_msg_id = self.send_stream_message(
            admin_user, old_stream.name, topic_name="test", content="First"
        )

        self.assert_has_usermessage(user.id, first_msg_id)
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=first_msg_id),
                has_user_message=lambda: True,
                stream=old_stream,
                is_subscribed=True,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            True,
        )

        # Unsubscribe the user; they will keep their UserMessage row,
        # but lose access to the message; their Subscription row
        # remains, but is inactive.
        self.unsubscribe(user, old_stream.name)
        self.assert_has_usermessage(user.id, first_msg_id)
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=first_msg_id),
                has_user_message=lambda: True,
                stream=old_stream,
                is_subscribed=False,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            False,
        )

        # The user is no longer subscribed, so does not have a
        # UserMessage row, or access
        second_msg_id = self.send_stream_message(
            admin_user, old_stream.name, topic_name="test", content="Second"
        )
        self.assert_lacks_usermessage(user.id, second_msg_id)
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=second_msg_id),
                has_user_message=lambda: False,
                stream=old_stream,
                is_subscribed=False,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            False,
        )

        # Move both messages
        result = self.client_patch(
            f"/json/messages/{first_msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        # They should have a UserMessage row for both messages, and
        # now have access to both -- being in the stream when the
        # message is moved in is always sufficient to grant access.
        self.assert_has_usermessage(user.id, first_msg_id)
        self.assert_has_usermessage(user.id, second_msg_id)
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=first_msg_id),
                has_user_message=lambda: True,
                stream=new_stream,
                is_subscribed=True,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            True,
        )
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=second_msg_id),
                has_user_message=lambda: True,
                stream=new_stream,
                is_subscribed=True,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            True,
        )

    def test_move_message_to_private_hidden_history_with_new_member(self) -> None:
        admin_user = self.example_user("iago")
        user = self.example_user("cordelia")

        self.login("iago")
        old_stream = self.make_stream(
            "test move stream", invite_only=True, history_public_to_subscribers=False
        )
        new_stream = self.make_stream(
            "new stream", invite_only=True, history_public_to_subscribers=False
        )

        self.subscribe(admin_user, old_stream.name)
        self.subscribe(admin_user, new_stream.name)

        # Cordelia is subscribed to neither stream when this message is sent
        msg_id = self.send_stream_message(
            admin_user, old_stream.name, topic_name="test", content="First"
        )
        self.assert_lacks_usermessage(user.id, msg_id)
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=msg_id),
                has_user_message=lambda: False,
                stream=old_stream,
                is_subscribed=False,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            False,
        )

        # Subscribe to both streams.  Because the streams do not have
        # shared history, Cordelia does not get a UserMessage row, or
        # access.
        self.subscribe(user, old_stream.name)
        self.subscribe(user, new_stream.name)
        self.assert_lacks_usermessage(user.id, msg_id)
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=msg_id),
                has_user_message=lambda: False,
                stream=old_stream,
                is_subscribed=False,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            False,
        )

        # Move the message to the other private-history stream
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

        # They should now have a UserMessage row, and now have access
        # -- being in the stream when the message is moved in is
        # always sufficient to grant access.
        self.assert_has_usermessage(user.id, msg_id)
        self.assertEqual(
            has_message_access(
                user,
                Message.objects.get(id=msg_id),
                has_user_message=lambda: True,
                stream=new_stream,
                is_subscribed=True,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_modifying_message=False,
            ),
            True,
        )

    def test_move_message_update_stream_active_status(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        # Delete all messages in new stream and mark it as inactive.
        Message.objects.filter(recipient__type_id=new_stream.id, realm=user_profile.realm).delete()

        with mock.patch("zerver.lib.streams.send_event_on_commit", wraps=send_event_on_commit) as m:
            update_stream_active_status_for_realm(
                user_profile.realm, timezone_now() - timedelta(days=10)
            )
            self.assertEqual(
                m.call_args.args,
                (
                    new_stream.realm,
                    dict(
                        type="stream",
                        op="update",
                        property="is_recently_active",
                        value=False,
                        stream_id=new_stream.id,
                        name=new_stream.name,
                    ),
                    can_access_stream_metadata_user_ids(new_stream),
                ),
            )

        new_stream.refresh_from_db()
        self.assertFalse(new_stream.is_recently_active)

        # Move the message to new stream should make active again.
        result = self.client_patch(
            f"/json/messages/{msg_id_later}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_later",
                "send_notification_to_new_thread": "false",
            },
        )
        self.assert_json_success(result)

        new_stream.refresh_from_db()
        self.assertTrue(new_stream.is_recently_active)

    def test_move_message_update_private_stream_active_status(self) -> None:
        # Goal is to test that we only send the stream status update to subscribers.
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test"
        )

        # Mark stream as private
        do_change_stream_permission(
            new_stream,
            invite_only=True,
            history_public_to_subscribers=False,
            is_web_public=False,
            acting_user=user_profile,
        )
        # Delete all messages in new stream and mark it as inactive.
        Message.objects.filter(recipient__type_id=new_stream.id, realm=user_profile.realm).delete()

        with mock.patch("zerver.lib.streams.send_event_on_commit", wraps=send_event_on_commit) as m:
            update_stream_active_status_for_realm(
                user_profile.realm, timezone_now() - timedelta(days=10)
            )
            self.assertEqual(
                m.call_args.args,
                (
                    new_stream.realm,
                    dict(
                        type="stream",
                        op="update",
                        property="is_recently_active",
                        value=False,
                        stream_id=new_stream.id,
                        name=new_stream.name,
                    ),
                    # Only send the event to users with stream access.
                    {
                        9,  # Realm owner (Desdemona)
                        11,  # Subscriber (iago)
                    },
                ),
            )

        new_stream.refresh_from_db()
        self.assertFalse(new_stream.is_recently_active)

        # Move the message to new stream should make active again.
        result = self.client_patch(
            f"/json/messages/{msg_id_later}",
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_later",
                "send_notification_to_new_thread": "false",
            },
        )
        self.assert_json_success(result)

        new_stream.refresh_from_db()
        self.assertTrue(new_stream.is_recently_active)

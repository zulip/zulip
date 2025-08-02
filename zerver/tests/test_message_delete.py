from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest import mock

import orjson
from django.db import IntegrityError
from django.utils.timezone import now as timezone_now

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.realm_settings import do_change_realm_permission_group_setting
from zerver.actions.streams import do_change_stream_group_based_setting, do_deactivate_stream
from zerver.actions.user_groups import check_add_user_group
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, NamedUserGroup, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class DeleteMessageTest(ZulipTestCase):
    def test_do_delete_messages_with_empty_list(self) -> None:
        realm = get_realm("zulip")
        inital_count = Message.objects.count()
        do_delete_messages(realm, [], acting_user=None)
        final_count = Message.objects.count()
        self.assertEqual(inital_count, final_count)

    def test_do_delete_private_messages_with_acting_user(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        acting_user = self.example_user("iago")
        msg_id = self.send_personal_message(cordelia, hamlet, "Hello!")
        message = Message.objects.get(id=msg_id)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            do_delete_messages(realm, [message], acting_user=acting_user)

        self.assert_length(events, 1)
        event = events[0]["event"]
        self.assertIn("type", event)
        self.assertEqual(event["type"], "delete_message")
        self.assertIn(msg_id, event["message_ids"])
        self.assertIn(acting_user.id, events[0]["users"])

    def test_do_delete_stream_messages_without_acting_user(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")

        stream_name = "Denmark-Test"
        self.make_stream(stream_name)
        self.subscribe(cordelia, stream_name)

        msg_id = self.send_stream_message(cordelia, stream_name, "Hello, Denmark!")
        message = Message.objects.get(id=msg_id)

        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, [message], acting_user=None)

        self.assert_length(events, 2)
        self.assertIn("type", events[0]["event"])
        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertIn(msg_id, events[1]["event"]["message_ids"])

    def test_do_delete_messages_grouping_logic(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        self.make_stream("stream1")
        self.make_stream("stream2")
        self.subscribe(cordelia, "stream1")
        self.subscribe(hamlet, "stream1")
        self.subscribe(cordelia, "stream2")
        self.subscribe(hamlet, "stream2")

        msg_id_1 = self.send_stream_message(
            cordelia, "stream1", topic_name="topic1", content="test1"
        )
        msg_id_2 = self.send_stream_message(hamlet, "stream1", topic_name="topic1", content="test2")
        msg_id_3 = self.send_stream_message(
            cordelia, "stream1", topic_name="topic2", content="test3"
        )
        msg_id_4 = self.send_stream_message(hamlet, "stream2", topic_name="topic3", content="test4")
        dm_id_1 = self.send_personal_message(cordelia, hamlet, "test5")
        dm_id_2 = self.send_personal_message(hamlet, iago, "test6")

        messages = Message.objects.filter(
            id__in=[msg_id_1, msg_id_2, msg_id_3, msg_id_4, dm_id_1, dm_id_2]
        )

        stream1 = get_stream("stream1", realm)
        stream2 = get_stream("stream2", realm)

        with self.capture_send_event_calls(expected_num_events=8) as events:
            do_delete_messages(realm, messages, acting_user=None)

        expected_events: list[dict[str, Any]] = [
            {
                "type": "delete_message",
                "message_ids": [dm_id_1],
                "message_type": "private",
            },
            {
                "type": "delete_message",
                "message_ids": [dm_id_2],
                "message_type": "private",
            },
            {
                "type": "stream",
                "op": "update",
                "property": "first_message_id",
                "value": msg_id_3,
                "stream_id": stream1.id,
                "name": "stream1",
            },
            {
                "type": "delete_message",
                "message_ids": [msg_id_1, msg_id_2],
                "stream_id": stream1.id,
                "topic": "topic1",
                "message_type": "stream",
            },
            {
                "type": "stream",
                "op": "update",
                "property": "first_message_id",
                "value": None,
                "stream_id": stream1.id,
                "name": "stream1",
            },
            {
                "type": "delete_message",
                "message_ids": [msg_id_3],
                "stream_id": stream1.id,
                "topic": "topic2",
                "message_type": "stream",
            },
            {
                "type": "stream",
                "op": "update",
                "property": "first_message_id",
                "value": None,
                "stream_id": stream2.id,
                "name": "stream2",
            },
            {
                "type": "delete_message",
                "message_ids": [msg_id_4],
                "stream_id": stream2.id,
                "topic": "topic3",
                "message_type": "stream",
            },
        ]

        actual_events = [event["event"] for event in events]

        self.assert_length(actual_events, len(expected_events))

        for actual, expected in zip(actual_events, expected_events, strict=True):
            for key, value in expected.items():
                if key == "message_ids":
                    self.assertEqual(set(actual[key]), set(value))
                else:
                    self.assertEqual(actual[key], value)

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
            can_delete_any_message_group: NamedUserGroup,
            can_delete_own_message_group: NamedUserGroup,
            message_content_delete_limit_seconds: int | str,
        ) -> None:
            self.login("iago")
            result = self.client_patch(
                "/json/realm",
                {
                    "can_delete_any_message_group": orjson.dumps(
                        {"new": can_delete_any_message_group.id}
                    ).decode(),
                    "can_delete_own_message_group": orjson.dumps(
                        {"new": can_delete_own_message_group.id}
                    ).decode(),
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

        def test_delete_message_by_moderator(msg_id: int) -> "TestHttpResponse":
            self.login("shiva")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_sender(msg_id: int) -> "TestHttpResponse":
            self.login("hamlet")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_other_user(msg_id: int) -> "TestHttpResponse":
            self.login("cordelia")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        realm = get_realm("zulip")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
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

        # Test if message deleting is not allowed(default).
        set_message_deleting_params(
            administrators_system_group, administrators_system_group, "unlimited"
        )
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        msg_id = self.send_stream_message(hamlet, "Denmark")

        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_admin(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if message deleting is allowed.
        # Test if time limit is None(no limit).
        set_message_deleting_params(administrators_system_group, everyone_system_group, "unlimited")
        msg_id = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id)
        message.date_sent -= timedelta(seconds=600)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if time limit is non-zero.
        set_message_deleting_params(administrators_system_group, everyone_system_group, 240)
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_1)
        message.date_sent -= timedelta(seconds=120)
        message.save()

        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_2)
        message.date_sent -= timedelta(seconds=360)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_sender(msg_id=msg_id_1)
        self.assert_json_success(result)
        result = test_delete_message_by_sender(msg_id=msg_id_2)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        # No limit for admin.
        result = test_delete_message_by_admin(msg_id=msg_id_2)
        self.assert_json_success(result)

        # Test multiple delete requests with no latency issues
        msg_id = self.send_stream_message(hamlet, "Denmark")
        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_success(result)
        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Test if message deletion is allowed when every member can delete any message.
        set_message_deleting_params(members_system_group, administrators_system_group, "unlimited")
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        msg_id_3 = self.send_stream_message(hamlet, "Denmark")

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_success(result)

        result = test_delete_message_by_sender(msg_id=msg_id_2)
        self.assert_json_success(result)

        result = test_delete_message_by_admin(msg_id=msg_id_3)
        self.assert_json_success(result)

        # Test if there is no time limit to delete messages for users who can delete
        # any message.
        set_message_deleting_params(moderators_system_group, everyone_system_group, 240)
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_1)
        message.date_sent -= timedelta(seconds=120)
        message.save()

        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_2)
        message.date_sent -= timedelta(seconds=360)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_sender(msg_id=msg_id_1)
        self.assert_json_success(result)

        result = test_delete_message_by_sender(msg_id=msg_id_2)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        result = test_delete_message_by_moderator(msg_id=msg_id_2)
        self.assert_json_success(result)

        # Test handling of 500 error caused by multiple delete requests due to latency.
        # see issue #11219.
        with (
            mock.patch("zerver.views.message_edit.do_delete_messages") as m,
            mock.patch("zerver.views.message_edit.validate_can_delete_message", return_value=None),
            mock.patch("zerver.views.message_edit.access_message", return_value=(None, None)),
        ):
            m.side_effect = IntegrityError()
            result = test_delete_message_by_sender(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")
            m.side_effect = Message.DoesNotExist()
            result = test_delete_message_by_sender(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")

    def test_delete_message_sent_by_bots(self) -> None:
        iago = self.example_user("iago")
        shiva = self.example_user("shiva")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        def set_message_deleting_params(
            can_delete_any_message_group: NamedUserGroup,
            can_delete_own_message_group: NamedUserGroup,
            message_content_delete_limit_seconds: int | str,
        ) -> None:
            result = self.api_patch(
                iago,
                "/api/v1/realm",
                {
                    "can_delete_any_message_group": orjson.dumps(
                        {"new": can_delete_any_message_group.id}
                    ).decode(),
                    "can_delete_own_message_group": orjson.dumps(
                        {"new": can_delete_own_message_group.id}
                    ).decode(),
                    "message_content_delete_limit_seconds": orjson.dumps(
                        message_content_delete_limit_seconds
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def test_delete_message_by_admin(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(iago, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_moderator(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(shiva, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_bot_owner(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(hamlet, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_other_user(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(cordelia, f"/api/v1/messages/{msg_id}")
            return result

        realm = get_realm("zulip")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )

        set_message_deleting_params(
            moderators_system_group, administrators_system_group, "unlimited"
        )

        hamlet = self.example_user("hamlet")
        test_bot = self.create_test_bot("test-bot", hamlet)
        msg_id_1 = self.send_stream_message(test_bot, "Denmark")
        msg_id_2 = self.send_stream_message(test_bot, "Denmark")

        result = test_delete_message_by_other_user(msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        # Admins and moderators can delete any message.
        result = test_delete_message_by_moderator(msg_id_1)
        self.assert_json_success(result)

        result = test_delete_message_by_admin(msg_id_2)
        self.assert_json_success(result)

        msg_id = self.send_stream_message(test_bot, "Denmark")
        set_message_deleting_params(administrators_system_group, everyone_system_group, "unlimited")

        result = test_delete_message_by_other_user(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id)
        self.assert_json_success(result)

        msg_id = self.send_stream_message(test_bot, "Denmark")
        set_message_deleting_params(administrators_system_group, everyone_system_group, 600)

        message = Message.objects.get(id=msg_id)
        message.date_sent = timezone_now() - timedelta(seconds=700)
        message.save()

        result = test_delete_message_by_other_user(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        result = test_delete_message_by_admin(msg_id)
        self.assert_json_success(result)

        # Check that the bot can also delete the messages sent by them
        # depending on the realm permissions for message deletion.
        set_message_deleting_params(administrators_system_group, administrators_system_group, 600)
        msg_id = self.send_stream_message(test_bot, "Denmark")
        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_error(result, "You don't have permission to delete this message")

        set_message_deleting_params(administrators_system_group, everyone_system_group, 600)
        message = Message.objects.get(id=msg_id)
        message.date_sent = timezone_now() - timedelta(seconds=700)
        message.save()

        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        message.date_sent = timezone_now() - timedelta(seconds=400)
        message.save()
        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_success(result)

    def test_delete_message_according_to_can_delete_any_message_group(self) -> None:
        def check_delete_message_by_sender(
            sender_name: str, error_msg: str | None = None, is_stream_message: bool = True
        ) -> None:
            sender = self.example_user(sender_name)
            if is_stream_message:
                msg_id = self.send_stream_message(sender, "Verona")
            else:
                msg_id = self.send_personal_message(sender, self.example_user("desdemona"))

            self.login_user(sender)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        def check_delete_message_by_other_user(
            sender_name: str,
            other_user_name: str,
            error_msg: str | None = None,
            is_stream_message: bool = True,
        ) -> None:
            sender = self.example_user(sender_name)
            other_user = self.example_user(other_user_name)
            if is_stream_message:
                msg_id = self.send_stream_message(sender, "Verona")
            else:
                msg_id = self.send_personal_message(sender, other_user)
            self.login_user(other_user)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)
        iago = self.example_user("iago")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
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

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            administrators_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            everyone_system_group,
            acting_user=None,
        )

        # Only admins can delete any message. Everyone else can only delete their
        # own message.
        check_delete_message_by_sender("shiva")
        check_delete_message_by_other_user(
            "hamlet", "shiva", "You don't have permission to delete this message"
        )
        check_delete_message_by_other_user("hamlet", "iago")

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            moderators_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            administrators_system_group,
            acting_user=None,
        )

        # Admins and moderators can delete any message. No one else can delete any
        # message.

        # Test deleting channel messages
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("shiva")
        check_delete_message_by_other_user("iago", "shiva")
        check_delete_message_by_other_user(
            "hamlet", "cordelia", "You don't have permission to delete this message"
        )
        # Test deleting DMs
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message", is_stream_message=False
        )
        check_delete_message_by_sender("shiva", is_stream_message=False)
        check_delete_message_by_other_user("iago", "shiva", is_stream_message=False)
        check_delete_message_by_other_user(
            "hamlet",
            "cordelia",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )

        # Check that guest cannot delete any message even when they are member
        # of the group which is allowed to delete any message.
        polonius = self.example_user("polonius")
        hamlet = self.example_user("hamlet")
        user_group = check_add_user_group(
            realm, "test-group", [hamlet, polonius], acting_user=hamlet
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            user_group,
            acting_user=None,
        )
        # Test deleting channel messages
        check_delete_message_by_other_user("cordelia", "hamlet")
        check_delete_message_by_other_user(
            "cordelia", "polonius", "You don't have permission to delete this message"
        )
        # Test deleting DMs
        check_delete_message_by_other_user(
            "cordelia",
            "polonius",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            nobody_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            nobody_system_group,
            acting_user=None,
        )

        check_delete_message_by_other_user(
            "cordelia", "shiva", "You don't have permission to delete this message"
        )
        check_delete_message_by_other_user(
            "cordelia",
            "shiva",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_any_message_group",
            moderators_system_group,
            acting_user=iago,
        )
        # Users in channel-level `can_delete_any_message_group` can delete
        # any message in the channel.
        check_delete_message_by_other_user("cordelia", "shiva")
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_any_message_group",
            nobody_system_group,
            acting_user=iago,
        )
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            moderators_system_group,
            acting_user=iago,
        )
        # Channel administrators can't delete messages if they don't have
        # the required permissions.
        check_delete_message_by_other_user(
            "cordelia", "shiva", "You don't have permission to delete this message"
        )
        check_delete_message_by_other_user(
            "cordelia", "iago", "You don't have permission to delete this message"
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_any_message_group",
            everyone_system_group,
            acting_user=iago,
        )
        # Everyone is allowed to delete any message in the channel.
        check_delete_message_by_other_user("cordelia", "polonius")
        check_delete_message_by_other_user("cordelia", "iago")

        # Cannot delete DMs as organization-level permission is set to nobody.
        check_delete_message_by_other_user(
            "cordelia",
            "iago",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )
        check_delete_message_by_sender(
            "iago", "You don't have permission to delete this message", is_stream_message=False
        )

    def test_delete_message_according_to_can_delete_own_message_group(self) -> None:
        def check_delete_message_by_sender(
            sender_name: str, error_msg: str | None = None, is_stream_message: bool = True
        ) -> None:
            sender = self.example_user(sender_name)
            if is_stream_message:
                msg_id = self.send_stream_message(sender, "Verona")
            else:
                msg_id = self.send_personal_message(sender, self.example_user("desdemona"))

            self.login_user(sender)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)
        iago = self.example_user("iago")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            administrators_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            nobody_system_group,
            acting_user=None,
        )
        # Test deleting channel messages
        check_delete_message_by_sender("shiva", "You don't have permission to delete this message")
        check_delete_message_by_sender("iago")
        # Test deleting DMs
        check_delete_message_by_sender(
            "shiva", "You don't have permission to delete this message", is_stream_message=False
        )
        check_delete_message_by_sender("iago", is_stream_message=False)

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            moderators_system_group,
            acting_user=None,
        )
        # Test deleting channel messages
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("shiva")
        # Test deleting DMs
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message", is_stream_message=False
        )
        check_delete_message_by_sender("shiva", is_stream_message=False)

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            members_system_group,
            acting_user=None,
        )
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("cordelia")

        do_change_realm_permission_group_setting(
            realm, "can_delete_own_message_group", everyone_system_group, acting_user=None
        )
        # Test deleting channel messages
        check_delete_message_by_sender("cordelia")
        check_delete_message_by_sender("polonius")
        # Test deleting DMs
        check_delete_message_by_sender("cordelia", is_stream_message=False)
        check_delete_message_by_sender("polonius", is_stream_message=False)

        do_change_realm_permission_group_setting(
            realm, "can_delete_own_message_group", nobody_system_group, acting_user=None
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_own_message_group",
            members_system_group,
            acting_user=iago,
        )
        # Users in per-channel `can_delete_own_message_group` can delete their
        # own messages.
        check_delete_message_by_sender("hamlet")
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_own_message_group",
            nobody_system_group,
            acting_user=iago,
        )
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            moderators_system_group,
            acting_user=iago,
        )
        # Channel administrators can't delete messages if they don't have
        # the required permissions.
        check_delete_message_by_sender("shiva", "You don't have permission to delete this message")
        check_delete_message_by_sender("iago", "You don't have permission to delete this message")

        do_change_stream_group_based_setting(
            stream,
            "can_delete_own_message_group",
            everyone_system_group,
            acting_user=iago,
        )
        check_delete_message_by_sender("iago")

        # Cannot delete DMs as organization-level permission is set to nobody.
        check_delete_message_by_sender(
            "iago", "You don't have permission to delete this message", is_stream_message=False
        )

    def test_delete_event_sent_after_transaction_commits(self) -> None:
        """
        Tests that `send_event_rollback_unsafe` is hooked to `transaction.on_commit`.
        This is important, because we don't want to end up holding locks on message rows
        for too long if the event queue runs into a problem.
        """
        hamlet = self.example_user("hamlet")
        self.send_stream_message(hamlet, "Denmark")
        message = self.get_last_message()

        with (
            self.capture_send_event_calls(expected_num_events=1),
            mock.patch("zerver.tornado.django_api.queue_json_publish_rollback_unsafe") as m,
        ):
            m.side_effect = AssertionError(
                "Events should be sent only after the transaction commits."
            )
            do_delete_messages(hamlet.realm, [message], acting_user=None)

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

    def test_delete_message_from_archived_channel(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")

        stream = self.make_stream("stream1")
        self.subscribe(hamlet, "stream1")
        msg_id = self.send_stream_message(
            hamlet, "stream1", topic_name="editing", content="before edit"
        )
        do_deactivate_stream(stream, acting_user=hamlet)

        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_error(result, "Invalid message(s)")

    def test_update_first_message_id_on_stream_message_deletion(self) -> None:
        realm = get_realm("zulip")
        stream_name = "test"
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name)
        self.subscribe(cordelia, stream_name)
        message_ids = [self.send_stream_message(cordelia, stream_name) for _ in range(5)]
        first_message_id = message_ids[0]

        message = Message.objects.get(id=message_ids[3])
        do_delete_messages(realm, [message], acting_user=None)
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, first_message_id)

        first_message = Message.objects.get(id=first_message_id)
        do_delete_messages(realm, [first_message], acting_user=None)
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, message_ids[1])

        all_messages = Message.objects.filter(id__in=message_ids)
        with self.assert_database_query_count(27):
            do_delete_messages(realm, all_messages, acting_user=None)
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, None)

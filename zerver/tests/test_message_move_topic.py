from datetime import timedelta
from typing import Any
from unittest import mock

import orjson
import time_machine
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import (
    build_message_edit_request,
    check_update_message,
    do_update_message,
    maybe_send_resolve_topic_notifications,
)
from zerver.actions.reactions import do_add_reaction
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_set_realm_property,
)
from zerver.actions.streams import do_change_stream_group_based_setting, do_set_stream_property
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.message import truncate_topic
from zerver.lib.test_classes import ZulipTestCase, get_topic_messages
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX
from zerver.lib.types import StreamMessageEditRequest, UserGroupMembersData
from zerver.lib.user_topics import (
    get_users_with_user_topic_visibility_policy,
    set_topic_visibility_policy,
    topic_has_visibility_policy,
)
from zerver.lib.utils import assert_is_not_none
from zerver.models import Message, UserMessage, UserProfile, UserTopic
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.groups import NamedUserGroup, SystemGroups
from zerver.models.realms import RealmTopicsPolicyEnum
from zerver.models.streams import Stream, StreamTopicsPolicyEnum, get_stream
from zerver.models.users import ResolvedTopicNoticeAutoReadPolicyEnum


class MessageMoveTopicTest(ZulipTestCase):
    def check_topic(self, msg_id: int, topic_name: str) -> None:
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.topic_name(), topic_name)

    def assert_move_message(
        self,
        user: str,
        orig_stream: Stream,
        orig_topic_name: str = "test",
        stream_id: int | None = None,
        topic_name: str | None = None,
        expected_error: str | None = None,
    ) -> None:
        user_profile = self.example_user(user)
        self.subscribe(user_profile, orig_stream.name)
        message_id = self.send_stream_message(
            user_profile, orig_stream.name, topic_name=orig_topic_name
        )

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

    def assert_has_visibility_policy(
        self,
        user_profile: UserProfile,
        topic_name: str,
        stream: Stream,
        visibility_policy: int,
        *,
        expected: bool = True,
    ) -> None:
        if expected:
            self.assertTrue(
                topic_has_visibility_policy(user_profile, stream.id, topic_name, visibility_policy)
            )
        else:
            self.assertFalse(
                topic_has_visibility_policy(user_profile, stream.id, topic_name, visibility_policy)
            )

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

    def test_edit_message_empty_topic_with_extra_space(self) -> None:
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
        self.assert_json_success(result)
        self.check_topic(msg_id, "")

    def test_topic_required_in_mandatory_topic_realm(self) -> None:
        admin_user = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        realm = admin_user.realm
        self.login_user(admin_user)

        stream = self.make_stream("new_stream")
        stream_mandatory_topics = self.make_stream(
            "topics_required", topics_policy=StreamTopicsPolicyEnum.disable_empty_topic.value
        )
        self.subscribe(admin_user, stream.name)
        self.subscribe(hamlet, stream.name)

        original_topic_name = "topic 1"
        message_id = self.send_stream_message(
            hamlet,
            stream.name,
            topic_name=original_topic_name,
        )

        # Verify with topics_policy=disable_empty_topic:
        # * A topic can't be moved to an empty topic
        # * A topic can be moved to a non-empty topic
        do_set_realm_property(
            realm,
            "topics_policy",
            RealmTopicsPolicyEnum.disable_empty_topic,
            acting_user=admin_user,
        )

        for topic_name in ["(no topic)", ""]:
            result = self.client_patch(
                f"/json/messages/{message_id}",
                {
                    "topic": topic_name,
                },
            )
            self.assert_json_error(
                result, "Sending messages to the general chat is not allowed in this channel."
            )
            self.check_topic(message_id, topic_name=original_topic_name)

        new_topic_name = "new valid topic"
        result = self.client_patch(
            f"/json/messages/{message_id}",
            {
                "topic": new_topic_name,
            },
        )
        self.assert_json_success(result)
        self.check_topic(message_id, new_topic_name)

        # Verify with topics_policy=allow_empty_topic:
        # * A topic can be moved to an empty topic
        # * A topic can be moved to a non-empty topic
        do_set_realm_property(
            realm, "topics_policy", RealmTopicsPolicyEnum.allow_empty_topic, acting_user=admin_user
        )

        for topic_name in ["(no topic)", "", "non-empty topic"]:
            result = self.client_patch(
                f"/json/messages/{message_id}",
                {
                    "topic": topic_name,
                },
            )
            self.assert_json_success(result)
            self.check_topic(message_id, topic_name)

        # Test that message cannot be moved to empty topic in stream with
        # `topics_policy=disable_empty_topic`.
        for topic_name in ["(no topic)", ""]:
            result = self.client_patch(
                f"/json/messages/{message_id}",
                {"topic": topic_name, "stream_id": stream_mandatory_topics.id},
            )
            self.assert_json_error(
                result, "Sending messages to the general chat is not allowed in this channel."
            )
            self.check_topic(message_id, topic_name="non-empty topic")

        # Test that message cannot be moved to empty topic in stream with
        # `topics_policy=disable_empty_topic` when `topic_name` is `None`.
        for topic_name in ["(no topic)", ""]:
            message_id = self.send_stream_message(
                hamlet,
                stream.name,
                topic_name=topic_name,
            )
            result = self.client_patch(
                f"/json/messages/{message_id}",
                {"stream_id": stream_mandatory_topics.id},
            )
            self.assert_json_error(
                result, "Sending messages to the general chat is not allowed in this channel."
            )
            self.check_topic(message_id, topic_name="")

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

        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "topic": f"{Message.DM_TOPIC}",
            },
        )
        self.assert_json_error(result, "Invalid character in topic, at position 1!")

    @mock.patch("zerver.actions.message_edit.send_event_on_commit")
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
            users_to_be_notified: list[dict[str, Any]],
        ) -> None:
            message_edit_request = build_message_edit_request(
                message=message,
                user_profile=user_profile,
                propagate_mode="change_later",
                stream_id=None,
                topic_name=topic_name,
                content=None,
            )
            do_update_message(
                user_profile=user_profile,
                target_message=message,
                message_edit_request=message_edit_request,
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                rendering_result=None,
                prior_mention_user_ids=set(),
                mention_data=None,
            )

            mock_send_event.assert_called_with(mock.ANY, mock.ANY, users_to_be_notified)

        # Returns the users that need to be notified when a message topic is changed
        def notify(user_id: int) -> dict[str, Any]:
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

    @mock.patch("zerver.actions.user_topics.send_event_on_commit")
    def test_edit_muted_topic(self, mock_send_event_on_commit: mock.MagicMock) -> None:
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

        already_muted_topic_name = "Already muted topic"
        muted_topics = [
            [stream_name, "Topic1"],
            [stream_name, "Topic2"],
            [stream_name, already_muted_topic_name],
        ]
        set_topic_visibility_policy(hamlet, muted_topics, UserTopic.VisibilityPolicy.MUTED)
        set_topic_visibility_policy(cordelia, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        # users that need to be notified by send_event in the case of change-topic-name operation.
        users_to_be_notified_via_muted_topics_event: list[int] = []
        users_to_be_notified_via_user_topic_event: list[int] = []
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
        with self.assert_database_query_count(27):
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
        users_notified_via_muted_topics_event: list[int] = []
        users_notified_via_user_topic_event: list[int] = []
        for call_args in mock_send_event_on_commit.call_args_list:
            (_arg_realm, arg_event, arg_notified_users) = call_args[0]
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
            topic_name=already_muted_topic_name,
            propagate_mode="change_all",
            send_notification_to_old_thread=False,
            send_notification_to_new_thread=False,
            content=None,
        )
        assert_is_topic_muted(hamlet, stream.id, change_later_topic_name, muted=False)
        assert_is_topic_muted(hamlet, stream.id, already_muted_topic_name, muted=True)

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
        with self.assert_database_query_count(35):
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

        with self.assert_database_query_count(31):
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

    @mock.patch("zerver.actions.user_topics.send_event_on_commit")
    def test_edit_unmuted_topic(self, mock_send_event_on_commit: mock.MagicMock) -> None:
        stream_name = "Stream 123"
        stream = self.make_stream(stream_name)

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")
        othello = self.example_user("othello")

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
        users_to_be_notified_via_muted_topics_event: list[int] = []
        users_to_be_notified_via_user_topic_event: list[int] = []
        for user_topic in get_users_with_user_topic_visibility_policy(stream.id, "Topic1"):
            # We are appending the same data twice because 'user_topic' event notifies
            # the user during delete and create operation.
            users_to_be_notified_via_user_topic_event.append(user_topic.user_profile_id)
            users_to_be_notified_via_user_topic_event.append(user_topic.user_profile_id)
            # 'muted_topics' event notifies the user of muted topics during create
            # operation only.
            users_to_be_notified_via_muted_topics_event.append(user_topic.user_profile_id)

        change_all_topic_name = "Topic 1 edited"
        with self.assert_database_query_count(32):
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
        users_notified_via_muted_topics_event: list[int] = []
        users_notified_via_user_topic_event: list[int] = []
        for call_args in mock_send_event_on_commit.call_args_list:
            (_arg_realm, arg_event, arg_notified_users) = call_args[0]
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
        self.assert_has_visibility_policy(
            hamlet, "Topic1", stream, UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        self.assert_has_visibility_policy(
            cordelia, "Topic1", stream, UserTopic.VisibilityPolicy.MUTED, expected=False
        )
        self.assert_has_visibility_policy(
            othello, "Topic1", stream, UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        self.assert_has_visibility_policy(
            aaron, "Topic1", stream, UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        # No change in visibility_policy configurations for 'Topic2'
        self.assert_has_visibility_policy(
            hamlet, "Topic2", stream, UserTopic.VisibilityPolicy.UNMUTED, expected=True
        )
        self.assert_has_visibility_policy(
            cordelia, "Topic2", stream, UserTopic.VisibilityPolicy.MUTED, expected=True
        )
        self.assert_has_visibility_policy(
            othello, "Topic2", stream, UserTopic.VisibilityPolicy.UNMUTED, expected=True
        )
        self.assert_has_visibility_policy(
            aaron, "Topic2", stream, UserTopic.VisibilityPolicy.UNMUTED, expected=False
        )
        # UserTopic records moved to 'Topic 1 edited' after move-topic operation.
        self.assert_has_visibility_policy(
            hamlet, change_all_topic_name, stream, UserTopic.VisibilityPolicy.UNMUTED, expected=True
        )
        self.assert_has_visibility_policy(
            cordelia, change_all_topic_name, stream, UserTopic.VisibilityPolicy.MUTED, expected=True
        )
        self.assert_has_visibility_policy(
            othello,
            change_all_topic_name,
            stream,
            UserTopic.VisibilityPolicy.UNMUTED,
            expected=True,
        )
        self.assert_has_visibility_policy(
            aaron, change_all_topic_name, stream, UserTopic.VisibilityPolicy.MUTED, expected=False
        )

    def test_merge_user_topic_states_on_move_messages(self) -> None:
        stream_name = "Stream 123"
        stream = self.make_stream(stream_name)

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")
        shiva = self.example_user("shiva")

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
        #   INHERIT       FOLLOWED      FOLLOWED
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
        do_set_user_topic_visibility_policy(
            shiva, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
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

        self.assert_has_visibility_policy(
            hamlet, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            cordelia, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            aaron, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            shiva, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            hamlet, target_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            cordelia, target_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            aaron, target_topic, stream, UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assert_has_visibility_policy(
            shiva, target_topic, stream, UserTopic.VisibilityPolicy.FOLLOWED
        )

        # Test the following cases:
        #
        #  orig_topic | target_topic | final behaviour
        #     MUTED       INHERIT        INHERIT
        #     MUTED        MUTED          MUTED
        #     MUTED       UNMUTED        UNMUTED
        #     MUTED       FOLLOWED       FOLLOWED
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
            shiva, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )
        do_set_user_topic_visibility_policy(
            shiva, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
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

        self.assert_has_visibility_policy(
            hamlet, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            cordelia, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            aaron, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            shiva, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            hamlet, target_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            cordelia, target_topic, stream, UserTopic.VisibilityPolicy.MUTED
        )
        self.assert_has_visibility_policy(
            aaron, target_topic, stream, UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assert_has_visibility_policy(
            shiva, target_topic, stream, UserTopic.VisibilityPolicy.FOLLOWED
        )

        # Test the following cases:
        #
        #  orig_topic | target_topic | final behaviour
        #    UNMUTED       INHERIT        UNMUTED
        #    UNMUTED        MUTED         UNMUTED
        #    UNMUTED       UNMUTED        UNMUTED
        #    UNMUTED       FOLLOWED       FOLLOWED
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
            shiva, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )
        do_set_user_topic_visibility_policy(
            shiva, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
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

        self.assert_has_visibility_policy(
            hamlet, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            cordelia, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            aaron, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            shiva, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            hamlet, target_topic, stream, UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assert_has_visibility_policy(
            cordelia, target_topic, stream, UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assert_has_visibility_policy(
            aaron, target_topic, stream, UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assert_has_visibility_policy(
            shiva, target_topic, stream, UserTopic.VisibilityPolicy.FOLLOWED
        )

        # Test the following cases:
        #
        #  orig_topic | target_topic | final behaviour
        #   FOLLOWED     INHERIT         FOLLOWED
        #   FOLLOWED     MUTED           FOLLOWED
        #   FOLLOWED     UNMUTED         FOLLOWED
        orig_topic = "Topic4"
        target_topic = "Topic4 edited"
        orig_message_id = self.send_stream_message(
            hamlet, stream_name, topic_name=orig_topic, content="Hello World"
        )
        self.send_stream_message(
            hamlet, stream_name, topic_name=target_topic, content="Hello World 2"
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
        )

        do_set_user_topic_visibility_policy(
            hamlet, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
        )
        do_set_user_topic_visibility_policy(
            cordelia, stream, target_topic, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )
        do_set_user_topic_visibility_policy(
            aaron, stream, orig_topic, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
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

        self.assert_has_visibility_policy(
            hamlet, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            cordelia, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            aaron, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            hamlet, target_topic, stream, UserTopic.VisibilityPolicy.FOLLOWED
        )
        self.assert_has_visibility_policy(
            cordelia, target_topic, stream, UserTopic.VisibilityPolicy.FOLLOWED
        )
        self.assert_has_visibility_policy(
            aaron, target_topic, stream, UserTopic.VisibilityPolicy.FOLLOWED
        )

    def test_user_topic_states_on_moving_to_topic_with_no_messages(self) -> None:
        stream_name = "Stream 123"
        stream = self.make_stream(stream_name)

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")

        self.subscribe(hamlet, stream_name)
        self.subscribe(cordelia, stream_name)
        self.subscribe(aaron, stream_name)

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

        self.assert_has_visibility_policy(
            hamlet, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            cordelia, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            aaron, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )
        self.assert_has_visibility_policy(
            hamlet, target_topic, stream, UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assert_has_visibility_policy(
            cordelia, target_topic, stream, UserTopic.VisibilityPolicy.MUTED
        )
        self.assert_has_visibility_policy(
            aaron, target_topic, stream, UserTopic.VisibilityPolicy.INHERIT
        )

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
            members_system_group = NamedUserGroup.objects.get(
                name=SystemGroups.MEMBERS, realm_for_sharding=hamlet.realm, is_system_group=True
            )
            do_change_realm_permission_group_setting(
                hamlet.realm,
                "can_delete_own_message_group",
                members_system_group,
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

            self.assert_has_visibility_policy(
                hamlet, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
            )
            self.assert_has_visibility_policy(
                cordelia, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
            )
            self.assert_has_visibility_policy(
                aaron, orig_topic, stream, UserTopic.VisibilityPolicy.INHERIT
            )
            self.assert_has_visibility_policy(hamlet, target_topic, stream, original_topic_state)
            self.assert_has_visibility_policy(cordelia, target_topic, stream, original_topic_state)
            self.assert_has_visibility_policy(aaron, target_topic, stream, original_topic_state)

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

    def test_topic_edit_history_saved_in_all_message(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Verona", topic_name="topic1")
        id4 = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="topic2")
        id5 = self.send_stream_message(self.example_user("iago"), "Denmark", topic_name="topic1")

        def verify_edit_history(new_topic_name: str, len_edit_history: int) -> None:
            for msg_id in [id1, id2, id5]:
                msg = Message.objects.get(id=msg_id)

                self.assertEqual(
                    new_topic_name,
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

        new_topic_name = "edited"
        result = self.client_patch(
            f"/json/messages/{id1}",
            {
                "topic": new_topic_name,
                "propagate_mode": "change_later",
            },
        )

        self.assert_json_success(result)
        verify_edit_history(new_topic_name, 1)

        new_topic_name = "edited2"
        result = self.client_patch(
            f"/json/messages/{id1}",
            {
                "topic": new_topic_name,
                "propagate_mode": "change_later",
            },
        )

        self.assert_json_success(result)
        verify_edit_history(new_topic_name, 2)

    def test_topic_and_content_edit(self) -> None:
        self.login("hamlet")
        id1 = self.send_stream_message(self.example_user("hamlet"), "Denmark", "message 1", "topic")
        id2 = self.send_stream_message(self.example_user("iago"), "Denmark", "message 2", "topic")
        id3 = self.send_stream_message(self.example_user("hamlet"), "Denmark", "message 3", "topic")

        new_topic_name = "edited"
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": new_topic_name,
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
                new_topic_name,
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
        message.date_sent -= timedelta(days=10)
        message.save()

        message = Message.objects.get(id=id2)
        message.date_sent -= timedelta(days=9)
        message.save()

        message = Message.objects.get(id=id3)
        message.date_sent -= timedelta(days=8)
        message.save()

        message = Message.objects.get(id=id4)
        message.date_sent -= timedelta(days=6)
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

        message_fetch_result = self.client_get(
            f"/json/messages/{msg_id}",
        )
        self.assert_json_success(message_fetch_result)
        message_dict = orjson.loads(message_fetch_result.content)["message"]
        self.assert_json_success(result)
        self.assertNotIn("last_moved_timestamp", message_dict)

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

        message_fetch_result = self.client_get(
            f"/json/messages/{msg_id}",
        )
        self.assert_json_success(message_fetch_result)
        message_dict = orjson.loads(message_fetch_result.content)["message"]
        self.assert_json_success(result)
        self.assertNotIn("last_moved_timestamp", message_dict)

    def test_notify_resolve_and_move_topic(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login("hamlet")
        stream = self.make_stream("public stream")
        topic_name = "test"
        self.subscribe(user_profile, stream.name)

        # Resolve a topic normally first
        time_zero = timezone_now().replace(microsecond=0)
        with time_machine.travel(time_zero, tick=False):
            msg_id = self.send_stream_message(
                user_profile, stream.name, "foo", topic_name=topic_name
            )
        resolved_topic_name = RESOLVED_TOPIC_PREFIX + topic_name
        first_message_move_time = time_zero + timedelta(seconds=2)
        with time_machine.travel(first_message_move_time, tick=False):
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "topic": resolved_topic_name,
                    "propagate_mode": "change_all",
                },
            )
            self.assert_json_success(result)

        messages = get_topic_messages(user_profile, stream, resolved_topic_name)
        self.assert_length(messages, 2)
        self.assertEqual(
            messages[1].content,
            f"@_**{user_profile.full_name}|{user_profile.id}** has marked this topic as resolved.",
        )

        message_fetch_result = self.client_get(
            f"/json/messages/{msg_id}",
        )
        self.assert_json_success(message_fetch_result)
        message_dict = orjson.loads(message_fetch_result.content)["message"]
        self.assert_json_success(result)
        self.assertNotIn("last_moved_timestamp", message_dict)

        # Test unresolving a topic while moving it (✔ test -> bar)
        new_topic_name = "bar"
        second_message_move_time = time_zero + timedelta(seconds=4)
        with time_machine.travel(second_message_move_time, tick=False):
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "topic": new_topic_name,
                    "propagate_mode": "change_all",
                },
            )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, stream, new_topic_name)
        self.assert_length(messages, 3)
        self.assertEqual(
            messages[2].content,
            f"This topic was moved here from #**public stream>✔ test** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

        message_fetch_result = self.client_get(
            f"/json/messages/{msg_id}",
        )
        self.assert_json_success(message_fetch_result)
        message_dict = orjson.loads(message_fetch_result.content)["message"]
        self.assert_json_success(result)
        self.assertEqual(
            message_dict["last_moved_timestamp"],
            datetime_to_timestamp(second_message_move_time),
        )

        # Now test moving the topic while also resolving it (bar -> ✔ baz)
        new_resolved_topic_name = RESOLVED_TOPIC_PREFIX + "baz"
        third_message_move_time = time_zero + timedelta(seconds=6)
        with time_machine.travel(third_message_move_time, tick=False):
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "topic": new_resolved_topic_name,
                    "propagate_mode": "change_all",
                },
            )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, stream, new_resolved_topic_name)
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**public stream>{new_topic_name}** by @_**{user_profile.full_name}|{user_profile.id}**.",
        )

        message_fetch_result = self.client_get(
            f"/json/messages/{msg_id}",
        )
        self.assert_json_success(message_fetch_result)
        message_dict = orjson.loads(message_fetch_result.content)["message"]
        self.assert_json_success(result)
        self.assertEqual(
            message_dict["last_moved_timestamp"],
            datetime_to_timestamp(third_message_move_time),
        )

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

        original_topic_name = "topic 1"
        id1 = self.send_stream_message(hamlet, "new", topic_name=original_topic_name)
        id2 = self.send_stream_message(admin_user, "new", topic_name=original_topic_name)

        msg1 = Message.objects.get(id=id1)
        do_add_reaction(aaron, msg1, "tada", "1f389", "unicode_emoji")

        # Check that we don't incorrectly send "unresolve topic"
        # notifications when asking the preserve the current topic.
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": original_topic_name,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(result, "Nothing to change")

        resolved_topic_name = RESOLVED_TOPIC_PREFIX + original_topic_name
        result = self.resolve_topic_containing_message(
            admin_user,
            id1,
            HTTP_ACCEPT_LANGUAGE="de",
        )

        self.assert_json_success(result)
        for msg_id in [id1, id2]:
            msg = Message.objects.get(id=msg_id)
            self.assertEqual(
                resolved_topic_name,
                msg.topic_name(),
            )

        messages = get_topic_messages(admin_user, stream, resolved_topic_name)
        self.assert_length(messages, 3)
        self.assertEqual(
            messages[2].content,
            f"@_**Iago|{admin_user.id}** has marked this topic as resolved.",
        )

        # Now move to a weird state and confirm we get the normal topic moved message.
        weird_topic_name = "✔ ✔✔" + original_topic_name
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": weird_topic_name,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_success(result)
        for msg_id in [id1, id2]:
            msg = Message.objects.get(id=msg_id)
            self.assertEqual(
                weird_topic_name,
                msg.topic_name(),
            )

        messages = get_topic_messages(admin_user, stream, weird_topic_name)
        self.assert_length(messages, 4)
        self.assertEqual(
            messages[2].content,
            f"@_**Iago|{admin_user.id}** has marked this topic as resolved.",
        )
        self.assertEqual(
            messages[3].content,
            f"This topic was moved here from #**new>✔ topic 1** by @_**Iago|{admin_user.id}**.",
        )

        unresolved_topic_name = original_topic_name
        result = self.client_patch(
            "/json/messages/" + str(id1),
            {
                "topic": unresolved_topic_name,
                "propagate_mode": "change_all",
            },
        )

        self.assert_json_success(result)
        for msg_id in [id1, id2]:
            msg = Message.objects.get(id=msg_id)
            self.assertEqual(
                unresolved_topic_name,
                msg.topic_name(),
            )

        messages = get_topic_messages(admin_user, stream, unresolved_topic_name)
        self.assert_length(messages, 5)
        self.assertEqual(
            messages[2].content, f"@_**Iago|{admin_user.id}** has marked this topic as resolved."
        )
        self.assertEqual(
            messages[4].content,
            f"@_**Iago|{admin_user.id}** has marked this topic as unresolved.",
        )

    def test_resolved_topic_notice_auto_read_policy(self) -> None:
        # Test that resolved and unresolved-topic notices are marked as
        # read/unread based on the 'resolved_topic_notice_auto_read_policy'
        # setting for followed and unfollowed topics.
        self.login("iago")
        admin_user = self.example_user("iago")
        aaron = self.example_user("aaron")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        do_change_user_setting(
            aaron,
            "resolved_topic_notice_auto_read_policy",
            ResolvedTopicNoticeAutoReadPolicyEnum.always,
            acting_user=None,
        )
        do_change_user_setting(
            cordelia,
            "resolved_topic_notice_auto_read_policy",
            ResolvedTopicNoticeAutoReadPolicyEnum.except_followed,
            acting_user=None,
        )
        do_change_user_setting(
            hamlet,
            "resolved_topic_notice_auto_read_policy",
            ResolvedTopicNoticeAutoReadPolicyEnum.never,
            acting_user=None,
        )

        stream = self.make_stream("stream")
        self.subscribe(admin_user, stream.name)
        self.subscribe(aaron, stream.name)
        self.subscribe(cordelia, stream.name)
        self.subscribe(hamlet, stream.name)

        followed_topic_name = "followed"
        msg_id_1 = self.send_stream_message(admin_user, "stream", topic_name=followed_topic_name)

        do_set_user_topic_visibility_policy(
            aaron,
            stream,
            followed_topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        do_set_user_topic_visibility_policy(
            cordelia,
            stream,
            followed_topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        do_set_user_topic_visibility_policy(
            hamlet,
            stream,
            followed_topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )

        resolved_followed_topic_name = RESOLVED_TOPIC_PREFIX + followed_topic_name
        result_1 = self.resolve_topic_containing_message(
            admin_user,
            msg_id_1,
        )
        self.assert_json_success(result_1)
        msg_1 = Message.objects.get(id=msg_id_1)
        self.assertEqual(resolved_followed_topic_name, msg_1.topic_name())

        messages = get_topic_messages(admin_user, stream, resolved_followed_topic_name)
        self.assert_length(messages, 2)

        unread_user_ids = self.get_user_ids_for_whom_message_unread(messages[1].id)
        read_user_ids = self.get_user_ids_for_whom_message_read(messages[1].id)

        # For the resolved-topic notice in a "followed" topic:
        # - aaron: policy 'always' -> notice is marked as read.
        # - cordelia: policy 'except_followed' and is following -> notice remains unread.
        # - hamlet: policy 'never' -> notice is remains unread.
        # - admin_user: is the one who resolved the topic -> notice is marked as read.
        self.assertEqual(unread_user_ids, {hamlet.id, cordelia.id})
        self.assertEqual(read_user_ids, {aaron.id, admin_user.id})

        unfollowed_topic_name = "unfollowed"
        msg_id_2 = self.send_stream_message(admin_user, "stream", topic_name=unfollowed_topic_name)
        resolved_unfollowed_topic_name = RESOLVED_TOPIC_PREFIX + unfollowed_topic_name
        result_2 = self.resolve_topic_containing_message(
            admin_user,
            msg_id_2,
        )
        self.assert_json_success(result_2)
        msg_2 = Message.objects.get(id=msg_id_2)
        self.assertEqual(resolved_unfollowed_topic_name, msg_2.topic_name())

        messages = get_topic_messages(admin_user, stream, resolved_unfollowed_topic_name)
        self.assert_length(messages, 2)

        unread_user_ids = self.get_user_ids_for_whom_message_unread(messages[1].id)
        read_user_ids = self.get_user_ids_for_whom_message_read(messages[1].id)

        # For the resolved-topic notice in an "unfollowed" topic:
        # - aaron: policy 'always' -> notice is marked as read.
        # - cordelia: policy 'except_followed' but not following -> notice is marked as read.
        # - hamlet: policy 'never' -> notice remains unread.
        # - admin_user: is the one who resolved the topic -> notice is marked as read.
        self.assertEqual(unread_user_ids, {hamlet.id})
        self.assertEqual(read_user_ids, {aaron.id, cordelia.id, admin_user.id})

        result_3 = self.client_patch(
            "/json/messages/" + str(msg_id_1),
            {
                "topic": followed_topic_name,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result_3)
        msg_3 = Message.objects.get(id=msg_id_1)
        self.assertEqual(followed_topic_name, msg_3.topic_name())

        messages = get_topic_messages(admin_user, stream, followed_topic_name)
        self.assert_length(messages, 3)

        unread_user_ids = self.get_user_ids_for_whom_message_unread(messages[2].id)
        read_user_ids = self.get_user_ids_for_whom_message_read(messages[2].id)

        # Unresolved-topic notices in a "followed" topic
        # behave similar to resolved-topic notices.
        self.assertEqual(unread_user_ids, {hamlet.id, cordelia.id})
        self.assertEqual(read_user_ids, {aaron.id, admin_user.id})

        result_4 = self.client_patch(
            "/json/messages/" + str(msg_id_2),
            {
                "topic": unfollowed_topic_name,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result_4)
        msg_4 = Message.objects.get(id=msg_id_2)
        self.assertEqual(unfollowed_topic_name, msg_4.topic_name())

        messages = get_topic_messages(admin_user, stream, unfollowed_topic_name)
        self.assert_length(messages, 3)

        unread_user_ids = self.get_user_ids_for_whom_message_unread(messages[2].id)
        read_user_ids = self.get_user_ids_for_whom_message_read(messages[2].id)

        # Unresolved-topic notices in an "unfollowed" topic
        # behave similar to resolved-topic notices.
        self.assertEqual(unread_user_ids, {hamlet.id})
        self.assertEqual(read_user_ids, {aaron.id, cordelia.id, admin_user.id})

        do_change_user_setting(
            aaron,
            "resolved_topic_notice_auto_read_policy",
            ResolvedTopicNoticeAutoReadPolicyEnum.never,
            acting_user=None,
        )
        do_change_user_setting(
            cordelia,
            "resolved_topic_notice_auto_read_policy",
            ResolvedTopicNoticeAutoReadPolicyEnum.never,
            acting_user=None,
        )
        do_change_user_setting(
            admin_user,
            "resolved_topic_notice_auto_read_policy",
            ResolvedTopicNoticeAutoReadPolicyEnum.never,
            acting_user=None,
        )

        # Test topic resolved notice is automatically mark as read for the user
        # who resolved the topic.
        msg_id_5 = self.send_stream_message(admin_user, "stream", topic_name=unfollowed_topic_name)
        result_5 = self.resolve_topic_containing_message(
            hamlet,
            msg_id_5,
        )
        self.assert_json_success(result_5)
        msg_5 = Message.objects.get(id=msg_id_5)
        self.assertEqual(resolved_unfollowed_topic_name, msg_5.topic_name())

        messages = get_topic_messages(admin_user, stream, resolved_unfollowed_topic_name)
        self.assert_length(messages, 5)

        unread_user_ids = self.get_user_ids_for_whom_message_unread(messages[-1].id)
        read_user_ids = self.get_user_ids_for_whom_message_read(messages[-1].id)

        self.assertEqual(read_user_ids, {hamlet.id})
        self.assertEqual(unread_user_ids, {aaron.id, cordelia.id, admin_user.id})

    def test_move_message_notice_auto_read_for_acting_user(self) -> None:
        admin_user = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        stream = self.make_stream("stream", hamlet.realm)

        self.subscribe(admin_user, "stream")
        self.subscribe(cordelia, "stream")
        self.subscribe(hamlet, "stream")

        old_topic_name = "old topic"
        new_topic_name = "new topic"
        message_id = self.send_stream_message(hamlet, stream.name, topic_name=old_topic_name)

        result = self.api_patch(
            hamlet,
            "/api/v1/messages/" + str(message_id),
            {"topic": new_topic_name, "send_notification_to_old_thread": "true"},
        )
        self.assert_json_success(result)

        # Messages moved notice should be automatically mark as read for the user
        # who move the messages.
        old_topic_messages = get_topic_messages(admin_user, stream, old_topic_name)
        self.assert_length(old_topic_messages, 1)
        self.assertEqual(
            old_topic_messages[-1].content,
            "This topic was moved to #**stream>new topic** by @_**King Hamlet|10**.",
        )

        unread_user_ids = self.get_user_ids_for_whom_message_unread(old_topic_messages[-1].id)
        read_user_ids = self.get_user_ids_for_whom_message_read(old_topic_messages[-1].id)

        self.assertEqual(read_user_ids, {hamlet.id})
        self.assertEqual(unread_user_ids, {cordelia.id, admin_user.id})

        new_topic_messages = get_topic_messages(admin_user, stream, new_topic_name)
        self.assert_length(new_topic_messages, 2)
        self.assertEqual(
            new_topic_messages[-1].content,
            "This topic was moved here from #**stream>old topic** by @_**King Hamlet|10**.",
        )

        unread_user_ids = self.get_user_ids_for_whom_message_unread(new_topic_messages[-1].id)
        read_user_ids = self.get_user_ids_for_whom_message_read(new_topic_messages[-1].id)

        self.assertEqual(read_user_ids, {hamlet.id})
        self.assertEqual(unread_user_ids, {cordelia.id, admin_user.id})

    @override_settings(RESOLVE_TOPIC_UNDO_GRACE_PERIOD_SECONDS=60)
    def test_mark_topic_as_resolved_within_grace_period(self) -> None:
        self.login("iago")
        admin_user = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        stream = self.make_stream("new")
        self.subscribe(admin_user, stream.name)
        self.subscribe(hamlet, stream.name)
        original_topic = "topic 1"
        id1 = self.send_stream_message(
            hamlet, "new", content="message 1", topic_name=original_topic
        )
        id2 = self.send_stream_message(
            admin_user, "new", content="message 2", topic_name=original_topic
        )

        resolved_topic = RESOLVED_TOPIC_PREFIX + original_topic
        start_time = timezone_now()
        with time_machine.travel(start_time, tick=False):
            result = self.client_patch(
                "/json/messages/" + str(id1),
                {
                    "topic": resolved_topic,
                    "propagate_mode": "change_all",
                },
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

        unresolved_topic = original_topic

        # Now unresolve the topic within the grace period.
        with time_machine.travel(start_time + timedelta(seconds=30), tick=False):
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
        # The message about the topic having been resolved is gone.
        self.assert_length(messages, 2)
        self.assertEqual(
            messages[1].content,
            "message 2",
        )
        self.assertEqual(messages[0].content, "message 1")

        # Now resolve the topic again after the grace period
        with time_machine.travel(start_time + timedelta(seconds=61), tick=False):
            result = self.client_patch(
                "/json/messages/" + str(id1),
                {
                    "topic": resolved_topic,
                    "propagate_mode": "change_all",
                },
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

    def test_send_resolve_topic_notification_with_no_topic_messages(self) -> None:
        self.login("iago")
        admin_user = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        stream = self.make_stream("new")
        self.subscribe(admin_user, stream.name)
        self.subscribe(hamlet, stream.name)
        original_topic = "topic 1"
        message_id = self.send_stream_message(
            hamlet, "new", content="message 1", topic_name=original_topic
        )

        message = Message.objects.get(id=message_id)
        do_delete_messages(admin_user.realm, [message], acting_user=None)

        assert stream.recipient_id is not None
        resolve_topic = RESOLVED_TOPIC_PREFIX + original_topic
        message_edit_request = build_message_edit_request(
            message=message,
            user_profile=admin_user,
            propagate_mode="change_all",
            stream_id=None,
            topic_name=resolve_topic,
            content=None,
        )
        assert isinstance(message_edit_request, StreamMessageEditRequest)
        maybe_send_resolve_topic_notifications(
            user_profile=admin_user,
            message_edit_request=message_edit_request,
            users_following_topic=None,
        )

        topic_messages = get_topic_messages(admin_user, stream, resolve_topic)
        self.assert_length(topic_messages, 1)
        self.assertEqual(
            topic_messages[0].content,
            f"@_**Iago|{admin_user.id}** has marked this topic as resolved.",
        )

    def test_resolve_empty_string_topic(self) -> None:
        hamlet = self.example_user("hamlet")

        message_id = self.send_stream_message(hamlet, "Denmark", topic_name="")
        result = self.resolve_topic_containing_message(hamlet, target_message_id=message_id)
        self.assert_json_error(result, "General chat cannot be marked as resolved")

        # Verification for old clients that don't support empty string topic.
        message_id = self.send_stream_message(
            hamlet, "Denmark", topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME
        )
        result = self.resolve_topic_containing_message(hamlet, target_message_id=message_id)
        self.assert_json_error(result, "General chat cannot be marked as resolved")

    def test_resolved_topic_realm_level_permissions(self) -> None:
        self.login("iago")
        admin_user = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        admin_user.default_language = "de"
        admin_user.save()
        stream = self.make_stream("new")
        self.subscribe(admin_user, stream.name)
        self.subscribe(hamlet, stream.name)

        original_topic_name = "topic 1"
        id1 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)

        # Test resolving topics disabled by organization
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=admin_user.realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            admin_user.realm,
            "can_resolve_topics_group",
            nobody_group,
            acting_user=None,
        )

        result = self.resolve_topic_containing_message(
            admin_user,
            id1,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        # Test restrict resolving topics to admins only.
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS,
            realm_for_sharding=admin_user.realm,
            is_system_group=True,
        )
        do_change_realm_permission_group_setting(
            admin_user.realm,
            "can_resolve_topics_group",
            admins_group,
            acting_user=None,
        )

        result = self.resolve_topic_containing_message(
            hamlet,
            id1,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        result = self.resolve_topic_containing_message(
            admin_user,
            id1,
        )
        self.assert_json_success(result)

        # Test restrict resolving topics to a user defined group.
        original_topic_name = "topic 2"
        id2 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)
        leadership_group = check_add_user_group(
            admin_user.realm, "leadership", [hamlet], acting_user=hamlet
        )
        do_change_realm_permission_group_setting(
            admin_user.realm, "can_resolve_topics_group", leadership_group, acting_user=None
        )

        result = self.resolve_topic_containing_message(
            othello,
            id2,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        result = self.resolve_topic_containing_message(
            admin_user,
            id2,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        result = self.resolve_topic_containing_message(
            hamlet,
            id2,
        )
        self.assert_json_success(result)

        # Test restrict topics to an anonymous group.
        original_topic_name = "topic 3"
        id3 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)
        staff_group = check_add_user_group(
            admin_user.realm, "Staff", [admin_user], acting_user=admin_user
        )
        anonymous_setting_group = self.create_or_update_anonymous_group_for_setting(
            [cordelia], [staff_group]
        )
        do_change_realm_permission_group_setting(
            admin_user.realm, "can_resolve_topics_group", anonymous_setting_group, acting_user=None
        )

        result = self.resolve_topic_containing_message(
            othello,
            id3,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        result = self.resolve_topic_containing_message(
            cordelia,
            id3,
        )
        self.assert_json_success(result)

        id3 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)
        result = self.resolve_topic_containing_message(
            admin_user,
            id3,
        )
        self.assert_json_success(result)

        # Test resolving topics when there is no permission to move topics.
        do_change_realm_permission_group_setting(
            admin_user.realm,
            "can_move_messages_between_topics_group",
            nobody_group,
            acting_user=None,
        )
        original_topic_name = "topic 4"
        id4 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)

        # Do not allow if there is some change other than adding
        # RESOLVED_TOPIC_PREFIX
        self.login_user(cordelia)
        result = self.client_patch(
            "/json/messages/" + str(id4),
            {
                "topic": RESOLVED_TOPIC_PREFIX + "topic 45",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(result, "You don't have permission to edit this message")

        result = self.resolve_topic_containing_message(
            cordelia,
            id4,
        )
        self.assert_json_success(result)

        # Test resolving topics when time limit for moving messages between
        # topics has passed.
        do_change_realm_permission_group_setting(
            admin_user.realm,
            "can_move_messages_between_topics_group",
            anonymous_setting_group,
            acting_user=None,
        )
        do_set_realm_property(
            admin_user.realm, "move_messages_within_stream_limit_seconds", 3600, acting_user=None
        )
        original_topic_name = "topic 5"
        id5 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)
        message = Message.objects.get(id=id5)
        message.date_sent -= timedelta(seconds=4000)
        message.save()

        # Do not allow if there is some change other than adding
        # RESOLVED_TOPIC_PREFIX
        self.login_user(cordelia)
        result = self.client_patch(
            "/json/messages/" + str(id5),
            {
                "topic": RESOLVED_TOPIC_PREFIX + "topic 56",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(
            result, "The time limit for editing this message's topic has passed."
        )

        result = self.resolve_topic_containing_message(
            cordelia,
            id5,
        )
        self.assert_json_success(result)

    def test_resolved_topic_channel_level_permissions(self) -> None:
        admin_user = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        stream = self.make_stream("new")
        self.subscribe(admin_user, stream.name)
        self.subscribe(hamlet, stream.name)

        # Set resolving topics disabled by organization
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=admin_user.realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            admin_user.realm,
            "can_resolve_topics_group",
            nobody_group,
            acting_user=None,
        )

        # Test resolving topics disabled in a particular channel.
        original_topic_name = "topic 1"
        id1 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)

        do_change_stream_group_based_setting(
            stream, "can_resolve_topics_group", nobody_group, acting_user=admin_user
        )
        result = self.resolve_topic_containing_message(
            admin_user,
            id1,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        # Test restrict resolving topics to admins only in a particular channel.
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS,
            realm_for_sharding=admin_user.realm,
            is_system_group=True,
        )
        do_change_stream_group_based_setting(
            stream, "can_resolve_topics_group", admins_group, acting_user=admin_user
        )

        result = self.resolve_topic_containing_message(
            hamlet,
            id1,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        result = self.resolve_topic_containing_message(
            admin_user,
            id1,
        )
        self.assert_json_success(result)

        # Test restrict resolving topics to a user defined group in a particular channel.
        original_topic_name = "topic 2"
        id2 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)

        leadership_group = check_add_user_group(
            admin_user.realm, "leadership", [hamlet], acting_user=hamlet
        )

        do_change_stream_group_based_setting(
            stream, "can_resolve_topics_group", leadership_group, acting_user=admin_user
        )

        result = self.resolve_topic_containing_message(
            othello,
            id2,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        result = self.resolve_topic_containing_message(
            admin_user,
            id2,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        result = self.resolve_topic_containing_message(
            hamlet,
            id2,
        )
        self.assert_json_success(result)

        # Test restrict topics to an anonymous group in a particular channel.
        original_topic_name = "topic 3"
        id3 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)

        othello_group_member_dict = UserGroupMembersData(
            direct_members=[othello.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            stream, "can_resolve_topics_group", othello_group_member_dict, acting_user=othello
        )

        result = self.resolve_topic_containing_message(
            admin_user,
            id3,
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )
        result = self.resolve_topic_containing_message(
            othello,
            id3,
        )
        self.assert_json_success(result)

        # Test resolving topics while moving topics between different streams.
        # User can resolve the topic when moving it between streams if they have
        # permission to resolve topics in either the source or destination stream.
        original_topic_name = "topic 4"
        new_stream = self.make_stream("new stream")
        self.subscribe(hamlet, "new stream")
        id4 = self.send_stream_message(hamlet, new_stream.name, topic_name=original_topic_name)

        do_change_stream_group_based_setting(
            new_stream, "can_resolve_topics_group", nobody_group, acting_user=admin_user
        )

        result = self.api_patch(
            admin_user,
            "/api/v1/messages/" + str(id4),
            {"topic": RESOLVED_TOPIC_PREFIX + original_topic_name, "stream_id": stream.id},
        )
        self.assert_json_error(
            result, "You don't have permission to resolve topics in this channel."
        )

        # Othello can resolve the topic while moving it since he has permission to resolve topics
        # in the destination stream.
        result = self.api_patch(
            othello,
            "/api/v1/messages/" + str(id4),
            {"topic": RESOLVED_TOPIC_PREFIX + original_topic_name, "stream_id": stream.id},
        )
        self.assert_json_success(result)

        do_change_realm_permission_group_setting(
            admin_user.realm,
            "can_move_messages_between_topics_group",
            nobody_group,
            acting_user=None,
        )
        original_topic_name = "topic 5"
        id5 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)

        # Do not allow if there is some change other than adding
        # RESOLVED_TOPIC_PREFIX
        result = self.api_patch(
            othello,
            "/api/v1/messages/" + str(id5),
            {
                "topic": RESOLVED_TOPIC_PREFIX + "topic 45",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(result, "You don't have permission to edit this message")

        result = self.resolve_topic_containing_message(
            othello,
            id5,
        )
        self.assert_json_success(result)

        # Test resolving topics when time limit for moving messages between
        # topics has passed.
        do_change_realm_permission_group_setting(
            admin_user.realm,
            "can_move_messages_between_topics_group",
            leadership_group,
            acting_user=None,
        )
        do_set_realm_property(
            admin_user.realm, "move_messages_within_stream_limit_seconds", 3600, acting_user=None
        )
        do_change_stream_group_based_setting(
            stream, "can_resolve_topics_group", leadership_group, acting_user=admin_user
        )
        original_topic_name = "topic 6"
        id6 = self.send_stream_message(hamlet, stream.name, topic_name=original_topic_name)
        message = Message.objects.get(id=id6)
        message.date_sent -= timedelta(seconds=4000)
        message.save()

        # Do not allow if there is some change other than adding
        # RESOLVED_TOPIC_PREFIX
        result = self.api_patch(
            hamlet,
            "/api/v1/messages/" + str(id6),
            {
                "topic": RESOLVED_TOPIC_PREFIX + "topic 56",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(
            result, "The time limit for editing this message's topic has passed."
        )

        result = self.resolve_topic_containing_message(
            hamlet,
            id6,
        )
        self.assert_json_success(result)

    def test_can_move_messages_within_channel_group(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        realm = hamlet.realm

        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )

        expected_error = "You don't have permission to edit this message"

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_topics_group",
            nobody_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_channels_group",
            members_system_group,
            acting_user=None,
        )

        stream_1 = get_stream("Denmark", realm)
        stream_2 = get_stream("Verona", realm)

        # Nobody is allowed to move messages.
        self.assert_move_message(
            "hamlet", stream_1, topic_name="new topic", expected_error=expected_error
        )
        # Realm admin can always move messages within the channel.
        self.assert_move_message("iago", stream_1, topic_name="new topic")

        do_change_stream_group_based_setting(
            stream_1,
            "can_move_messages_within_channel_group",
            members_system_group,
            acting_user=iago,
        )
        # Only members are allowed to move messages within the channel.
        self.assert_move_message("hamlet", stream_1, topic_name="new topic")
        self.assert_move_message("cordelia", stream_1, topic_name="new topic")
        # Guests are not allowed.
        self.assert_move_message(
            "polonius", stream_1, topic_name="new topic", expected_error=expected_error
        )

        # Users are allowed to move messages to different topics out of the channel
        # if they are in `can_move_messages_within_channel_group` permission of either
        # the original channel or the destination channel.
        self.assert_move_message(
            "hamlet",
            stream_1,
            stream_id=stream_2.id,
            topic_name="new topic",
        )
        self.assert_move_message(
            "hamlet",
            stream_2,
            stream_id=stream_1.id,
            topic_name="new topic",
        )

        do_change_stream_group_based_setting(
            stream_1,
            "can_move_messages_within_channel_group",
            moderators_system_group,
            acting_user=iago,
        )
        # Hamlet can't move message to another topic now as he is not in
        # the `can_move_messages_within_channel_group` of either of the channel.
        self.assert_move_message(
            "hamlet",
            stream_1,
            stream_id=stream_2.id,
            topic_name="new topic",
            expected_error=expected_error,
        )
        # But he still can move messages between channel without changing the topic.
        self.assert_move_message(
            "hamlet",
            stream_1,
            stream_id=stream_2.id,
        )

        user_group = check_add_user_group(
            realm, "new_group", [hamlet, cordelia], acting_user=hamlet
        )
        do_change_stream_group_based_setting(
            stream_1, "can_move_messages_within_channel_group", user_group, acting_user=iago
        )

        # Hamlet and Cordelia are in the `can_move_messages_within_channel_group`,
        # so they can move messages within the channel.
        self.assert_move_message("cordelia", stream_1, topic_name="new topic")
        self.assert_move_message("hamlet", stream_1, topic_name="new topic")
        # But Shiva is not, so he can't.
        self.assert_move_message(
            "shiva", stream_1, topic_name="new topic", expected_error=expected_error
        )

        do_change_stream_group_based_setting(
            stream_1, "can_administer_channel_group", members_system_group, acting_user=iago
        )
        # Channel administrators with content access can always move messages within
        # the channel even if they are not in `can_move_messages_within_channel_group`.
        self.assert_move_message("shiva", stream_1, topic_name="new topic")

    def test_move_messages_within_channels_with_updated_topics_policy(self) -> None:
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_move_messages_between_topics_group",
            members_system_group,
            acting_user=None,
        )

        stream_1 = get_stream("Denmark", realm)

        self.assert_move_message("desdemona", stream_1, topic_name="")
        self.assert_move_message("desdemona", stream_1, topic_name="new topic")

        do_set_stream_property(
            stream_1,
            "topics_policy",
            StreamTopicsPolicyEnum.disable_empty_topic.value,
            acting_user=desdemona,
        )
        # Cannot move messages to empty topic as `topics_policy` is set to `disable_empty_topic`.
        self.assert_move_message(
            "desdemona",
            stream_1,
            topic_name="",
            expected_error="Sending messages to the general chat is not allowed in this channel.",
        )
        self.assert_move_message("desdemona", stream_1, topic_name="new topic")

        do_set_stream_property(
            stream_1,
            "topics_policy",
            StreamTopicsPolicyEnum.empty_topic_only.value,
            acting_user=desdemona,
        )

        # Cannot move messages to topics other than empty topic in the channels with
        # `topics_policy` set to `empty_topic_only`.
        self.assert_move_message(
            "desdemona",
            stream_1,
            orig_topic_name="",
            topic_name="new topic",
            expected_error="Only the general chat topic is allowed in this channel.",
        )

    def test_can_move_messages_can_create_topic_group(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        realm = hamlet.realm

        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        error_msg = "You do not have permission to create new topics in this channel."

        stream = get_stream("Denmark", realm)
        self.send_stream_message(hamlet, stream.name, topic_name="old topic")
        self.send_stream_message(hamlet, stream.name, topic_name="existing topic")

        def check_move_message(
            user_profile: UserProfile,
            stream: Stream,
            topic_name: str,
            expect_fail: bool = False,
        ) -> None:
            params = {
                "stream_id": stream.id,
                "topic": topic_name,
            }

            self.subscribe(user_profile, stream.name)
            msg_id = self.send_stream_message(user_profile, stream.name, topic_name="old topic")

            result = self.api_patch(
                user_profile,
                "/api/v1/messages/" + str(msg_id),
                params,
            )
            if expect_fail:
                self.assert_json_error(result, error_msg)
                return

            self.assert_json_success(result)
            if topic_name == "new topic":
                # Delete this topic, as it contains messages and is no longer new.
                messages = get_topic_messages(user_profile, stream, topic_name)
                do_delete_messages(user_profile.realm, messages, acting_user=None)

        # When nobody is allowed to move messages to new topics.
        do_change_stream_group_based_setting(
            stream, "can_create_topic_group", nobody_system_group, acting_user=iago
        )

        check_move_message(hamlet, stream, topic_name="new topic", expect_fail=True)
        check_move_message(iago, stream, topic_name="new topic", expect_fail=True)
        check_move_message(cordelia, stream, topic_name="new topic", expect_fail=True)

        # However moving messages to existing topics is allowed.
        check_move_message(hamlet, stream, topic_name="existing topic")
        check_move_message(iago, stream, topic_name="existing topic")
        check_move_message(cordelia, stream, topic_name="existing topic")

        # For a user defined group, its members can move messages to a new topic.
        do_change_stream_group_based_setting(
            stream,
            "can_create_topic_group",
            hamletcharacters_group,
            acting_user=iago,
        )
        check_move_message(iago, stream, topic_name="new topic", expect_fail=True)
        check_move_message(hamlet, stream, topic_name="new topic")
        check_move_message(cordelia, stream, topic_name="new topic")

        # However moving messages to existing topics is allowed.
        check_move_message(iago, stream, topic_name="existing topic")
        check_move_message(hamlet, stream, topic_name="existing topic")
        check_move_message(cordelia, stream, topic_name="existing topic")

        # For an anonymous group, its members can move messages to a new topic.
        anonymous_group = UserGroupMembersData(
            direct_members=[hamlet.id, iago.id],
            direct_subgroups=[],
        )
        do_change_stream_group_based_setting(
            stream,
            "can_create_topic_group",
            anonymous_group,
            acting_user=iago,
        )
        check_move_message(cordelia, stream, topic_name="new topic", expect_fail=True)
        check_move_message(hamlet, stream, topic_name="new topic")
        check_move_message(iago, stream, topic_name="new topic")

        # However moving messages to existing topics is allowed.
        check_move_message(cordelia, stream, topic_name="existing topic")
        check_move_message(hamlet, stream, topic_name="existing topic")
        check_move_message(iago, stream, topic_name="existing topic")

    def test_resolve_and_unresolve_topic_without_permission_to_create_new_topics(self) -> None:
        iago = self.example_user("iago")
        shiva = self.example_user("shiva")
        realm = iago.realm
        stream = get_stream("Verona", realm)

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )

        do_change_stream_group_based_setting(
            stream, "can_create_topic_group", admins_group, acting_user=iago
        )
        do_change_stream_group_based_setting(
            stream, "can_resolve_topics_group", moderators_group, acting_user=iago
        )

        self.subscribe(iago, stream.name)
        self.subscribe(shiva, stream.name)

        original_topic_name = "topic 1"
        msg_id = self.send_stream_message(iago, "Verona", topic_name=original_topic_name)

        # Test just changing to another topic fails.
        params = {
            "topic": "topic 2",
        }
        result = self.api_patch(
            shiva,
            "/api/v1/messages/" + str(msg_id),
            params,
        )
        self.assert_json_error(
            result, "You do not have permission to create new topics in this channel."
        )

        # Test changing anything other than adding the resolved topic prefix fails.
        params = {
            "topic": RESOLVED_TOPIC_PREFIX + "topic 2",
        }
        result = self.api_patch(
            shiva,
            "/api/v1/messages/" + str(msg_id),
            params,
        )
        self.assert_json_error(
            result, "You do not have permission to create new topics in this channel."
        )

        # Test resolving the topic works.
        resolved_topic_name = RESOLVED_TOPIC_PREFIX + original_topic_name
        params = {
            "topic": resolved_topic_name,
        }
        result = self.api_patch(
            shiva,
            "/api/v1/messages/" + str(msg_id),
            params,
        )
        self.assert_json_success(result)
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.topic_name(), resolved_topic_name)

        # Test unresolving the topic works.
        params = {
            "topic": original_topic_name,
        }
        result = self.api_patch(
            shiva,
            "/api/v1/messages/" + str(msg_id),
            params,
        )
        self.assert_json_success(result)
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.topic_name(), original_topic_name)

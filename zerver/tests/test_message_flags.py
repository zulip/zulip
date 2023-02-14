from typing import TYPE_CHECKING, Any, List, Mapping, Set
from unittest import mock

import orjson
from django.db import connection, transaction

from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.streams import do_change_stream_permission
from zerver.lib.fix_unreads import fix, fix_unsubscribed
from zerver.lib.message import (
    MessageDetailsDict,
    MessageDict,
    RawUnreadMessagesResult,
    RawUnreadPrivateMessageDict,
    UnreadMessagesResult,
    add_message_to_unread_msgs,
    aggregate_unread_data,
    apply_unread_message_event,
    bulk_access_messages,
    format_unread_message_details,
    get_raw_unread_data,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_subscription, timeout_mock
from zerver.lib.timeout import TimeoutExpiredError
from zerver.lib.user_topics import add_topic_mute
from zerver.models import (
    Message,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
    get_realm,
    get_stream,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def check_flags(flags: List[str], expected: Set[str]) -> None:
    """
    The has_alert_word flag can be ignored for most tests.
    """
    assert "has_alert_word" not in expected
    flag_set = set(flags)
    flag_set.discard("has_alert_word")
    if flag_set != expected:
        raise AssertionError(f"expected flags (ignoring has_alert_word) to be {expected}")


class FirstUnreadAnchorTests(ZulipTestCase):
    """
    HISTORICAL NOTE:

    The two tests in this class were originally written when
    we had the concept of a "pointer", and they may be a bit
    redundant in what they now check.
    """

    def test_use_first_unread_anchor(self) -> None:
        self.login("hamlet")

        # Mark all existing messages as read
        with timeout_mock("zerver.views.message_flags"):
            result = self.client_post("/json/mark_all_as_read")
        self.assert_json_success(result)

        # Send a new message (this will be unread)
        new_message_id = self.send_stream_message(self.example_user("othello"), "Verona", "test")

        # If we call get_messages with use_first_unread_anchor=True, we
        # should get the message we just sent
        messages_response = self.get_messages_response(
            anchor="first_unread", num_before=0, num_after=1
        )
        self.assertEqual(messages_response["messages"][0]["id"], new_message_id)
        self.assertEqual(messages_response["anchor"], new_message_id)

        # Test with the old way of expressing use_first_unread_anchor=True
        messages_response = self.get_messages_response(
            anchor=0, num_before=0, num_after=1, use_first_unread_anchor=True
        )
        self.assertEqual(messages_response["messages"][0]["id"], new_message_id)
        self.assertEqual(messages_response["anchor"], new_message_id)

        # We want to get the message_id of an arbitrary old message. We can
        # call get_messages with use_first_unread_anchor=False and simply
        # save the first message we're returned.
        messages = self.get_messages(
            anchor=0, num_before=0, num_after=2, use_first_unread_anchor=False
        )
        old_message_id = messages[0]["id"]

        # Verify the message is marked as read
        user_message = UserMessage.objects.get(
            message_id=old_message_id, user_profile=self.example_user("hamlet")
        )
        self.assertTrue(user_message.flags.read)

        # Let's set this old message to be unread
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps([old_message_id]).decode(), "op": "remove", "flag": "read"},
        )

        # Verify it's now marked as unread
        user_message = UserMessage.objects.get(
            message_id=old_message_id, user_profile=self.example_user("hamlet")
        )
        self.assert_json_success(result)
        self.assertFalse(user_message.flags.read)

        # Now if we call get_messages with use_first_unread_anchor=True,
        # we should get the old message we just set to unread
        messages_response = self.get_messages_response(
            anchor="first_unread", num_before=0, num_after=1
        )
        self.assertEqual(messages_response["messages"][0]["id"], old_message_id)
        self.assertEqual(messages_response["anchor"], old_message_id)

    def test_visible_messages_use_first_unread_anchor(self) -> None:
        self.login("hamlet")

        with timeout_mock("zerver.views.message_flags"):
            result = self.client_post("/json/mark_all_as_read")
        self.assert_json_success(result)

        new_message_id = self.send_stream_message(self.example_user("othello"), "Verona", "test")

        messages_response = self.get_messages_response(
            anchor="first_unread", num_before=0, num_after=1
        )
        self.assertEqual(messages_response["messages"][0]["id"], new_message_id)
        self.assertEqual(messages_response["anchor"], new_message_id)

        with mock.patch(
            "zerver.lib.narrow.get_first_visible_message_id", return_value=new_message_id
        ):
            messages_response = self.get_messages_response(
                anchor="first_unread", num_before=0, num_after=1
            )
        self.assertEqual(messages_response["messages"][0]["id"], new_message_id)
        self.assertEqual(messages_response["anchor"], new_message_id)

        with mock.patch(
            "zerver.lib.narrow.get_first_visible_message_id",
            return_value=new_message_id + 1,
        ):
            messages_response = self.get_messages_response(
                anchor="first_unread", num_before=0, num_after=1
            )
        self.assert_length(messages_response["messages"], 0)
        self.assertIn("anchor", messages_response)

        with mock.patch(
            "zerver.lib.narrow.get_first_visible_message_id",
            return_value=new_message_id - 1,
        ):
            messages = self.get_messages(anchor="first_unread", num_before=0, num_after=1)
        self.assert_length(messages, 1)


class UnreadCountTests(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        with mock.patch(
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
        ) as mock_push_notifications_enabled:
            self.unread_msg_ids = [
                self.send_personal_message(
                    self.example_user("iago"), self.example_user("hamlet"), "hello"
                ),
                self.send_personal_message(
                    self.example_user("iago"), self.example_user("hamlet"), "hello2"
                ),
            ]
            mock_push_notifications_enabled.assert_called()

    # Sending a new message results in unread UserMessages being created
    def test_new_message(self) -> None:
        self.login("hamlet")
        content = "Test message for unset read bit"
        last_msg = self.send_stream_message(self.example_user("hamlet"), "Verona", content)
        user_messages = list(UserMessage.objects.filter(message=last_msg))
        self.assertGreater(len(user_messages), 0)
        for um in user_messages:
            self.assertEqual(um.message.content, content)
            if um.user_profile.email != self.example_email("hamlet"):
                self.assertFalse(um.flags.read)

    def test_update_flags(self) -> None:
        self.login("hamlet")

        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(self.unread_msg_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)

        # Ensure we properly set the flags
        found = 0
        for msg in self.get_messages():
            if msg["id"] in self.unread_msg_ids:
                check_flags(msg["flags"], {"read"})
                found += 1
        self.assertEqual(found, 2)

        result = self.client_post(
            "/json/messages/flags",
            {
                "messages": orjson.dumps([self.unread_msg_ids[1]]).decode(),
                "op": "remove",
                "flag": "read",
            },
        )
        self.assert_json_success(result)

        # Ensure we properly remove just one flag
        for msg in self.get_messages():
            if msg["id"] == self.unread_msg_ids[0]:
                check_flags(msg["flags"], {"read"})
            elif msg["id"] == self.unread_msg_ids[1]:
                check_flags(msg["flags"], set())

    def test_update_flags_for_narrow(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        message_ids = [
            self.send_stream_message(
                self.example_user("cordelia"), "Verona", topic_name=f"topic {i % 2}"
            )
            for i in range(10)
        ]

        response = self.assert_json_success(
            self.client_post(
                "/json/messages/flags/narrow",
                {
                    "anchor": message_ids[5],
                    "num_before": 2,
                    "num_after": 2,
                    "narrow": "[]",
                    "op": "add",
                    "flag": "read",
                },
            )
        )
        self.assertEqual(response["processed_count"], 5)
        self.assertEqual(response["updated_count"], 5)
        self.assertEqual(response["first_processed_id"], message_ids[3])
        self.assertEqual(response["last_processed_id"], message_ids[7])
        self.assertEqual(response["found_oldest"], False)
        self.assertEqual(response["found_newest"], False)
        self.assertCountEqual(
            UserMessage.objects.filter(user_profile_id=user.id, message_id__in=message_ids)
            .extra(where=[UserMessage.where_read()])
            .values_list("message_id", flat=True),
            message_ids[3:8],
        )

        response = self.assert_json_success(
            self.client_post(
                "/json/messages/flags/narrow",
                {
                    "anchor": message_ids[3],
                    "include_anchor": "false",
                    "num_before": 0,
                    "num_after": 5,
                    "narrow": orjson.dumps(
                        [
                            {"operator": "stream", "operand": "Verona"},
                            {"operator": "topic", "operand": "topic 1"},
                        ]
                    ).decode(),
                    "op": "add",
                    "flag": "starred",
                },
            )
        )
        # In this topic (1, 3, 5, 7, 9), processes everything after 3.
        self.assertEqual(response["processed_count"], 3)
        self.assertEqual(response["updated_count"], 3)
        self.assertEqual(response["first_processed_id"], message_ids[5])
        self.assertEqual(response["last_processed_id"], message_ids[9])
        self.assertEqual(response["found_oldest"], False)
        self.assertEqual(response["found_newest"], True)
        self.assertCountEqual(
            UserMessage.objects.filter(user_profile_id=user.id, message_id__in=message_ids)
            .extra(where=[UserMessage.where_starred()])
            .values_list("message_id", flat=True),
            message_ids[5::2],
        )

    def test_update_flags_for_narrow_misuse(self) -> None:
        self.login("hamlet")

        response = self.client_post(
            "/json/messages/flags/narrow",
            {
                "anchor": "0",
                "include_anchor": "false",
                "num_before": "1",
                "num_after": "1",
                "narrow": "[]",
                "op": "add",
                "flag": "read",
            },
        )
        self.assert_json_error(response, "The anchor can only be excluded at an end of the range")

    def test_mark_all_in_stream_read(self) -> None:
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        stream = self.subscribe(user_profile, "test_stream")
        self.subscribe(self.example_user("cordelia"), "test_stream")

        message_id = self.send_stream_message(self.example_user("hamlet"), "test_stream", "hello")
        unrelated_message_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", "hello"
        )

        events: List[Mapping[str, Any]] = []
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.client_post(
                "/json/mark_stream_as_read",
                {
                    "stream_id": stream.id,
                },
            )

        self.assert_json_success(result)

        event = events[0]["event"]
        expected = dict(
            operation="add",
            messages=[message_id],
            flag="read",
            type="update_message_flags",
            all=False,
        )

        differences = [key for key in expected if expected[key] != event[key]]
        self.assert_length(differences, 0)

        hamlet = self.example_user("hamlet")
        um = list(UserMessage.objects.filter(message=message_id))
        for msg in um:
            if msg.user_profile.email == hamlet.email:
                self.assertTrue(msg.flags.read)
            else:
                self.assertFalse(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile.email == hamlet.email:
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_stream_read(self) -> None:
        self.login("hamlet")
        invalid_stream_id = "12345678"
        result = self.client_post(
            "/json/mark_stream_as_read",
            {
                "stream_id": invalid_stream_id,
            },
        )
        self.assert_json_error(result, "Invalid stream ID")

    def test_mark_all_topics_unread_with_invalid_stream_name(self) -> None:
        self.login("hamlet")
        invalid_stream_id = "12345678"
        result = self.client_post(
            "/json/mark_topic_as_read",
            {
                "stream_id": invalid_stream_id,
                "topic_name": "whatever",
            },
        )
        self.assert_json_error(result, "Invalid stream ID")

    def test_mark_all_in_stream_topic_read(self) -> None:
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        self.subscribe(user_profile, "test_stream")

        message_id = self.send_stream_message(
            self.example_user("hamlet"), "test_stream", "hello", "test_topic"
        )
        unrelated_message_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", "hello", "Denmark2"
        )
        events: List[Mapping[str, Any]] = []
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.client_post(
                "/json/mark_topic_as_read",
                {
                    "stream_id": get_stream("test_stream", user_profile.realm).id,
                    "topic_name": "test_topic",
                },
            )

        self.assert_json_success(result)

        event = events[0]["event"]
        expected = dict(
            operation="add",
            messages=[message_id],
            flag="read",
            type="update_message_flags",
            all=False,
        )

        differences = [key for key in expected if expected[key] != event[key]]
        self.assert_length(differences, 0)

        um = list(UserMessage.objects.filter(message=message_id))
        for msg in um:
            if msg.user_profile_id == user_profile.id:
                self.assertTrue(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile_id == user_profile.id:
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_topic_read(self) -> None:
        self.login("hamlet")
        invalid_topic_name = "abc"
        result = self.client_post(
            "/json/mark_topic_as_read",
            {
                "stream_id": get_stream("Denmark", get_realm("zulip")).id,
                "topic_name": invalid_topic_name,
            },
        )
        self.assert_json_error(result, "No such topic 'abc'")


class FixUnreadTests(ZulipTestCase):
    def test_fix_unreads(self) -> None:
        user = self.example_user("hamlet")
        othello = self.example_user("othello")
        realm = get_realm("zulip")

        def send_message(stream_name: str, topic_name: str) -> int:
            self.subscribe(othello, stream_name)
            msg_id = self.send_stream_message(othello, stream_name, topic_name=topic_name)
            um = UserMessage.objects.get(user_profile=user, message_id=msg_id)
            return um.id

        def assert_read(user_message_id: int) -> None:
            um = UserMessage.objects.get(id=user_message_id)
            self.assertTrue(um.flags.read)

        def assert_unread(user_message_id: int) -> None:
            um = UserMessage.objects.get(id=user_message_id)
            self.assertFalse(um.flags.read)

        def mute_stream(stream_name: str) -> None:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient
            subscription = Subscription.objects.get(
                user_profile=user,
                recipient=recipient,
            )
            subscription.is_muted = True
            subscription.save()

        def mute_topic(stream_name: str, topic_name: str) -> None:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient
            assert recipient is not None

            add_topic_mute(
                user_profile=user,
                stream_id=stream.id,
                recipient_id=recipient.id,
                topic_name=topic_name,
            )

        def force_unsubscribe(stream_name: str) -> None:
            """
            We don't want side effects here, since the eventual
            unsubscribe path may mark messages as read, defeating
            the test setup here.
            """
            sub = get_subscription(stream_name, user)
            sub.active = False
            sub.save()

        # The data setup here is kind of funny, because some of these
        # conditions should not actually happen in practice going forward,
        # but we may have had bad data from the past.

        mute_stream("Denmark")
        mute_topic("Verona", "muted_topic")

        um_normal_id = send_message("Verona", "normal")
        um_muted_topic_id = send_message("Verona", "muted_topic")
        um_muted_stream_id = send_message("Denmark", "whatever")

        self.subscribe(user, "temporary")
        um_unsubscribed_id = send_message("temporary", "whatever")
        force_unsubscribe("temporary")

        # Verify the setup
        assert_unread(um_normal_id)
        assert_unread(um_muted_topic_id)
        assert_unread(um_muted_stream_id)
        assert_unread(um_unsubscribed_id)

        # fix unsubscribed
        with connection.cursor() as cursor, self.assertLogs(
            "zulip.fix_unreads", "INFO"
        ) as info_logs:
            fix_unsubscribed(cursor, user)

        self.assertEqual(info_logs.output[0], "INFO:zulip.fix_unreads:get recipients")
        self.assertTrue("INFO:zulip.fix_unreads:[" in info_logs.output[1])
        self.assertTrue("INFO:zulip.fix_unreads:elapsed time:" in info_logs.output[2])
        self.assertEqual(
            info_logs.output[3],
            "INFO:zulip.fix_unreads:finding unread messages for non-active streams",
        )
        self.assertEqual(info_logs.output[4], "INFO:zulip.fix_unreads:rows found: 1")
        self.assertTrue("INFO:zulip.fix_unreads:elapsed time:" in info_logs.output[5])
        self.assertEqual(
            info_logs.output[6],
            "INFO:zulip.fix_unreads:fixing unread messages for non-active streams",
        )
        self.assertTrue("INFO:zulip.fix_unreads:elapsed time:" in info_logs.output[7])

        # Muted messages don't change.
        assert_unread(um_muted_topic_id)
        assert_unread(um_muted_stream_id)
        assert_unread(um_normal_id)

        # The unsubscribed entry should change.
        assert_read(um_unsubscribed_id)

        with self.assertLogs("zulip.fix_unreads", "INFO") as info_logs:
            # test idempotency
            fix(user)

        self.assertEqual(info_logs.output[0], f"INFO:zulip.fix_unreads:\n---\nFixing {user.id}:")
        self.assertEqual(info_logs.output[1], "INFO:zulip.fix_unreads:get recipients")
        self.assertTrue("INFO:zulip.fix_unreads:[" in info_logs.output[2])
        self.assertTrue("INFO:zulip.fix_unreads:elapsed time:" in info_logs.output[3])
        self.assertEqual(
            info_logs.output[4],
            "INFO:zulip.fix_unreads:finding unread messages for non-active streams",
        )
        self.assertEqual(info_logs.output[5], "INFO:zulip.fix_unreads:rows found: 0")
        self.assertTrue("INFO:zulip.fix_unreads:elapsed time:" in info_logs.output[6])

        assert_unread(um_normal_id)
        assert_unread(um_muted_topic_id)
        assert_unread(um_muted_stream_id)
        assert_read(um_unsubscribed_id)


class PushNotificationMarkReadFlowsTest(ZulipTestCase):
    def get_mobile_push_notification_ids(self, user_profile: UserProfile) -> List[int]:
        return list(
            UserMessage.objects.filter(
                user_profile=user_profile,
            )
            .extra(
                where=[UserMessage.where_active_push_notification()],
            )
            .order_by("message_id")
            .values_list("message_id", flat=True)
        )

    @mock.patch("zerver.lib.push_notifications.push_notifications_enabled", return_value=True)
    def test_track_active_mobile_push_notifications(
        self, mock_push_notifications: mock.MagicMock
    ) -> None:
        mock_push_notifications.return_value = True
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        stream = self.subscribe(user_profile, "test_stream")
        self.subscribe(cordelia, "test_stream")
        second_stream = self.subscribe(user_profile, "second_stream")
        self.subscribe(cordelia, "second_stream")

        property_name = "push_notifications"
        result = self.api_post(
            user_profile,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": True, "stream_id": stream.id}]
                ).decode()
            },
        )
        result = self.api_post(
            user_profile,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": True, "stream_id": second_stream.id}]
                ).decode()
            },
        )
        self.assert_json_success(result)
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile), [])

        message_id = self.send_stream_message(cordelia, "test_stream", "hello", "test_topic")
        second_message_id = self.send_stream_message(
            cordelia, "test_stream", "hello", "other_topic"
        )
        third_message_id = self.send_stream_message(
            cordelia, "second_stream", "hello", "test_topic"
        )

        self.assertEqual(
            self.get_mobile_push_notification_ids(user_profile),
            [message_id, second_message_id, third_message_id],
        )

        result = self.client_post(
            "/json/mark_topic_as_read",
            {
                "stream_id": str(stream.id),
                "topic_name": "test_topic",
            },
        )

        self.assert_json_success(result)
        self.assertEqual(
            self.get_mobile_push_notification_ids(user_profile),
            [second_message_id, third_message_id],
        )

        result = self.client_post(
            "/json/mark_stream_as_read",
            {
                "stream_id": str(stream.id),
            },
        )
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile), [third_message_id])

        fourth_message_id = self.send_stream_message(
            self.example_user("cordelia"), "test_stream", "hello", "test_topic"
        )
        self.assertEqual(
            self.get_mobile_push_notification_ids(user_profile),
            [third_message_id, fourth_message_id],
        )

        with timeout_mock("zerver.views.message_flags"):
            result = self.client_post("/json/mark_all_as_read", {})
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile), [])
        mock_push_notifications.assert_called()


class MarkAllAsReadEndpointTest(ZulipTestCase):
    def test_mark_all_as_read_endpoint(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.subscribe(hamlet, "Denmark")

        for i in range(0, 4):
            self.send_stream_message(othello, "Verona", "test")
            self.send_personal_message(othello, hamlet, "test")

        unread_count = (
            UserMessage.objects.filter(user_profile=hamlet)
            .extra(where=[UserMessage.where_unread()])
            .count()
        )
        self.assertNotEqual(unread_count, 0)
        with timeout_mock("zerver.views.message_flags"):
            result = self.client_post("/json/mark_all_as_read", {})
        self.assert_json_success(result)

        new_unread_count = (
            UserMessage.objects.filter(user_profile=hamlet)
            .extra(where=[UserMessage.where_unread()])
            .count()
        )
        self.assertEqual(new_unread_count, 0)

    def test_mark_all_as_read_timeout_response(self) -> None:
        self.login("hamlet")
        with mock.patch("zerver.views.message_flags.timeout", side_effect=TimeoutExpiredError):
            result = self.client_post("/json/mark_all_as_read", {})
            self.assertEqual(result.status_code, 200)

            result_dict = orjson.loads(result.content)
            self.assertEqual(
                result_dict, {"result": "partially_completed", "msg": "", "code": "REQUEST_TIMEOUT"}
            )


class GetUnreadMsgsTest(ZulipTestCase):
    def mute_stream(self, user_profile: UserProfile, stream: Stream) -> None:
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscription = Subscription.objects.get(
            user_profile=user_profile,
            recipient=recipient,
        )
        subscription.is_muted = True
        subscription.save()

    def mute_topic(self, user_profile: UserProfile, stream_name: str, topic_name: str) -> None:
        realm = user_profile.realm
        stream = get_stream(stream_name, realm)
        recipient = stream.recipient
        assert recipient is not None

        add_topic_mute(
            user_profile=user_profile,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=topic_name,
        )

    def test_raw_unread_stream(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        for stream_name in ["social", "devel", "test here"]:
            self.subscribe(hamlet, stream_name)
            self.subscribe(cordelia, stream_name)

        all_message_ids: Set[int] = set()
        message_ids = {}

        tups = [
            ("social", "lunch"),
            ("test here", "bla"),
            ("devel", "python"),
            ("devel", "ruby"),
        ]

        for stream_name, topic_name in tups:
            message_ids[topic_name] = [
                self.send_stream_message(
                    sender=cordelia,
                    stream_name=stream_name,
                    topic_name=topic_name,
                )
                for i in range(3)
            ]
            all_message_ids |= set(message_ids[topic_name])

        self.assert_length(all_message_ids, 12)  # sanity check on test setup

        self.mute_stream(
            user_profile=hamlet,
            stream=get_stream("test here", realm),
        )

        self.mute_topic(
            user_profile=hamlet,
            stream_name="devel",
            topic_name="ruby",
        )

        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        stream_dict = raw_unread_data["stream_dict"]

        self.assertEqual(
            set(stream_dict.keys()),
            all_message_ids,
        )

        self.assertEqual(
            raw_unread_data["unmuted_stream_msgs"],
            set(message_ids["python"]) | set(message_ids["lunch"]),
        )

        self.assertEqual(
            stream_dict[message_ids["lunch"][0]],
            dict(
                stream_id=get_stream("social", realm).id,
                topic="lunch",
            ),
        )

    def test_raw_unread_huddle(self) -> None:
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        prospero = self.example_user("prospero")

        huddle1_message_ids = [
            self.send_huddle_message(
                cordelia,
                [hamlet, othello],
            )
            for i in range(3)
        ]

        huddle2_message_ids = [
            self.send_huddle_message(
                cordelia,
                [hamlet, prospero],
            )
            for i in range(3)
        ]

        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        huddle_dict = raw_unread_data["huddle_dict"]

        self.assertEqual(
            set(huddle_dict.keys()),
            set(huddle1_message_ids) | set(huddle2_message_ids),
        )

        huddle_string = ",".join(str(uid) for uid in sorted([cordelia.id, hamlet.id, othello.id]))

        self.assertEqual(
            huddle_dict[huddle1_message_ids[0]],
            dict(user_ids_string=huddle_string),
        )

    def test_raw_unread_personal(self) -> None:
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")

        cordelia_pm_message_ids = [self.send_personal_message(cordelia, hamlet) for i in range(3)]

        othello_pm_message_ids = [self.send_personal_message(othello, hamlet) for i in range(3)]

        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        pm_dict = raw_unread_data["pm_dict"]

        self.assertEqual(
            set(pm_dict.keys()),
            set(cordelia_pm_message_ids) | set(othello_pm_message_ids),
        )

        self.assertEqual(
            pm_dict[cordelia_pm_message_ids[0]],
            dict(other_user_id=cordelia.id),
        )

    def test_raw_unread_personal_from_self(self) -> None:
        hamlet = self.example_user("hamlet")

        def send_unread_pm(other_user: UserProfile) -> Message:
            # It is rare to send a message from Hamlet to Othello
            # (or any other user) and have it be unread for
            # Hamlet himself, but that is actually normal
            # behavior for most API clients.
            message_id = self.send_personal_message(
                from_user=hamlet,
                to_user=other_user,
                sending_client_name="some_api_program",
            )

            # Check our test setup is correct--the message should
            # not have looked like it was sent by a human.
            message = Message.objects.get(id=message_id)
            self.assertFalse(message.sent_by_human())

            # And since it was not sent by a human, it should not
            # be read, not even by the sender (Hamlet).
            um = UserMessage.objects.get(
                user_profile_id=hamlet.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)

            return message

        othello = self.example_user("othello")
        othello_msg = send_unread_pm(other_user=othello)

        # And now check the unread data structure...
        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        pm_dict = raw_unread_data["pm_dict"]

        self.assertEqual(set(pm_dict.keys()), {othello_msg.id})

        self.assertEqual(
            pm_dict[othello_msg.id],
            dict(other_user_id=othello.id),
        )

        cordelia = self.example_user("cordelia")
        cordelia_msg = send_unread_pm(other_user=cordelia)

        apply_unread_message_event(
            user_profile=hamlet,
            state=raw_unread_data,
            message=MessageDict.wide_dict(cordelia_msg),
            flags=[],
        )
        self.assertEqual(
            set(pm_dict.keys()),
            {othello_msg.id, cordelia_msg.id},
        )

        self.assertEqual(
            pm_dict[cordelia_msg.id],
            dict(other_user_id=cordelia.id),
        )

        # Send a message to ourself.
        hamlet_msg = send_unread_pm(other_user=hamlet)
        apply_unread_message_event(
            user_profile=hamlet,
            state=raw_unread_data,
            message=MessageDict.wide_dict(hamlet_msg),
            flags=[],
        )
        self.assertEqual(
            set(pm_dict.keys()),
            {othello_msg.id, cordelia_msg.id, hamlet_msg.id},
        )

        self.assertEqual(
            pm_dict[hamlet_msg.id],
            dict(other_user_id=hamlet.id),
        )

        # Call get_raw_unread_data again.
        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )
        pm_dict = raw_unread_data["pm_dict"]

        self.assertEqual(
            set(pm_dict.keys()),
            {othello_msg.id, cordelia_msg.id, hamlet_msg.id},
        )

        self.assertEqual(
            pm_dict[hamlet_msg.id],
            dict(other_user_id=hamlet.id),
        )

    def test_unread_msgs(self) -> None:
        sender = self.example_user("cordelia")
        sender_id = sender.id
        user_profile = self.example_user("hamlet")
        othello = self.example_user("othello")

        self.subscribe(sender, "Denmark")

        pm1_message_id = self.send_personal_message(sender, user_profile, "hello1")
        pm2_message_id = self.send_personal_message(sender, user_profile, "hello2")

        muted_stream = self.subscribe(user_profile, "Muted stream")
        self.subscribe(sender, muted_stream.name)
        self.mute_stream(user_profile, muted_stream)
        self.mute_topic(user_profile, "Denmark", "muted-topic")

        stream_message_id = self.send_stream_message(sender, "Denmark", "hello")
        muted_stream_message_id = self.send_stream_message(sender, "Muted stream", "hello")
        muted_topic_message_id = self.send_stream_message(
            sender,
            "Denmark",
            topic_name="muted-topic",
            content="hello",
        )

        huddle_message_id = self.send_huddle_message(
            sender,
            [user_profile, othello],
            "hello3",
        )

        def get_unread_data() -> UnreadMessagesResult:
            raw_unread_data = get_raw_unread_data(user_profile)
            aggregated_data = aggregate_unread_data(raw_unread_data)
            return aggregated_data

        with mock.patch("zerver.lib.message.MAX_UNREAD_MESSAGES", 4):
            result = get_unread_data()
            self.assertEqual(result["count"], 2)
            self.assertTrue(result["old_unreads_missing"])

        result = get_unread_data()

        # The count here reflects the count of unread messages that we will
        # report to users in the bankruptcy dialog, and for now it excludes unread messages
        # from muted streams, but it doesn't exclude unread messages from muted topics yet.
        self.assertEqual(result["count"], 4)
        self.assertFalse(result["old_unreads_missing"])

        unread_pm = result["pms"][0]
        self.assertEqual(unread_pm["sender_id"], sender_id)
        self.assertEqual(unread_pm["unread_message_ids"], [pm1_message_id, pm2_message_id])

        unread_stream = result["streams"][0]
        self.assertEqual(unread_stream["stream_id"], get_stream("Denmark", user_profile.realm).id)
        self.assertEqual(unread_stream["topic"], "muted-topic")
        self.assertEqual(unread_stream["unread_message_ids"], [muted_topic_message_id])

        unread_stream = result["streams"][1]
        self.assertEqual(unread_stream["stream_id"], get_stream("Denmark", user_profile.realm).id)
        self.assertEqual(unread_stream["topic"], "test")
        self.assertEqual(unread_stream["unread_message_ids"], [stream_message_id])

        unread_stream = result["streams"][2]
        self.assertEqual(
            unread_stream["stream_id"], get_stream("Muted stream", user_profile.realm).id
        )
        self.assertEqual(unread_stream["topic"], "test")
        self.assertEqual(unread_stream["unread_message_ids"], [muted_stream_message_id])

        huddle_string = ",".join(
            str(uid) for uid in sorted([sender_id, user_profile.id, othello.id])
        )

        unread_huddle = result["huddles"][0]
        self.assertEqual(unread_huddle["user_ids_string"], huddle_string)
        self.assertEqual(unread_huddle["unread_message_ids"], [huddle_message_id])

        self.assertEqual(result["mentions"], [])

        um = UserMessage.objects.get(
            user_profile_id=user_profile.id,
            message_id=stream_message_id,
        )
        um.flags |= UserMessage.flags.mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [stream_message_id])

        um.flags = UserMessage.flags.has_alert_word
        um.save()
        result = get_unread_data()
        # TODO: This should change when we make alert words work better.
        self.assertEqual(result["mentions"], [])

        um.flags = UserMessage.flags.wildcard_mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [stream_message_id])

        um.flags = 0
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [])

        # Test with a muted stream
        um = UserMessage.objects.get(
            user_profile_id=user_profile.id,
            message_id=muted_stream_message_id,
        )
        um.flags = UserMessage.flags.mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [muted_stream_message_id])

        um.flags = UserMessage.flags.has_alert_word
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [])

        um.flags = UserMessage.flags.wildcard_mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [])

        um.flags = 0
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [])

        # Test with a muted topic
        um = UserMessage.objects.get(
            user_profile_id=user_profile.id,
            message_id=muted_topic_message_id,
        )
        um.flags = UserMessage.flags.mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [muted_topic_message_id])

        um.flags = UserMessage.flags.has_alert_word
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [])

        um.flags = UserMessage.flags.wildcard_mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [])

        um.flags = 0
        um.save()
        result = get_unread_data()
        self.assertEqual(result["mentions"], [])


class MessageAccessTests(ZulipTestCase):
    def test_update_invalid_flags(self) -> None:
        message = self.send_personal_message(
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            "hello",
        )

        self.login("hamlet")
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps([message]).decode(), "op": "add", "flag": "invalid"},
        )
        self.assert_json_error(result, "Invalid flag: 'invalid'")

        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps([message]).decode(), "op": "add", "flag": "is_private"},
        )
        self.assert_json_error(result, "Invalid flag: 'is_private'")

        result = self.client_post(
            "/json/messages/flags",
            {
                "messages": orjson.dumps([message]).decode(),
                "op": "add",
                "flag": "active_mobile_push_notification",
            },
        )
        self.assert_json_error(result, "Invalid flag: 'active_mobile_push_notification'")

        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps([message]).decode(), "op": "add", "flag": "mentioned"},
        )
        self.assert_json_error(result, "Flag not editable: 'mentioned'")

        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps([message]).decode(), "op": "bogus", "flag": "starred"},
        )
        self.assert_json_error(result, "Invalid message flag operation: 'bogus'")

    def change_star(
        self, messages: List[int], add: bool = True, **kwargs: Any
    ) -> "TestHttpResponse":
        return self.client_post(
            "/json/messages/flags",
            {
                "messages": orjson.dumps(messages).decode(),
                "op": "add" if add else "remove",
                "flag": "starred",
            },
            **kwargs,
        )

    def test_change_star(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login("hamlet")
        message_ids = [
            self.send_personal_message(
                self.example_user("hamlet"), self.example_user("hamlet"), "test"
            )
        ]

        # Star a message.
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_messages():
            if msg["id"] in message_ids:
                check_flags(msg["flags"], {"starred"})
            else:
                check_flags(msg["flags"], {"read"})

        # Remove the stars.
        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        for msg in self.get_messages():
            if msg["id"] in message_ids:
                check_flags(msg["flags"], set())

    def test_change_collapsed_public_stream_historical(self) -> None:
        hamlet = self.example_user("hamlet")
        stream_name = "new_stream"
        self.subscribe(hamlet, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(hamlet, stream_name, "test")

        # Now login as another user who wasn't on that stream
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        result = self.client_post(
            "/json/messages/flags",
            dict(messages=orjson.dumps([message_id]).decode(), op="add", flag="collapsed"),
        )
        self.assert_json_success(result)

        um = UserMessage.objects.get(user_profile_id=cordelia.id, message_id=message_id)
        self.assertEqual(um.flags_list(), ["read", "collapsed", "historical"])

    def test_change_star_public_stream_historical(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        stream_name = "new_stream"
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login("hamlet")
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]
        # Send a second message so we can verify it isn't modified
        other_message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test_unused"),
        ]
        received_message_ids = [
            self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                "test_received",
            ),
        ]

        # Now login as another user who wasn't on that stream
        self.login("cordelia")
        # Send a message to yourself to make sure we have at least one with the read flag
        sent_message_ids = [
            self.send_personal_message(
                self.example_user("cordelia"),
                self.example_user("cordelia"),
                "test_read_message",
            ),
        ]
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(sent_message_ids).decode(), "op": "add", "flag": "read"},
        )

        # Confirm that one can change the historical flag now
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_messages():
            if msg["id"] in message_ids:
                check_flags(msg["flags"], {"starred", "historical", "read"})
            elif msg["id"] in received_message_ids:
                check_flags(msg["flags"], set())
            else:
                check_flags(msg["flags"], {"read"})
            self.assertNotIn(msg["id"], other_message_ids)

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # But it still doesn't work if you're in another realm
        user = self.mit_user("sipbtest")
        self.login_user(user)
        result = self.change_star(message_ids, subdomain="zephyr")
        self.assert_json_error(result, "Invalid message(s)")

    def test_change_star_private_message_security(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login("hamlet")
        message_ids = [
            self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("hamlet"),
                "test",
            ),
        ]

        # Starring private messages you didn't receive fails.
        self.login("cordelia")
        result = self.change_star(message_ids)
        self.assert_json_error(result, "Invalid message(s)")

    def test_change_star_private_stream_security(self) -> None:
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True)
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login("hamlet")
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]

        # Starring private stream messages you received works
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        # Starring private stream messages you didn't receive fails.
        self.login("cordelia")
        with transaction.atomic():
            result = self.change_star(message_ids)
        self.assert_json_error(result, "Invalid message(s)")

        stream_name = "private_stream_2"
        self.make_stream(stream_name, invite_only=True, history_public_to_subscribers=True)
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login("hamlet")
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]

        # With stream.history_public_to_subscribers = True, you still
        # can't see it if you didn't receive the message and are
        # not subscribed.
        self.login("cordelia")
        with transaction.atomic():
            result = self.change_star(message_ids)
        self.assert_json_error(result, "Invalid message(s)")

        # But if you subscribe, then you can star the message
        self.subscribe(self.example_user("cordelia"), stream_name)
        result = self.change_star(message_ids)
        self.assert_json_success(result)

    def test_new_message(self) -> None:
        """
        New messages aren't starred.
        """
        sender = self.example_user("hamlet")
        self.login_user(sender)
        content = "Test message for star"
        self.send_stream_message(sender, "Verona", content=content)

        sent_message = (
            UserMessage.objects.filter(
                user_profile=self.example_user("hamlet"),
            )
            .order_by("id")
            .reverse()[0]
        )
        self.assertEqual(sent_message.message.content, content)
        self.assertFalse(sent_message.flags.starred)

    def test_change_star_public_stream_security_for_guest_user(self) -> None:
        # Guest user can't access(star) unsubscribed public stream messages
        normal_user = self.example_user("hamlet")
        stream_name = "public_stream"
        self.make_stream(stream_name)
        self.subscribe(normal_user, stream_name)
        self.login_user(normal_user)

        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 1"),
        ]

        guest_user = self.example_user("polonius")
        self.login_user(guest_user)
        with transaction.atomic():
            result = self.change_star(message_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Subscribed guest users can access public stream messages sent before they join
        self.subscribe(guest_user, stream_name)
        result = self.change_star(message_id)
        self.assert_json_success(result)

        # And messages sent after they join
        self.login_user(normal_user)
        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 2"),
        ]
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_success(result)

    def test_change_star_private_stream_security_for_guest_user(self) -> None:
        # Guest users can't access(star) unsubscribed private stream messages
        normal_user = self.example_user("hamlet")
        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True)
        self.subscribe(normal_user, stream_name)
        self.login_user(normal_user)

        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 1"),
        ]

        guest_user = self.example_user("polonius")
        self.login_user(guest_user)
        with transaction.atomic():
            result = self.change_star(message_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Guest user can't access messages of subscribed private streams if
        # history is not public to subscribers
        self.subscribe(guest_user, stream_name)
        with transaction.atomic():
            result = self.change_star(message_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Guest user can access messages of subscribed private streams if
        # history is public to subscribers
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=guest_user,
        )
        result = self.change_star(message_id)
        self.assert_json_success(result)

        # With history not public to subscribers, they can still see new messages
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=False,
            is_web_public=False,
            acting_user=guest_user,
        )
        self.login_user(normal_user)
        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 2"),
        ]
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_success(result)

    def test_bulk_access_messages_private_stream(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        stream_name = "private_stream"
        stream = self.make_stream(
            stream_name, invite_only=True, history_public_to_subscribers=False
        )

        self.subscribe(user, stream_name)
        # Send a message before subscribing a new user to stream
        message_one_id = self.send_stream_message(user, stream_name, "Message one")

        later_subscribed_user = self.example_user("cordelia")
        # Subscribe a user to private-protected history stream
        self.subscribe(later_subscribed_user, stream_name)

        # Send a message after subscribing a new user to stream
        message_two_id = self.send_stream_message(user, stream_name, "Message two")

        message_ids = [message_one_id, message_two_id]
        messages = [
            Message.objects.select_related().get(id=message_id) for message_id in message_ids
        ]

        with self.assert_database_query_count(2):
            filtered_messages = bulk_access_messages(later_subscribed_user, messages, stream=stream)

        # Message sent before subscribing wouldn't be accessible by later
        # subscribed user as stream has protected history
        self.assert_length(filtered_messages, 1)
        self.assertEqual(filtered_messages[0].id, message_two_id)

        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=self.example_user("cordelia"),
        )

        with self.assert_database_query_count(2):
            filtered_messages = bulk_access_messages(later_subscribed_user, messages, stream=stream)

        # Message sent before subscribing are accessible by 8user as stream
        # don't have protected history
        self.assert_length(filtered_messages, 2)

        # Testing messages accessibility for an unsubscribed user
        unsubscribed_user = self.example_user("ZOE")

        with self.assert_database_query_count(2):
            filtered_messages = bulk_access_messages(unsubscribed_user, messages, stream=stream)

        self.assert_length(filtered_messages, 0)

        # Verify an exception is thrown if called where the passed
        # stream not matching the messages.
        with self.assertRaises(AssertionError):
            bulk_access_messages(
                unsubscribed_user, messages, stream=get_stream("Denmark", unsubscribed_user.realm)
            )

    def test_bulk_access_messages_public_stream(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # Testing messages accessibility including a public stream message
        stream_name = "public_stream"
        stream = self.subscribe(user, stream_name)
        message_one_id = self.send_stream_message(user, stream_name, "Message one")

        later_subscribed_user = self.example_user("cordelia")
        self.subscribe(later_subscribed_user, stream_name)

        # Send a message after subscribing a new user to stream
        message_two_id = self.send_stream_message(user, stream_name, "Message two")

        message_ids = [message_one_id, message_two_id]
        messages = [
            Message.objects.select_related().get(id=message_id) for message_id in message_ids
        ]

        # All public stream messages are always accessible
        with self.assert_database_query_count(2):
            filtered_messages = bulk_access_messages(later_subscribed_user, messages, stream=stream)
        self.assert_length(filtered_messages, 2)

        unsubscribed_user = self.example_user("ZOE")
        with self.assert_database_query_count(2):
            filtered_messages = bulk_access_messages(unsubscribed_user, messages, stream=stream)

        self.assert_length(filtered_messages, 2)


class PersonalMessagesFlagTest(ZulipTestCase):
    def test_is_private_flag_not_leaked(self) -> None:
        """
        Make sure `is_private` flag is not leaked to the API.
        """
        self.login("hamlet")
        self.send_personal_message(
            self.example_user("hamlet"), self.example_user("cordelia"), "test"
        )

        for msg in self.get_messages():
            self.assertNotIn("is_private", msg["flags"])


class MarkUnreadTest(ZulipTestCase):
    def mute_stream(self, stream_name: str, user: UserProfile) -> None:
        realm = get_realm("zulip")
        stream = get_stream(stream_name, realm)
        recipient = stream.recipient
        subscription = Subscription.objects.get(
            user_profile=user,
            recipient=recipient,
        )
        subscription.is_muted = True
        subscription.save()

    def test_missing_usermessage_record(self) -> None:
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        stream_name = "Some new stream"
        self.subscribe(cordelia, stream_name)

        message_id1 = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
            topic_name="lunch",
            content="whatever",
        )

        self.subscribe(othello, stream_name)

        raw_unread_data = get_raw_unread_data(
            user_profile=othello,
        )

        self.assertEqual(raw_unread_data["stream_dict"], {})

        message_id2 = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
            topic_name="lunch",
            content="whatever",
        )

        raw_unread_data = get_raw_unread_data(
            user_profile=othello,
        )

        self.assertEqual(raw_unread_data["stream_dict"].keys(), {message_id2})

        do_update_message_flags(othello, "remove", "read", [message_id1])

        raw_unread_data = get_raw_unread_data(
            user_profile=othello,
        )

        self.assertEqual(raw_unread_data["stream_dict"].keys(), {message_id1, message_id2})

    def test_format_unread_message_details(self) -> None:
        user = self.example_user("cordelia")
        message_id = 999

        # send message to self
        pm_dict = {
            message_id: RawUnreadPrivateMessageDict(other_user_id=user.id),
        }

        raw_unread_data = RawUnreadMessagesResult(
            pm_dict=pm_dict,
            stream_dict={},
            huddle_dict={},
            mentions=set(),
            muted_stream_ids=[],
            unmuted_stream_msgs=set(),
            old_unreads_missing=False,
        )

        message_details = format_unread_message_details(user.id, raw_unread_data)
        self.assertEqual(
            message_details,
            {
                str(message_id): dict(type="private", user_ids=[]),
            },
        )

    def test_add_message_to_unread_msgs(self) -> None:
        user = self.example_user("cordelia")
        message_id = 999

        raw_unread_data = RawUnreadMessagesResult(
            pm_dict={},
            stream_dict={},
            huddle_dict={},
            mentions=set(),
            muted_stream_ids=[],
            unmuted_stream_msgs=set(),
            old_unreads_missing=False,
        )

        # message to self
        message_details = MessageDetailsDict(type="private", user_ids=[])
        add_message_to_unread_msgs(user.id, raw_unread_data, message_id, message_details)
        self.assertEqual(
            raw_unread_data["pm_dict"],
            {message_id: RawUnreadPrivateMessageDict(other_user_id=user.id)},
        )

    def test_stream_messages_unread(self) -> None:
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        stream_name = "Denmark"
        stream = self.subscribe(receiver, stream_name)
        self.subscribe(sender, stream_name)
        topic_name = "test"
        message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
            )
            for i in range(4)
        ]
        self.login("hamlet")
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        messages_to_unread = message_ids[2:]
        messages_still_read = message_ids[:2]

        params = {
            "messages": orjson.dumps(messages_to_unread).decode(),
            "op": "remove",
            "flag": "read",
        }

        events: List[Mapping[str, Any]] = []

        # Use the tornado_redirected_to_list context manager to capture
        # events.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.api_post(receiver, "/api/v1/messages/flags", params)

        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], messages_to_unread)
        unread_message_ids = {str(message_id) for message_id in messages_to_unread}
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)
        for message_id in event["message_details"]:
            self.assertEqual(
                event["message_details"][message_id],
                dict(
                    type="stream",
                    topic="test",
                    unmuted_stream_msg=True,
                    stream_id=stream.id,
                ),
            )

        for message_id in messages_to_unread:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        for message_id in messages_still_read:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

    def test_stream_messages_unread_muted(self) -> None:
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        stream_name = "Denmark"
        stream = self.subscribe(receiver, stream_name)
        self.subscribe(sender, stream_name)
        topic_name = "test"
        message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
            )
            for i in range(4)
        ]
        self.mute_stream(stream_name, receiver)
        self.login("hamlet")
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        messages_to_unread = message_ids[2:]
        messages_still_read = message_ids[:2]

        params = {
            "messages": orjson.dumps(messages_to_unread).decode(),
            "op": "remove",
            "flag": "read",
        }

        events: List[Mapping[str, Any]] = []

        # Use the tornado_redirected_to_list context manager to capture
        # events.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.api_post(receiver, "/api/v1/messages/flags", params)

        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], messages_to_unread)
        unread_message_ids = {str(message_id) for message_id in messages_to_unread}
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)
        for message_id in event["message_details"]:
            self.assertEqual(
                event["message_details"][message_id],
                dict(
                    type="stream",
                    topic="test",
                    unmuted_stream_msg=False,
                    stream_id=stream.id,
                ),
            )

        for message_id in messages_to_unread:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        for message_id in messages_still_read:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

    def test_stream_messages_unread_mention(self) -> None:
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        stream_name = "Denmark"
        stream = self.subscribe(receiver, stream_name)
        self.subscribe(sender, stream_name)
        topic_name = "test"
        message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
                content="@**King Hamlet**",
            )
            for i in range(4)
        ]
        self.login("hamlet")
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        messages_to_unread = message_ids[2:]
        messages_still_read = message_ids[:2]

        params = {
            "messages": orjson.dumps(messages_to_unread).decode(),
            "op": "remove",
            "flag": "read",
        }

        events: List[Mapping[str, Any]] = []

        # Use the tornado_redirected_to_list context manager to capture
        # events.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.api_post(receiver, "/api/v1/messages/flags", params)

        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], messages_to_unread)
        unread_message_ids = {str(message_id) for message_id in messages_to_unread}
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)
        for message_id in event["message_details"]:
            self.assertEqual(
                event["message_details"][message_id],
                dict(
                    type="stream",
                    mentioned=True,
                    topic="test",
                    unmuted_stream_msg=True,
                    stream_id=stream.id,
                ),
            )

        for message_id in messages_to_unread:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        for message_id in messages_still_read:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

    def test_unsubscribed_stream_messages_unread(self) -> None:
        """An extended test verifying that the `update_message_flags` endpoint
        correctly preserves the invariant that messages cannot be
        marked unread in streams a user is not currently subscribed
        to.
        """
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        stream_name = "Test stream"
        topic_name = "test"
        self.subscribe(sender, stream_name)
        before_subscribe_stream_message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
            )
            for i in range(2)
        ]

        self.subscribe(receiver, stream_name)
        subscribed_stream_message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
            )
            for i in range(2)
        ]
        stream_name = "Verona"
        sub = get_subscription(stream_name, receiver)
        self.assertTrue(sub.active)
        unsubscribed_stream_message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
            )
            for i in range(2)
        ]
        # Unsubscribing generates an event in the deferred_work queue
        # that marks the above messages as read.
        self.unsubscribe(receiver, stream_name)
        after_unsubscribe_stream_message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
            )
            for i in range(2)
        ]

        stream_name = "New-stream"
        self.subscribe(sender, stream_name)
        never_subscribed_stream_message_ids = [
            self.send_stream_message(
                sender=sender,
                stream_name=stream_name,
                topic_name=topic_name,
            )
            for i in range(2)
        ]

        message_ids = (
            subscribed_stream_message_ids
            + unsubscribed_stream_message_ids
            + after_unsubscribe_stream_message_ids
            + never_subscribed_stream_message_ids
        )
        # Before doing anything, verify the state of each message's flags.
        for message_id in subscribed_stream_message_ids + unsubscribed_stream_message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertEqual(um.flags.read, message_id in unsubscribed_stream_message_ids)
        for message_id in (
            before_subscribe_stream_message_ids
            + never_subscribed_stream_message_ids
            + after_unsubscribe_stream_message_ids
        ):
            self.assertFalse(
                UserMessage.objects.filter(
                    user_profile_id=receiver.id,
                    message_id=message_id,
                ).exists()
            )

        # First, try marking them all as unread; should be a noop. The
        # ones that already have UserMessage rows are already unread,
        # and the others don't have UserMessage rows and cannot be
        # marked as unread without first subscribing.
        events: List[Mapping[str, Any]] = []
        with self.tornado_redirected_to_list(events, expected_num_events=0):
            result = self.client_post(
                "/json/messages/flags",
                {"messages": orjson.dumps(message_ids).decode(), "op": "remove", "flag": "read"},
            )
        for message_id in subscribed_stream_message_ids + unsubscribed_stream_message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertEqual(um.flags.read, message_id in unsubscribed_stream_message_ids)
        for message_id in (
            never_subscribed_stream_message_ids + after_unsubscribe_stream_message_ids
        ):
            self.assertFalse(
                UserMessage.objects.filter(
                    user_profile_id=receiver.id,
                    message_id=message_id,
                ).exists()
            )

        # Now, explicitly mark them all as read. The messages which don't
        # have UserMessage rows will be ignored.
        message_ids = before_subscribe_stream_message_ids + message_ids
        self.login("hamlet")
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.client_post(
                "/json/messages/flags",
                {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
            )
        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], subscribed_stream_message_ids)

        for message_id in subscribed_stream_message_ids + unsubscribed_stream_message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        for message_id in (
            before_subscribe_stream_message_ids
            + never_subscribed_stream_message_ids
            + after_unsubscribe_stream_message_ids
        ):
            self.assertFalse(
                UserMessage.objects.filter(
                    user_profile_id=receiver.id,
                    message_id=message_id,
                ).exists()
            )

        # Now, request marking them all as unread. Since we haven't
        # resubscribed to any of the streams, we expect this to not
        # modify the messages in streams we're not subscribed to.
        #
        # This also create new 'historical' UserMessage rows for the
        # messages in subscribed streams that didn't have them
        # previously.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.client_post(
                "/json/messages/flags",
                {"messages": orjson.dumps(message_ids).decode(), "op": "remove", "flag": "read"},
            )
        event = events[0]["event"]
        self.assertEqual(
            event["messages"], before_subscribe_stream_message_ids + subscribed_stream_message_ids
        )
        unread_message_ids = {
            str(message_id)
            for message_id in before_subscribe_stream_message_ids + subscribed_stream_message_ids
        }
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)

        for message_id in before_subscribe_stream_message_ids + subscribed_stream_message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)

        for message_id in unsubscribed_stream_message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

        for message_id in (
            after_unsubscribe_stream_message_ids + never_subscribed_stream_message_ids
        ):
            self.assertFalse(
                UserMessage.objects.filter(
                    user_profile_id=receiver.id,
                    message_id=message_id,
                ).exists()
            )

    def test_pm_messages_unread(self) -> None:
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        message_ids = [
            self.send_personal_message(sender, receiver, content="Hello") for i in range(4)
        ]
        self.login("hamlet")
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        messages_to_unread = message_ids[2:]
        messages_still_read = message_ids[:2]

        params = {
            "messages": orjson.dumps(messages_to_unread).decode(),
            "op": "remove",
            "flag": "read",
        }

        events: List[Mapping[str, Any]] = []

        # Use the tornado_redirected_to_list context manager to capture
        # events.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.api_post(receiver, "/api/v1/messages/flags", params)

        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], messages_to_unread)
        unread_message_ids = {str(message_id) for message_id in messages_to_unread}
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)
        for message_id in event["message_details"]:
            self.assertEqual(
                event["message_details"][message_id],
                dict(
                    type="private",
                    user_ids=[sender.id],
                ),
            )

        for message_id in messages_to_unread:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        for message_id in messages_still_read:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

    def test_pm_messages_unread_mention(self) -> None:
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        stream_name = "Denmark"
        self.subscribe(receiver, stream_name)
        message_ids = [
            self.send_personal_message(sender, receiver, content="@**King Hamlet**")
            for i in range(4)
        ]
        self.login("hamlet")
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        messages_to_unread = message_ids[2:]
        messages_still_read = message_ids[:2]

        params = {
            "messages": orjson.dumps(messages_to_unread).decode(),
            "op": "remove",
            "flag": "read",
        }

        events: List[Mapping[str, Any]] = []

        # Use the tornado_redirected_to_list context manager to capture
        # events.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.api_post(receiver, "/api/v1/messages/flags", params)

        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], messages_to_unread)
        unread_message_ids = {str(message_id) for message_id in messages_to_unread}
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)
        for message_id in event["message_details"]:
            self.assertEqual(
                event["message_details"][message_id],
                dict(
                    type="private",
                    user_ids=[sender.id],
                    mentioned=True,
                ),
            )

        for message_id in messages_to_unread:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        for message_id in messages_still_read:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

    def test_huddle_messages_unread(self) -> None:
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        user1 = self.example_user("othello")
        message_ids = [
            # self.send_huddle_message(sender, receiver, content="Hello") for i in range(4)
            self.send_huddle_message(sender, [receiver, user1])
            for i in range(4)
        ]
        self.login("hamlet")
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        messages_to_unread = message_ids[2:]
        messages_still_read = message_ids[:2]

        params = {
            "messages": orjson.dumps(messages_to_unread).decode(),
            "op": "remove",
            "flag": "read",
        }

        events: List[Mapping[str, Any]] = []

        # Use the tornado_redirected_to_list context manager to capture
        # events.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.api_post(receiver, "/api/v1/messages/flags", params)

        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], messages_to_unread)
        unread_message_ids = {str(message_id) for message_id in messages_to_unread}
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)
        for message_id in event["message_details"]:
            self.assertNotIn("mentioned", event["message_details"][message_id])

        for message_id in messages_to_unread:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        for message_id in messages_still_read:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

    def test_huddle_messages_unread_mention(self) -> None:
        sender = self.example_user("cordelia")
        receiver = self.example_user("hamlet")
        user1 = self.example_user("othello")
        message_ids = [
            # self.send_huddle_message(sender, receiver, content="Hello") for i in range(4)
            self.send_huddle_message(
                from_user=sender, to_users=[receiver, user1], content="@**King Hamlet**"
            )
            for i in range(4)
        ]
        self.login("hamlet")
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        result = self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps(message_ids).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)
        for message_id in message_ids:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)
        messages_to_unread = message_ids[2:]
        messages_still_read = message_ids[:2]

        params = {
            "messages": orjson.dumps(messages_to_unread).decode(),
            "op": "remove",
            "flag": "read",
        }

        events: List[Mapping[str, Any]] = []

        # Use the tornado_redirected_to_list context manager to capture
        # events.
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            result = self.api_post(receiver, "/api/v1/messages/flags", params)

        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["messages"], messages_to_unread)
        unread_message_ids = {str(message_id) for message_id in messages_to_unread}
        self.assertSetEqual(set(event["message_details"].keys()), unread_message_ids)
        for message_id in event["message_details"]:
            self.assertEqual(event["message_details"][message_id]["mentioned"], True)

        for message_id in messages_to_unread:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)
        for message_id in messages_still_read:
            um = UserMessage.objects.get(
                user_profile_id=receiver.id,
                message_id=message_id,
            )
            self.assertTrue(um.flags.read)

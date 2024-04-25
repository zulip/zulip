import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Huddle
from zerver.models.recipients import get_huddle_hash


class TypingValidateOperatorTest(ZulipTestCase):
    def test_missing_parameter(self) -> None:
        """
        Sending typing notification without op parameter fails
        """
        sender = self.example_user("hamlet")
        params = dict(
            to=orjson.dumps([sender.id]).decode(),
        )
        result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_error(result, "Missing 'op' argument")

    def test_invalid_parameter_direct_message(self) -> None:
        """
        Sending typing notification with invalid value for op parameter fails
        """
        sender = self.example_user("hamlet")
        params = dict(
            to=orjson.dumps([sender.id]).decode(),
            op="foo",
        )
        result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_error(result, "Invalid op")

    def test_invalid_parameter_stream(self) -> None:
        sender = self.example_user("hamlet")

        result = self.api_post(
            sender, "/api/v1/typing", {"op": "foo", "stream_id": 1, "topic": "topic"}
        )
        self.assert_json_error(result, "Invalid op")


class TypingMessagetypeTest(ZulipTestCase):
    def test_invalid_type(self) -> None:
        sender = self.example_user("hamlet")
        params = dict(
            to=orjson.dumps([sender.id]).decode(),
            type="invalid",
            op="start",
        )
        result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_error(result, "Invalid type")


class TypingValidateToArgumentsTest(ZulipTestCase):
    def test_invalid_to_for_direct_messages(self) -> None:
        """
        Sending dms typing notifications without 'to' as a list fails.
        """
        sender = self.example_user("hamlet")
        result = self.api_post(sender, "/api/v1/typing", {"op": "start", "to": "2"})
        self.assert_json_error(result, "to is not a list")

    def test_invalid_user_id_for_direct_messages(self) -> None:
        """
        Sending dms typing notifications with invalid user_id fails.
        """
        sender = self.example_user("hamlet")
        invalid_user_ids = orjson.dumps([2, "a", 4]).decode()
        result = self.api_post(sender, "/api/v1/typing", {"op": "start", "to": invalid_user_ids})
        self.assert_json_error(result, "to[1] is not an integer")

    def test_empty_to_array_direct_messages(self) -> None:
        """
        Sending dms typing notification without recipient fails
        """
        sender = self.example_user("hamlet")
        result = self.api_post(sender, "/api/v1/typing", {"op": "start", "to": "[]"})
        self.assert_json_error(result, "Empty 'to' list")

    def test_missing_recipient(self) -> None:
        """
        Sending typing notification without recipient fails
        """
        sender = self.example_user("hamlet")
        result = self.api_post(sender, "/api/v1/typing", {"op": "start"})
        self.assert_json_error(result, "Missing 'to' argument")

    def test_bogus_user_id(self) -> None:
        """
        Sending typing notification to invalid recipient fails
        """
        sender = self.example_user("hamlet")
        invalid = "[9999999]"
        result = self.api_post(sender, "/api/v1/typing", {"op": "start", "to": invalid})
        self.assert_json_error(result, "Invalid user ID 9999999")


class TypingValidateStreamIdTopicArgumentsTest(ZulipTestCase):
    def test_missing_stream_id(self) -> None:
        """
        Sending stream typing notifications without 'stream_id' fails.
        """
        sender = self.example_user("hamlet")
        result = self.api_post(
            sender,
            "/api/v1/typing",
            {"type": "stream", "op": "start", "topic": "test"},
        )
        self.assert_json_error(result, "Missing 'stream_id' argument")

    def test_invalid_stream_id(self) -> None:
        """
        Sending stream typing notifications without 'stream_id' as an integer fails.
        """
        sender = self.example_user("hamlet")
        result = self.api_post(
            sender,
            "/api/v1/typing",
            {"type": "stream", "op": "start", "stream_id": "invalid", "topic": "test"},
        )
        self.assert_json_error(result, 'Argument "stream_id" is not valid JSON.')

    def test_includes_stream_id_but_not_topic(self) -> None:
        sender = self.example_user("hamlet")
        stream_id = self.get_stream_id("general")

        result = self.api_post(
            sender,
            "/api/v1/typing",
            {"type": "stream", "op": "start", "stream_id": str(stream_id)},
        )
        self.assert_json_error(result, "Missing topic")

    def test_stream_doesnt_exist(self) -> None:
        sender = self.example_user("hamlet")
        stream_id = self.INVALID_STREAM_ID
        topic_name = "some topic"

        result = self.api_post(
            sender,
            "/api/v1/typing",
            {
                "type": "stream",
                "op": "start",
                "stream_id": str(stream_id),
                "topic": topic_name,
            },
        )
        self.assert_json_error(result, "Invalid channel ID")


class TypingHappyPathTestDirectMessages(ZulipTestCase):
    def test_valid_type_and_op_parameters(self) -> None:
        operator_type = ["start", "stop"]
        sender = self.example_user("hamlet")
        recipient_user = self.example_user("othello")

        for operator in operator_type:
            params = dict(
                to=orjson.dumps([recipient_user.id]).decode(),
                op=operator,
                type="direct",
            )

            result = self.api_post(sender, "/api/v1/typing", params)
            self.assert_json_success(result)

    def test_start_to_single_recipient(self) -> None:
        sender = self.example_user("hamlet")
        recipient_user = self.example_user("othello")
        expected_recipients = {sender, recipient_user}
        expected_recipient_emails = {user.email for user in expected_recipients}
        expected_recipient_ids = {user.id for user in expected_recipients}

        params = dict(
            to=orjson.dumps([recipient_user.id]).decode(),
            op="start",
        )

        with self.assert_database_query_count(4):
            with self.capture_send_event_calls(expected_num_events=1) as events:
                result = self.api_post(sender, "/api/v1/typing", params)

        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_recipient_emails = {user["email"] for user in event["recipients"]}
        event_user_ids = set(events[0]["users"])
        event_recipient_user_ids = {user["user_id"] for user in event["recipients"]}

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event["sender"]["email"], sender.email)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event["type"], "typing")
        self.assertEqual(event["op"], "start")

    def test_start_to_multiple_recipients(self) -> None:
        sender = self.example_user("hamlet")
        recipient_users = [self.example_user("othello"), self.example_user("cordelia")]
        expected_recipients = set(recipient_users) | {sender}
        expected_recipient_emails = {user.email for user in expected_recipients}
        expected_recipient_ids = {user.id for user in expected_recipients}

        huddle_hash = get_huddle_hash(list(expected_recipient_ids))
        self.assertFalse(Huddle.objects.filter(huddle_hash=huddle_hash).exists())

        params = dict(
            to=orjson.dumps([user.id for user in recipient_users]).decode(),
            op="start",
        )

        with self.assert_database_query_count(5):
            with self.capture_send_event_calls(expected_num_events=1) as events:
                result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_success(result)
        self.assert_length(events, 1)

        # We should not be adding new Huddles just because
        # a user started typing in the compose box.  Let's
        # wait till they send an actual message.
        self.assertFalse(Huddle.objects.filter(huddle_hash=huddle_hash).exists())

        event = events[0]["event"]
        event_recipient_emails = {user["email"] for user in event["recipients"]}
        event_user_ids = set(events[0]["users"])
        event_recipient_user_ids = {user["user_id"] for user in event["recipients"]}

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event["sender"]["email"], sender.email)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event["type"], "typing")
        self.assertEqual(event["op"], "start")

    def test_start_to_self(self) -> None:
        """
        Sending typing notification to yourself (using user IDs)
        is successful.
        """
        user = self.example_user("hamlet")
        email = user.email
        expected_recipient_emails = {email}
        expected_recipient_ids = {user.id}
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.api_post(
                user,
                "/api/v1/typing",
                {
                    "to": orjson.dumps([user.id]).decode(),
                    "op": "start",
                },
            )
        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_recipient_emails = {user["email"] for user in event["recipients"]}
        event_user_ids = set(events[0]["users"])
        event_recipient_user_ids = {user["user_id"] for user in event["recipients"]}

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event["sender"]["email"], email)
        self.assertEqual(event["type"], "typing")
        self.assertEqual(event["op"], "start")

    def test_start_to_another_user(self) -> None:
        """
        Sending typing notification to another user
        is successful.
        """
        sender = self.example_user("hamlet")
        recipient = self.example_user("othello")
        expected_recipients = {sender, recipient}
        expected_recipient_emails = {user.email for user in expected_recipients}
        expected_recipient_ids = {user.id for user in expected_recipients}

        params = dict(
            to=orjson.dumps([recipient.id]).decode(),
            op="start",
        )

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.api_post(sender, "/api/v1/typing", params)

        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_recipient_emails = {user["email"] for user in event["recipients"]}
        event_user_ids = set(events[0]["users"])
        event_recipient_user_ids = {user["user_id"] for user in event["recipients"]}

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event["sender"]["email"], sender.email)
        self.assertEqual(event["type"], "typing")
        self.assertEqual(event["op"], "start")

    def test_stop_to_self(self) -> None:
        """
        Sending stopped typing notification to yourself
        is successful.
        """
        user = self.example_user("hamlet")
        email = user.email
        expected_recipient_emails = {email}
        expected_recipient_ids = {user.id}

        with self.capture_send_event_calls(expected_num_events=1) as events:
            params = dict(
                to=orjson.dumps([user.id]).decode(),
                op="stop",
            )
            result = self.api_post(user, "/api/v1/typing", params)

        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_recipient_emails = {user["email"] for user in event["recipients"]}
        event_user_ids = set(events[0]["users"])
        event_recipient_user_ids = {user["user_id"] for user in event["recipients"]}

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event["sender"]["email"], email)
        self.assertEqual(event["type"], "typing")
        self.assertEqual(event["op"], "stop")

    def test_stop_to_another_user(self) -> None:
        """
        Sending stopped typing notification to another user
        is successful.
        """
        sender = self.example_user("hamlet")
        recipient = self.example_user("othello")
        expected_recipients = {sender, recipient}
        expected_recipient_emails = {user.email for user in expected_recipients}
        expected_recipient_ids = {user.id for user in expected_recipients}

        with self.capture_send_event_calls(expected_num_events=1) as events:
            params = dict(
                to=orjson.dumps([recipient.id]).decode(),
                op="stop",
            )
            result = self.api_post(sender, "/api/v1/typing", params)

        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_recipient_emails = {user["email"] for user in event["recipients"]}
        event_user_ids = set(events[0]["users"])
        event_recipient_user_ids = {user["user_id"] for user in event["recipients"]}

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event["sender"]["email"], sender.email)
        self.assertEqual(event["type"], "typing")
        self.assertEqual(event["op"], "stop")


class TypingHappyPathTestStreams(ZulipTestCase):
    def test_valid_type_and_op_parameters(self) -> None:
        recipient_type_name = ["channel", "stream"]
        operator_type = ["start", "stop"]
        sender = self.example_user("hamlet")
        stream_name = self.get_streams(sender)[0]
        stream_id = self.get_stream_id(stream_name)
        topic_name = "Some topic"

        for recipient_type in recipient_type_name:
            for operator in operator_type:
                params = dict(
                    type=recipient_type,
                    op=operator,
                    stream_id=str(stream_id),
                    topic=topic_name,
                )

                result = self.api_post(sender, "/api/v1/typing", params)
                self.assert_json_success(result)

    def test_start(self) -> None:
        sender = self.example_user("hamlet")
        stream_name = self.get_streams(sender)[0]
        stream_id = self.get_stream_id(stream_name)
        topic_name = "Some topic"

        expected_user_ids = self.not_long_term_idle_subscriber_ids(stream_name, sender.realm)

        params = dict(
            type="stream",
            op="start",
            stream_id=str(stream_id),
            topic=topic_name,
        )

        with self.assert_database_query_count(6):
            with self.capture_send_event_calls(expected_num_events=1) as events:
                result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_user_ids = set(events[0]["users"])

        self.assertEqual(expected_user_ids, event_user_ids)
        self.assertEqual(sender.email, event["sender"]["email"])
        self.assertEqual(stream_id, event["stream_id"])
        self.assertEqual(topic_name, event["topic"])
        self.assertEqual("typing", event["type"])
        self.assertEqual("start", event["op"])

    def test_stop(self) -> None:
        sender = self.example_user("hamlet")
        stream_name = self.get_streams(sender)[0]
        stream_id = self.get_stream_id(stream_name)
        topic_name = "Some topic"

        expected_user_ids = self.not_long_term_idle_subscriber_ids(stream_name, sender.realm)

        params = dict(
            type="stream",
            op="stop",
            stream_id=str(stream_id),
            topic=topic_name,
        )

        with self.assert_database_query_count(6):
            with self.capture_send_event_calls(expected_num_events=1) as events:
                result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_user_ids = set(events[0]["users"])

        self.assertEqual(expected_user_ids, event_user_ids)
        self.assertEqual(sender.email, event["sender"]["email"])
        self.assertEqual(stream_id, event["stream_id"])
        self.assertEqual(topic_name, event["topic"])
        self.assertEqual("typing", event["type"])
        self.assertEqual("stop", event["op"])

    def test_max_stream_size_for_typing_notifications_setting(self) -> None:
        sender = self.example_user("hamlet")
        stream_name = self.get_streams(sender)[0]
        stream_id = self.get_stream_id(stream_name)
        topic_name = "Some topic"

        for name in ["aaron", "iago", "cordelia", "prospero", "othello", "polonius"]:
            user = self.example_user(name)
            self.subscribe(user, stream_name)

        params = dict(
            type="stream",
            op="start",
            stream_id=str(stream_id),
            topic=topic_name,
        )
        with self.settings(MAX_STREAM_SIZE_FOR_TYPING_NOTIFICATIONS=5):
            with self.assert_database_query_count(5):
                with self.capture_send_event_calls(expected_num_events=0) as events:
                    result = self.api_post(sender, "/api/v1/typing", params)
            self.assert_json_success(result)
            self.assert_length(events, 0)

    def test_notify_not_long_term_idle_subscribers_only(self) -> None:
        sender = self.example_user("hamlet")
        stream_name = self.get_streams(sender)[0]
        stream_id = self.get_stream_id(stream_name)
        topic_name = "Some topic"

        aaron = self.example_user("aaron")
        iago = self.example_user("iago")
        for user in [aaron, iago]:
            self.subscribe(user, stream_name)
            self.soft_deactivate_user(user)

        subscriber_ids = {
            user_profile.id
            for user_profile in self.users_subscribed_to_stream(stream_name, sender.realm)
        }
        not_long_term_idle_subscriber_ids = subscriber_ids - {aaron.id, iago.id}

        params = dict(
            type="stream",
            op="start",
            stream_id=str(stream_id),
            topic=topic_name,
        )

        with self.assert_database_query_count(6):
            with self.capture_send_event_calls(expected_num_events=1) as events:
                result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_success(result)
        self.assert_length(events, 1)

        event = events[0]["event"]
        event_user_ids = set(events[0]["users"])

        # Only subscribers who are not long_term_idle are notified for typing notifications.
        self.assertNotEqual(subscriber_ids, event_user_ids)
        self.assertEqual(not_long_term_idle_subscriber_ids, event_user_ids)

        self.assertEqual(sender.email, event["sender"]["email"])
        self.assertEqual(stream_id, event["stream_id"])
        self.assertEqual(topic_name, event["topic"])
        self.assertEqual("typing", event["type"])
        self.assertEqual("start", event["op"])


class TestSendTypingNotificationsSettings(ZulipTestCase):
    def test_send_private_typing_notifications_setting(self) -> None:
        sender = self.example_user("hamlet")
        recipient_user = self.example_user("othello")
        expected_recipients = {sender, recipient_user}
        expected_recipient_ids = {user.id for user in expected_recipients}

        params = dict(
            to=orjson.dumps([recipient_user.id]).decode(),
            op="start",
        )

        # Test typing events sent when `send_private_typing_notifications` set to `True`.
        self.assertTrue(sender.send_private_typing_notifications)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.api_post(sender, "/api/v1/typing", params)

        self.assert_json_success(result)
        self.assert_length(events, 1)
        event_user_ids = set(events[0]["users"])
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(orjson.loads(result.content)["msg"], "")

        sender.send_private_typing_notifications = False
        sender.save()

        # No events should be sent now
        with self.capture_send_event_calls(expected_num_events=0) as events:
            result = self.api_post(sender, "/api/v1/typing", params)

        self.assert_json_error(result, "User has disabled typing notifications for direct messages")
        self.assertEqual(events, [])

    def test_send_stream_typing_notifications_setting(self) -> None:
        sender = self.example_user("hamlet")
        stream_name = self.get_streams(sender)[0]
        stream_id = self.get_stream_id(stream_name)
        topic_name = "Some topic"

        expected_user_ids = self.not_long_term_idle_subscriber_ids(stream_name, sender.realm)

        params = dict(
            type="stream",
            op="start",
            stream_id=str(stream_id),
            topic=topic_name,
        )

        # Test typing events sent when `send_stream_typing_notifications` set to `True`.
        self.assertTrue(sender.send_stream_typing_notifications)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(orjson.loads(result.content)["msg"], "")
        event_user_ids = set(events[0]["users"])
        self.assertEqual(expected_user_ids, event_user_ids)

        sender.send_stream_typing_notifications = False
        sender.save()

        # No events should be sent now
        with self.capture_send_event_calls(expected_num_events=0) as events:
            result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_error(
            result, "User has disabled typing notifications for channel messages"
        )
        self.assertEqual(events, [])

    def test_typing_notifications_disabled(self) -> None:
        sender = self.example_user("hamlet")
        stream_name = self.get_streams(sender)[0]
        stream_id = self.get_stream_id(stream_name)
        topic_name = "Some topic"

        aaron = self.example_user("aaron")
        iago = self.example_user("iago")
        for user in [aaron, iago]:
            self.subscribe(user, stream_name)

        aaron.receives_typing_notifications = False
        aaron.save()

        params = dict(
            type="stream",
            op="start",
            stream_id=str(stream_id),
            topic=topic_name,
        )

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.api_post(sender, "/api/v1/typing", params)
        self.assert_json_success(result)
        self.assert_length(events, 1)

        event_user_ids = set(events[0]["users"])

        # Only users who have typing notifications enabled would receive
        # notifications.
        self.assertNotIn(aaron.id, event_user_ids)
        self.assertIn(iago.id, event_user_ids)

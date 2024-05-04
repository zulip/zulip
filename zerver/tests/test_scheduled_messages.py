import re
import time
from datetime import timedelta
from io import StringIO
from typing import TYPE_CHECKING, Any, Dict, List, Union
from unittest import mock

import orjson
import time_machine
from django.utils.timezone import now as timezone_now

from zerver.actions.scheduled_messages import (
    SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES,
    try_deliver_one_scheduled_message,
)
from zerver.actions.users import change_user_is_active
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Attachment, Message, Recipient, ScheduledMessage, UserMessage

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class ScheduledMessageTest(ZulipTestCase):
    def last_scheduled_message(self) -> ScheduledMessage:
        return ScheduledMessage.objects.all().order_by("-id")[0]

    def get_scheduled_message(self, id: str) -> ScheduledMessage:
        return ScheduledMessage.objects.get(id=id)

    def do_schedule_message(
        self,
        msg_type: str,
        to: Union[int, List[str], List[int]],
        msg: str,
        scheduled_delivery_timestamp: int,
    ) -> "TestHttpResponse":
        self.login("hamlet")

        topic_name = ""
        if msg_type in ["stream", "channel"]:
            topic_name = "Test topic"

        payload = {
            "type": msg_type,
            "to": orjson.dumps(to).decode(),
            "content": msg,
            "topic": topic_name,
            "scheduled_delivery_timestamp": scheduled_delivery_timestamp,
        }

        result = self.client_post("/json/scheduled_messages", payload)
        return result

    def test_schedule_message(self) -> None:
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        verona_stream_id = self.get_stream_id("Verona")

        # Scheduling a message to a stream you are subscribed is successful.
        result = self.do_schedule_message(
            "channel", verona_stream_id, content + " 1", scheduled_delivery_timestamp
        )
        scheduled_message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(scheduled_message.content, "Test message 1")
        self.assertEqual(scheduled_message.rendered_content, "<p>Test message 1</p>")
        self.assertEqual(scheduled_message.topic_name(), "Test topic")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )

        # Scheduling a direct message with user IDs is successful.
        othello = self.example_user("othello")
        result = self.do_schedule_message(
            "direct", [othello.id], content + " 3", scheduled_delivery_timestamp
        )
        scheduled_message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(scheduled_message.content, "Test message 3")
        self.assertEqual(scheduled_message.rendered_content, "<p>Test message 3</p>")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )

        # Cannot schedule a direct message with user emails.
        result = self.do_schedule_message(
            "direct", [othello.email], content + " 4", scheduled_delivery_timestamp
        )
        self.assert_json_error(result, "Recipient list may only contain user IDs")

    def create_scheduled_message(self) -> None:
        content = "Test message"
        scheduled_delivery_datetime = timezone_now() + timedelta(minutes=5)
        scheduled_delivery_timestamp = int(scheduled_delivery_datetime.timestamp())
        verona_stream_id = self.get_stream_id("Verona")
        result = self.do_schedule_message(
            "channel", verona_stream_id, content + " 1", scheduled_delivery_timestamp
        )
        self.assert_json_success(result)

    def test_successful_deliver_stream_scheduled_message(self) -> None:
        logger = mock.Mock()
        # No scheduled message
        result = try_deliver_one_scheduled_message(logger)
        self.assertFalse(result)

        self.create_scheduled_message()
        scheduled_message = self.last_scheduled_message()

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = scheduled_message.scheduled_timestamp + timedelta(
            minutes=1
        )

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            result = try_deliver_one_scheduled_message(logger)
            self.assertTrue(result)
            logger.info.assert_called_once_with(
                "Sending scheduled message %s with date %s (sender: %s)",
                scheduled_message.id,
                scheduled_message.scheduled_timestamp,
                scheduled_message.sender_id,
            )
            scheduled_message.refresh_from_db()
            assert isinstance(scheduled_message.delivered_message_id, int)
            self.assertEqual(scheduled_message.delivered, True)
            self.assertEqual(scheduled_message.failed, False)
            delivered_message = Message.objects.get(id=scheduled_message.delivered_message_id)
            self.assertEqual(delivered_message.content, scheduled_message.content)
            self.assertEqual(delivered_message.rendered_content, scheduled_message.rendered_content)
            self.assertEqual(delivered_message.topic_name(), scheduled_message.topic_name())
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_successful_deliver_direct_scheduled_message(self) -> None:
        logger = mock.Mock()
        # No scheduled message
        self.assertFalse(try_deliver_one_scheduled_message(logger))

        content = "Test message"
        scheduled_delivery_datetime = timezone_now() + timedelta(minutes=5)
        scheduled_delivery_timestamp = int(scheduled_delivery_datetime.timestamp())
        sender = self.example_user("hamlet")
        othello = self.example_user("othello")
        response = self.do_schedule_message(
            "direct", [othello.id], content + " 3", scheduled_delivery_timestamp
        )
        self.assert_json_success(response)
        scheduled_message = self.last_scheduled_message()

        # mock current time to be greater than the scheduled time.
        more_than_scheduled_delivery_datetime = scheduled_delivery_datetime + timedelta(minutes=1)

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            result = try_deliver_one_scheduled_message(logger)
            self.assertTrue(result)
            logger.info.assert_called_once_with(
                "Sending scheduled message %s with date %s (sender: %s)",
                scheduled_message.id,
                scheduled_message.scheduled_timestamp,
                scheduled_message.sender_id,
            )
            scheduled_message.refresh_from_db()
            assert isinstance(scheduled_message.delivered_message_id, int)
            self.assertEqual(scheduled_message.delivered, True)
            self.assertEqual(scheduled_message.failed, False)
            delivered_message = Message.objects.get(id=scheduled_message.delivered_message_id)
            self.assertEqual(delivered_message.content, scheduled_message.content)
            self.assertEqual(delivered_message.rendered_content, scheduled_message.rendered_content)
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)
            sender_user_message = UserMessage.objects.get(
                message_id=scheduled_message.delivered_message_id, user_profile_id=sender.id
            )
            self.assertTrue(sender_user_message.flags.read)

        # Check error is sent if an edit happens after the scheduled
        # message is successfully sent.
        new_delivery_datetime = timezone_now() + timedelta(minutes=7)
        new_delivery_timestamp = int(new_delivery_datetime.timestamp())
        content = "New message content"
        payload = {
            "content": content,
            "scheduled_delivery_timestamp": new_delivery_timestamp,
        }
        updated_response = self.client_patch(
            f"/json/scheduled_messages/{scheduled_message.id}", payload
        )
        self.assert_json_error(updated_response, "Scheduled message was already sent")

    def test_successful_deliver_direct_scheduled_message_to_self(self) -> None:
        logger = mock.Mock()
        # No scheduled message
        self.assertFalse(try_deliver_one_scheduled_message(logger))

        content = "Test message to self"
        scheduled_delivery_datetime = timezone_now() + timedelta(minutes=5)
        scheduled_delivery_timestamp = int(scheduled_delivery_datetime.timestamp())
        sender = self.example_user("hamlet")
        response = self.do_schedule_message(
            "direct", [sender.id], content, scheduled_delivery_timestamp
        )
        self.assert_json_success(response)
        scheduled_message = self.last_scheduled_message()

        # mock current time to be greater than the scheduled time.
        more_than_scheduled_delivery_datetime = scheduled_delivery_datetime + timedelta(minutes=1)

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            result = try_deliver_one_scheduled_message(logger)
            self.assertTrue(result)
            logger.info.assert_called_once_with(
                "Sending scheduled message %s with date %s (sender: %s)",
                scheduled_message.id,
                scheduled_message.scheduled_timestamp,
                scheduled_message.sender_id,
            )
            scheduled_message.refresh_from_db()
            assert isinstance(scheduled_message.delivered_message_id, int)
            self.assertEqual(scheduled_message.delivered, True)
            self.assertEqual(scheduled_message.failed, False)
            delivered_message = Message.objects.get(id=scheduled_message.delivered_message_id)
            self.assertEqual(delivered_message.content, scheduled_message.content)
            self.assertEqual(delivered_message.rendered_content, scheduled_message.rendered_content)
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)
            sender_user_message = UserMessage.objects.get(
                message_id=scheduled_message.delivered_message_id, user_profile_id=sender.id
            )
            self.assertFalse(sender_user_message.flags.read)

    def verify_deliver_scheduled_message_failure(
        self, scheduled_message: ScheduledMessage, logger: mock.Mock, expected_failure_message: str
    ) -> None:
        result = try_deliver_one_scheduled_message(logger)
        self.assertTrue(result)
        scheduled_message.refresh_from_db()
        self.assertEqual(scheduled_message.failure_message, expected_failure_message)
        calls = [
            mock.call(
                "Sending scheduled message %s with date %s (sender: %s)",
                scheduled_message.id,
                scheduled_message.scheduled_timestamp,
                scheduled_message.sender_id,
            ),
            mock.call("Failed with message: %s", scheduled_message.failure_message),
        ]
        logger.info.assert_has_calls(calls)
        self.assertEqual(logger.info.call_count, 2)
        self.assertTrue(scheduled_message.failed)

    def test_too_late_to_deliver_scheduled_message(self) -> None:
        expected_failure_message = "Message could not be sent at the scheduled time."
        logger = mock.Mock()
        self.create_scheduled_message()
        scheduled_message = self.last_scheduled_message()

        too_late_to_send_message_datetime = scheduled_message.scheduled_timestamp + timedelta(
            minutes=SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES + 1
        )

        with time_machine.travel(too_late_to_send_message_datetime, tick=False):
            self.verify_deliver_scheduled_message_failure(
                scheduled_message, logger, expected_failure_message
            )

        # Verify that the user was sent a message informing them about
        # the failed scheduled message.
        realm = scheduled_message.realm
        msg = most_recent_message(scheduled_message.sender)
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id, self.notification_bot(realm).id)
        self.assertIn(expected_failure_message, msg.content)

    def test_realm_deactivated_failed_to_deliver_scheduled_message(self) -> None:
        expected_failure_message = "This organization has been deactivated"
        logger = mock.Mock()
        self.create_scheduled_message()
        scheduled_message = self.last_scheduled_message()

        # Verify realm isn't deactivated and get user's most recent
        # message.
        self.assertFalse(scheduled_message.realm.deactivated)
        message_before_deactivation = most_recent_message(scheduled_message.sender)

        more_than_scheduled_delivery_datetime = scheduled_message.scheduled_timestamp + timedelta(
            minutes=1
        )

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            scheduled_message = self.last_scheduled_message()
            scheduled_message.realm.deactivated = True
            scheduled_message.realm.save()
            self.verify_deliver_scheduled_message_failure(
                scheduled_message, logger, expected_failure_message
            )

        # Verify that no failed scheduled message notification was sent.
        self.assertTrue(scheduled_message.realm.deactivated)
        message_after_deactivation = most_recent_message(scheduled_message.sender)
        self.assertEqual(message_after_deactivation.content, message_before_deactivation.content)
        self.assertNotIn(expected_failure_message, message_after_deactivation.content)

    def test_sender_deactivated_failed_to_deliver_scheduled_message(self) -> None:
        expected_failure_message = "Account is deactivated"
        logger = mock.Mock()
        self.create_scheduled_message()
        scheduled_message = self.last_scheduled_message()

        # Verify user isn't deactivated and get user's most recent
        # message.
        self.assertTrue(scheduled_message.sender.is_active)
        message_before_deactivation = most_recent_message(scheduled_message.sender)

        more_than_scheduled_delivery_datetime = scheduled_message.scheduled_timestamp + timedelta(
            minutes=1
        )

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            scheduled_message = self.last_scheduled_message()
            change_user_is_active(scheduled_message.sender, False)
            self.verify_deliver_scheduled_message_failure(
                scheduled_message, logger, expected_failure_message
            )

        # Verify that no failed scheduled message notification was sent.
        self.assertFalse(scheduled_message.sender.is_active)
        message_after_deactivation = most_recent_message(scheduled_message.sender)
        self.assertEqual(message_after_deactivation.content, message_before_deactivation.content)
        self.assertNotIn(expected_failure_message, message_after_deactivation.content)

    def test_delivery_type_reminder_failed_to_deliver_scheduled_message_unknown_exception(
        self,
    ) -> None:
        logger = mock.Mock()
        self.create_scheduled_message()
        scheduled_message = self.last_scheduled_message()

        more_than_scheduled_delivery_datetime = scheduled_message.scheduled_timestamp + timedelta(
            minutes=1
        )

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            scheduled_message = self.last_scheduled_message()
            scheduled_message.delivery_type = ScheduledMessage.REMIND
            scheduled_message.save()
            result = try_deliver_one_scheduled_message(logger)
            self.assertTrue(result)
            scheduled_message.refresh_from_db()
            logger.info.assert_called_once_with(
                "Sending scheduled message %s with date %s (sender: %s)",
                scheduled_message.id,
                scheduled_message.scheduled_timestamp,
                scheduled_message.sender_id,
            )
            logger.exception.assert_called_once_with(
                "Unexpected error sending scheduled message %s (sent: %s)",
                scheduled_message.id,
                scheduled_message.delivered,
                stack_info=True,
            )
            self.assertTrue(scheduled_message.failed)

        # Verify that the user was sent a message informing them about
        # the failed scheduled message.
        realm = scheduled_message.realm
        msg = most_recent_message(scheduled_message.sender)
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id, self.notification_bot(realm).id)
        self.assertIn("Internal server error", msg.content)

    def test_editing_failed_send_scheduled_message(self) -> None:
        expected_failure_message = "Message could not be sent at the scheduled time."
        logger = mock.Mock()
        self.create_scheduled_message()
        scheduled_message = self.last_scheduled_message()

        too_late_to_send_message_datetime = scheduled_message.scheduled_timestamp + timedelta(
            minutes=SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES + 1
        )

        with time_machine.travel(too_late_to_send_message_datetime, tick=False):
            self.verify_deliver_scheduled_message_failure(
                scheduled_message, logger, expected_failure_message
            )

            # After verifying the scheduled message failed to be sent:
            # Confirm not updating the scheduled delivery timestamp for
            # the scheduled message with that ID returns an error.
            payload_without_timestamp = {"topic": "Failed to send"}
            response = self.client_patch(
                f"/json/scheduled_messages/{scheduled_message.id}", payload_without_timestamp
            )
            self.assert_json_error(response, "Scheduled delivery time must be in the future.")

        # Editing the scheduled message with that ID for a future time is
        # successful and resets the `failed` and `failure_message` fields.
        new_delivery_datetime = timezone_now() + timedelta(minutes=60)
        new_delivery_timestamp = int(new_delivery_datetime.timestamp())
        scheduled_message_id = scheduled_message.id
        payload_with_timestamp = {
            "scheduled_delivery_timestamp": new_delivery_timestamp,
        }
        response = self.client_patch(
            f"/json/scheduled_messages/{scheduled_message.id}", payload_with_timestamp
        )
        self.assert_json_success(response)

        scheduled_message = self.last_scheduled_message()
        self.assertEqual(scheduled_message.id, scheduled_message_id)
        self.assertFalse(scheduled_message.failed)
        self.assertIsNone(scheduled_message.failure_message)

    def test_scheduling_in_past(self) -> None:
        # Scheduling a message in past should fail.
        content = "Test message"
        verona_stream_id = self.get_stream_id("Verona")
        scheduled_delivery_timestamp = int(time.time() - 86400)

        result = self.do_schedule_message(
            "channel", verona_stream_id, content + " 1", scheduled_delivery_timestamp
        )
        self.assert_json_error(result, "Scheduled delivery time must be in the future.")

    def test_edit_schedule_message(self) -> None:
        content = "Original test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        verona_stream_id = self.get_stream_id("Verona")

        # Scheduling a message to a stream you are subscribed is successful.
        result = self.do_schedule_message(
            "channel", verona_stream_id, content, scheduled_delivery_timestamp
        )
        scheduled_message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(scheduled_message.recipient.type, Recipient.STREAM)
        self.assertEqual(scheduled_message.content, "Original test message")
        self.assertEqual(scheduled_message.topic_name(), "Test topic")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )
        scheduled_message_id = scheduled_message.id
        payload: Dict[str, Any]

        # Edit message with other stream message type ("stream") and no other changes
        # results in no changes to the scheduled message.
        payload = {
            "type": "stream",
            "to": orjson.dumps(verona_stream_id).decode(),
            "topic": "Test topic",
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_success(result)

        scheduled_message = self.get_scheduled_message(str(scheduled_message_id))
        self.assertEqual(scheduled_message.recipient.type, Recipient.STREAM)
        self.assertEqual(scheduled_message.stream_id, verona_stream_id)
        self.assertEqual(scheduled_message.content, "Original test message")
        self.assertEqual(scheduled_message.topic_name(), "Test topic")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )

        # Sending request with only scheduled message ID returns an error
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}")
        self.assert_json_error(result, "Nothing to change")

        # Trying to edit only message `type` returns an error
        payload = {
            "type": "direct",
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_error(
            result, "Recipient required when updating type of scheduled message."
        )

        # Edit message `type` with valid `to` parameter succeeds
        othello = self.example_user("othello")
        to = [othello.id]
        payload = {"type": "direct", "to": orjson.dumps(to).decode()}
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_success(result)

        scheduled_message = self.get_scheduled_message(str(scheduled_message_id))
        self.assertNotEqual(scheduled_message.recipient.type, Recipient.STREAM)

        # Trying to edit `topic` for direct message is ignored
        payload = {
            "topic": "Direct message topic",
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_success(result)

        scheduled_message = self.get_scheduled_message(str(scheduled_message_id))
        self.assertEqual(scheduled_message.topic_name(), "")

        # Trying to edit `type` to stream message type without a `topic` returns an error
        payload = {
            "type": "channel",
            "to": orjson.dumps(verona_stream_id).decode(),
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_error(
            result, "Topic required when updating scheduled message type to channel."
        )

        # Edit message `type` to stream with valid `to` and `topic` succeeds
        payload = {
            "type": "channel",
            "to": orjson.dumps(verona_stream_id).decode(),
            "topic": "New test topic",
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_success(result)

        scheduled_message = self.get_scheduled_message(str(scheduled_message_id))
        self.assertEqual(scheduled_message.recipient.type, Recipient.STREAM)
        self.assertEqual(scheduled_message.topic_name(), "New test topic")

        # Trying to edit with timestamp in the past returns an error
        new_scheduled_delivery_timestamp = int(time.time() - 86400)
        payload = {
            "scheduled_delivery_timestamp": new_scheduled_delivery_timestamp,
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_error(result, "Scheduled delivery time must be in the future.")

        # Edit content and time of scheduled message succeeds
        edited_content = "Edited test message"
        new_scheduled_delivery_timestamp = scheduled_delivery_timestamp + int(
            time.time() + (3 * 86400)
        )
        payload = {
            "content": edited_content,
            "scheduled_delivery_timestamp": new_scheduled_delivery_timestamp,
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message_id}", payload)
        self.assert_json_success(result)

        scheduled_message = self.get_scheduled_message(str(scheduled_message_id))
        self.assertEqual(scheduled_message.content, edited_content)
        self.assertEqual(scheduled_message.topic_name(), "New test topic")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(new_scheduled_delivery_timestamp),
        )

        # Edit topic and content of scheduled stream message
        edited_content = "Final content edit for test"
        payload = {
            "topic": "Another topic for test",
            "content": edited_content,
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message.id}", payload)
        self.assert_json_success(result)

        scheduled_message = self.get_scheduled_message(str(scheduled_message.id))
        self.assertEqual(scheduled_message.content, edited_content)
        self.assertEqual(scheduled_message.topic_name(), "Another topic for test")

        # Edit only topic of scheduled stream message
        payload = {
            "topic": "Final topic for test",
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message.id}", payload)
        self.assert_json_success(result)

        scheduled_message = self.get_scheduled_message(str(scheduled_message.id))
        self.assertEqual(scheduled_message.recipient.type, Recipient.STREAM)
        self.assertEqual(scheduled_message.content, edited_content)
        self.assertEqual(scheduled_message.topic_name(), "Final topic for test")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(new_scheduled_delivery_timestamp),
        )

    def test_fetch_scheduled_messages(self) -> None:
        self.login("hamlet")
        # No scheduled message
        result = self.client_get("/json/scheduled_messages")
        self.assert_json_success(result)
        self.assert_length(orjson.loads(result.content)["scheduled_messages"], 0)

        verona_stream_id = self.get_stream_id("Verona")
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        self.do_schedule_message("channel", verona_stream_id, content, scheduled_delivery_timestamp)

        # Single scheduled message
        result = self.client_get("/json/scheduled_messages")
        self.assert_json_success(result)
        scheduled_messages = orjson.loads(result.content)["scheduled_messages"]

        self.assert_length(scheduled_messages, 1)
        self.assertEqual(
            scheduled_messages[0]["scheduled_message_id"], self.last_scheduled_message().id
        )
        self.assertEqual(scheduled_messages[0]["content"], content)
        self.assertEqual(scheduled_messages[0]["to"], verona_stream_id)
        self.assertEqual(scheduled_messages[0]["type"], "stream")
        self.assertEqual(scheduled_messages[0]["topic"], "Test topic")
        self.assertEqual(
            scheduled_messages[0]["scheduled_delivery_timestamp"], scheduled_delivery_timestamp
        )

        othello = self.example_user("othello")
        result = self.do_schedule_message(
            "direct", [othello.id], content + " 3", scheduled_delivery_timestamp
        )

        # Multiple scheduled messages
        result = self.client_get("/json/scheduled_messages")
        self.assert_json_success(result)
        self.assert_length(orjson.loads(result.content)["scheduled_messages"], 2)

        # Check if another user can access these scheduled messages.
        self.logout()
        self.login("othello")
        result = self.client_get("/json/scheduled_messages")
        self.assert_json_success(result)
        self.assert_length(orjson.loads(result.content)["scheduled_messages"], 0)

    def test_delete_scheduled_messages(self) -> None:
        self.login("hamlet")

        content = "Test message"
        verona_stream_id = self.get_stream_id("Verona")
        scheduled_delivery_timestamp = int(time.time() + 86400)

        self.do_schedule_message("channel", verona_stream_id, content, scheduled_delivery_timestamp)
        scheduled_message = self.last_scheduled_message()
        self.logout()

        # Other user cannot delete it.
        othello = self.example_user("othello")
        result = self.api_delete(othello, f"/api/v1/scheduled_messages/{scheduled_message.id}")
        self.assert_json_error(result, "Scheduled message does not exist", 404)

        self.login("hamlet")
        result = self.client_delete(f"/json/scheduled_messages/{scheduled_message.id}")
        self.assert_json_success(result)

        # Already deleted.
        result = self.client_delete(f"/json/scheduled_messages/{scheduled_message.id}")
        self.assert_json_error(result, "Scheduled message does not exist", 404)

    def test_attachment_handling(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        verona_stream_id = self.get_stream_id("Verona")

        attachment_file1 = StringIO("zulip!")
        attachment_file1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {"file": attachment_file1})
        path_id1 = re.sub(r"/user_uploads/", "", result.json()["uri"])
        attachment_object1 = Attachment.objects.get(path_id=path_id1)

        attachment_file2 = StringIO("zulip!")
        attachment_file2.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {"file": attachment_file2})
        path_id2 = re.sub(r"/user_uploads/", "", result.json()["uri"])
        attachment_object2 = Attachment.objects.get(path_id=path_id2)

        content = f"Test [zulip.txt](http://{hamlet.realm.host}/user_uploads/{path_id1})"
        scheduled_delivery_timestamp = int(time.time() + 86400)

        # Test sending with attachment
        self.do_schedule_message("channel", verona_stream_id, content, scheduled_delivery_timestamp)
        scheduled_message = self.last_scheduled_message()
        self.assertEqual(
            list(attachment_object1.scheduled_messages.all().values_list("id", flat=True)),
            [scheduled_message.id],
        )
        self.assertEqual(scheduled_message.has_attachment, True)

        # Test editing to change attachmment
        edited_content = f"Test [zulip.txt](http://{hamlet.realm.host}/user_uploads/{path_id2})"
        payload = {
            "content": edited_content,
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message.id}", payload)

        scheduled_message = self.get_scheduled_message(str(scheduled_message.id))
        self.assertEqual(
            list(attachment_object1.scheduled_messages.all().values_list("id", flat=True)), []
        )
        self.assertEqual(
            list(attachment_object2.scheduled_messages.all().values_list("id", flat=True)),
            [scheduled_message.id],
        )
        self.assertEqual(scheduled_message.has_attachment, True)

        # Test editing to no longer reference any attachments
        edited_content = "No more attachments"
        payload = {
            "content": edited_content,
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message.id}", payload)

        scheduled_message = self.get_scheduled_message(str(scheduled_message.id))
        self.assertEqual(
            list(attachment_object1.scheduled_messages.all().values_list("id", flat=True)), []
        )
        self.assertEqual(
            list(attachment_object2.scheduled_messages.all().values_list("id", flat=True)), []
        )
        self.assertEqual(scheduled_message.has_attachment, False)

        # Test editing to now have an attachment again
        edited_content = (
            f"Attachment is back! [zulip.txt](http://{hamlet.realm.host}/user_uploads/{path_id2})"
        )
        payload = {
            "content": edited_content,
        }
        result = self.client_patch(f"/json/scheduled_messages/{scheduled_message.id}", payload)

        scheduled_message = self.get_scheduled_message(str(scheduled_message.id))
        self.assertEqual(
            list(attachment_object1.scheduled_messages.all().values_list("id", flat=True)), []
        )
        self.assertEqual(
            list(attachment_object2.scheduled_messages.all().values_list("id", flat=True)),
            [scheduled_message.id],
        )
        self.assertEqual(scheduled_message.has_attachment, True)

import datetime
import re
import time
from io import StringIO
from typing import TYPE_CHECKING, List, Union
from unittest import mock

import orjson
from django.utils.timezone import now as timezone_now

from zerver.actions.scheduled_messages import (
    SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES,
    extract_direct_message_recipient_ids,
    extract_stream_id,
    try_deliver_one_scheduled_message,
)
from zerver.actions.users import change_user_is_active
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Attachment, Message, ScheduledMessage

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
        scheduled_message_id: str = "",
    ) -> "TestHttpResponse":
        self.login("hamlet")

        topic_name = ""
        if msg_type == "stream":
            topic_name = "Test topic"

        payload = {
            "type": msg_type,
            "to": orjson.dumps(to).decode(),
            "content": msg,
            "topic": topic_name,
            "scheduled_delivery_timestamp": scheduled_delivery_timestamp,
        }

        if scheduled_message_id:
            payload["scheduled_message_id"] = scheduled_message_id

        result = self.client_post("/json/scheduled_messages", payload)
        return result

    def test_schedule_message(self) -> None:
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        verona_stream_id = self.get_stream_id("Verona")

        # Scheduling a message to a stream you are subscribed is successful.
        result = self.do_schedule_message(
            "stream", verona_stream_id, content + " 1", scheduled_delivery_timestamp
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

        # Scheduling a private message is successful.
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

    def create_scheduled_message(self) -> None:
        content = "Test message"
        scheduled_delivery_datetime = timezone_now() + datetime.timedelta(minutes=5)
        scheduled_delivery_timestamp = int(scheduled_delivery_datetime.timestamp())
        verona_stream_id = self.get_stream_id("Verona")
        result = self.do_schedule_message(
            "stream", verona_stream_id, content + " 1", scheduled_delivery_timestamp
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
        more_than_scheduled_delivery_datetime = (
            scheduled_message.scheduled_timestamp + datetime.timedelta(minutes=1)
        )
        with mock.patch(
            "zerver.actions.scheduled_messages.timezone_now",
            return_value=more_than_scheduled_delivery_datetime,
        ):
            # mock time that will be set for delivered_message
            with mock.patch(
                "zerver.actions.message_send.timezone_now",
                return_value=more_than_scheduled_delivery_datetime,
            ):
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
                self.assertEqual(
                    delivered_message.rendered_content, scheduled_message.rendered_content
                )
                self.assertEqual(delivered_message.topic_name(), scheduled_message.topic_name())
                self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_successful_deliver_private_scheduled_message(self) -> None:
        logger = mock.Mock()
        # No scheduled message
        self.assertFalse(try_deliver_one_scheduled_message(logger))

        content = "Test message"
        scheduled_delivery_datetime = timezone_now() + datetime.timedelta(minutes=5)
        scheduled_delivery_timestamp = int(scheduled_delivery_datetime.timestamp())
        othello = self.example_user("othello")
        response = self.do_schedule_message(
            "direct", [othello.id], content + " 3", scheduled_delivery_timestamp
        )
        self.assert_json_success(response)
        scheduled_message = self.last_scheduled_message()

        # mock current time to be greater than the scheduled time.
        more_than_scheduled_delivery_datetime = scheduled_delivery_datetime + datetime.timedelta(
            minutes=1
        )
        with mock.patch(
            "zerver.actions.scheduled_messages.timezone_now",
            return_value=more_than_scheduled_delivery_datetime,
        ):
            with mock.patch(
                "zerver.actions.message_send.timezone_now",
                return_value=more_than_scheduled_delivery_datetime,
            ):
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
                self.assertEqual(
                    delivered_message.rendered_content, scheduled_message.rendered_content
                )
                self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

        # Check error is sent if an edit happens after the scheduled
        # message is successfully sent.
        new_delivery_datetime = timezone_now() + datetime.timedelta(minutes=7)
        new_delivery_timestamp = int(new_delivery_datetime.timestamp())
        updated_response = self.do_schedule_message(
            "direct",
            [othello.id],
            "New content!",
            new_delivery_timestamp,
            scheduled_message_id=str(scheduled_message.id),
        )
        self.assert_json_error(updated_response, "Scheduled message was already sent")

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

        too_late_to_send_message_datetime = (
            scheduled_message.scheduled_timestamp
            + datetime.timedelta(minutes=SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES + 1)
        )
        with mock.patch(
            "zerver.actions.scheduled_messages.timezone_now",
            return_value=too_late_to_send_message_datetime,
        ):
            self.verify_deliver_scheduled_message_failure(
                scheduled_message, logger, expected_failure_message
            )

        # Verify that the user was sent a message informing them about
        # the failed scheduled message.
        realm = scheduled_message.sender.realm
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
        self.assertFalse(scheduled_message.sender.realm.deactivated)
        message_before_deactivation = most_recent_message(scheduled_message.sender)

        more_than_scheduled_delivery_datetime = (
            scheduled_message.scheduled_timestamp + datetime.timedelta(minutes=1)
        )
        with mock.patch(
            "zerver.actions.scheduled_messages.timezone_now",
            return_value=more_than_scheduled_delivery_datetime,
        ):
            scheduled_message = self.last_scheduled_message()
            scheduled_message.realm.deactivated = True
            scheduled_message.realm.save()
            self.verify_deliver_scheduled_message_failure(
                scheduled_message, logger, expected_failure_message
            )

        # Verify that no failed scheduled message notification was sent.
        self.assertTrue(scheduled_message.sender.realm.deactivated)
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

        more_than_scheduled_delivery_datetime = (
            scheduled_message.scheduled_timestamp + datetime.timedelta(minutes=1)
        )
        with mock.patch(
            "zerver.actions.scheduled_messages.timezone_now",
            return_value=more_than_scheduled_delivery_datetime,
        ):
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

        more_than_scheduled_delivery_datetime = (
            scheduled_message.scheduled_timestamp + datetime.timedelta(minutes=1)
        )
        with mock.patch(
            "zerver.actions.scheduled_messages.timezone_now",
            return_value=more_than_scheduled_delivery_datetime,
        ):
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
        realm = scheduled_message.sender.realm
        msg = most_recent_message(scheduled_message.sender)
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id, self.notification_bot(realm).id)
        self.assertIn("Internal server error", msg.content)

    def test_scheduling_in_past(self) -> None:
        # Scheduling a message in past should fail.
        content = "Test message"
        verona_stream_id = self.get_stream_id("Verona")
        scheduled_delivery_timestamp = int(time.time() - 86400)

        result = self.do_schedule_message(
            "stream", verona_stream_id, content + " 1", scheduled_delivery_timestamp
        )
        self.assert_json_error(result, "Scheduled delivery time must be in the future.")

    def test_edit_schedule_message(self) -> None:
        content = "Original test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        verona_stream_id = self.get_stream_id("Verona")

        # Scheduling a message to a stream you are subscribed is successful.
        result = self.do_schedule_message(
            "stream", verona_stream_id, content, scheduled_delivery_timestamp
        )
        scheduled_message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(scheduled_message.content, "Original test message")
        self.assertEqual(scheduled_message.topic_name(), "Test topic")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )

        # Edit content and time of scheduled message.
        edited_content = "Edited test message"
        new_scheduled_delivery_timestamp = scheduled_delivery_timestamp + int(
            time.time() + (3 * 86400)
        )

        result = self.do_schedule_message(
            "stream",
            verona_stream_id,
            edited_content,
            new_scheduled_delivery_timestamp,
            scheduled_message_id=str(scheduled_message.id),
        )
        scheduled_message = self.get_scheduled_message(str(scheduled_message.id))
        self.assert_json_success(result)
        self.assertEqual(scheduled_message.content, edited_content)
        self.assertEqual(scheduled_message.topic_name(), "Test topic")
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
        self.do_schedule_message("stream", verona_stream_id, content, scheduled_delivery_timestamp)

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

        self.do_schedule_message("stream", verona_stream_id, content, scheduled_delivery_timestamp)
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
        path_id1 = re.sub("/user_uploads/", "", result.json()["uri"])
        attachment_object1 = Attachment.objects.get(path_id=path_id1)

        attachment_file2 = StringIO("zulip!")
        attachment_file2.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {"file": attachment_file2})
        path_id2 = re.sub("/user_uploads/", "", result.json()["uri"])
        attachment_object2 = Attachment.objects.get(path_id=path_id2)

        content = f"Test [zulip.txt](http://{hamlet.realm.host}/user_uploads/{path_id1})"
        scheduled_delivery_timestamp = int(time.time() + 86400)

        # Test sending with attachment
        self.do_schedule_message("stream", verona_stream_id, content, scheduled_delivery_timestamp)
        scheduled_message = self.last_scheduled_message()
        self.assertEqual(
            list(attachment_object1.scheduled_messages.all().values_list("id", flat=True)),
            [scheduled_message.id],
        )
        self.assertEqual(scheduled_message.has_attachment, True)

        # Test editing to change attachmment
        edited_content = f"Test [zulip.txt](http://{hamlet.realm.host}/user_uploads/{path_id2})"
        result = self.do_schedule_message(
            "stream",
            verona_stream_id,
            edited_content,
            scheduled_delivery_timestamp,
            scheduled_message_id=str(scheduled_message.id),
        )
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
        result = self.do_schedule_message(
            "stream",
            verona_stream_id,
            edited_content,
            scheduled_delivery_timestamp,
            scheduled_message_id=str(scheduled_message.id),
        )
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
        result = self.do_schedule_message(
            "stream",
            verona_stream_id,
            edited_content,
            scheduled_delivery_timestamp,
            scheduled_message_id=str(scheduled_message.id),
        )
        scheduled_message = self.get_scheduled_message(str(scheduled_message.id))
        self.assertEqual(
            list(attachment_object1.scheduled_messages.all().values_list("id", flat=True)), []
        )
        self.assertEqual(
            list(attachment_object2.scheduled_messages.all().values_list("id", flat=True)),
            [scheduled_message.id],
        )
        self.assertEqual(scheduled_message.has_attachment, True)

    def test_extract_stream_id(self) -> None:
        # Scheduled stream message recipient = single stream ID.
        stream_id = extract_stream_id("1")
        self.assertEqual(stream_id, [1])

        with self.assertRaisesRegex(JsonableError, "Invalid data type for stream ID"):
            extract_stream_id("1,2")

        with self.assertRaisesRegex(JsonableError, "Invalid data type for stream ID"):
            extract_stream_id("[1]")

        with self.assertRaisesRegex(JsonableError, "Invalid data type for stream ID"):
            extract_stream_id("general")

    def test_extract_recipient_ids(self) -> None:
        # Scheduled direct message recipients = user IDs.
        user_ids = "[3,2,1]"
        result = sorted(extract_direct_message_recipient_ids(user_ids))
        self.assertEqual(result, [1, 2, 3])

        # JSON list w/duplicates
        user_ids = orjson.dumps([3, 3, 12]).decode()
        result = sorted(extract_direct_message_recipient_ids(user_ids))
        self.assertEqual(result, [3, 12])

        # Invalid data
        user_ids = "1, 12"
        with self.assertRaisesRegex(JsonableError, "Invalid data type for recipients"):
            extract_direct_message_recipient_ids(user_ids)

        user_ids = orjson.dumps(dict(recipient=12)).decode()
        with self.assertRaisesRegex(JsonableError, "Invalid data type for recipients"):
            extract_direct_message_recipient_ids(user_ids)

        # Heterogeneous lists are not supported
        user_ids = orjson.dumps([3, 4, "eeshan@example.com"]).decode()
        with self.assertRaisesRegex(JsonableError, "Recipient list may only contain user IDs"):
            extract_direct_message_recipient_ids(user_ids)

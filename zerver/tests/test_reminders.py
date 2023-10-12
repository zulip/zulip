import datetime
import time
from typing import TYPE_CHECKING
from unittest import mock

import time_machine

from zerver.actions.scheduled_messages import try_deliver_one_scheduled_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Message, ScheduledMessage

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class RemindersTest(ZulipTestCase):
    def do_schedule_reminder(
        self,
        message_id: int,
        scheduled_delivery_timestamp: int,
    ) -> "TestHttpResponse":
        self.login("hamlet")

        payload = {
            "message_id": message_id,
            "scheduled_delivery_timestamp": scheduled_delivery_timestamp,
        }

        result = self.client_post("/json/reminders", payload)
        return result

    def create_reminder(self, content: str, message_type: str = "direct") -> ScheduledMessage:
        if message_type == "stream":
            message_id = self.get_stream_message(content)
        else:
            message_id = self.get_direct_message(content)

        scheduled_delivery_timestamp = int(time.time() + 86400)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        return self.last_scheduled_reminder()

    def last_scheduled_reminder(self) -> ScheduledMessage:
        return ScheduledMessage.objects.all().order_by("-id")[0]

    def last_message(self) -> Message:
        return Message.objects.all().order_by("-id")[0]

    def get_stream_message(self, content: str) -> int:
        return self.send_stream_message(self.example_user("hamlet"), "Verona", content)

    def get_direct_message(self, content: str) -> int:
        return self.send_personal_message(
            self.example_user("hamlet"), self.example_user("othello"), content
        )

    def test_schedule_reminder(self) -> None:
        self.login("hamlet")
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)

        # Scheduling a reminder to a stream you are subscribed is successful.
        message_id = self.get_stream_message(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(scheduled_message.content, content)
        self.assertEqual(scheduled_message.rendered_content, "<p>Test message</p>")
        # Recipient and sender are the same for reminders.
        self.assertEqual(scheduled_message.recipient.type_id, self.example_user("hamlet").id)
        self.assertEqual(scheduled_message.sender, self.example_user("hamlet"))
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )
        self.assertEqual(
            scheduled_message.reminder_target_message_id,
            message_id,
        )

        # Scheduling a direct message with user IDs is successful.
        self.example_user("othello")
        message_id = self.get_direct_message(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(scheduled_message.content, content)
        self.assertEqual(scheduled_message.rendered_content, "<p>Test message</p>")
        self.assertEqual(scheduled_message.recipient.type_id, self.example_user("hamlet").id)
        self.assertEqual(scheduled_message.sender, self.example_user("hamlet"))
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )
        self.assertEqual(
            scheduled_message.reminder_target_message_id,
            message_id,
        )

    def test_schedule_reminder_with_bad_timestamp(self) -> None:
        self.login("hamlet")
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() - 86400)

        message_id = self.get_stream_message(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_error(
            result, "Scheduled delivery time for reminder must be in the future."
        )

    def test_schedule_reminder_with_bad_message_id(self) -> None:
        self.login("hamlet")
        scheduled_delivery_timestamp = int(time.time() + 86400)

        result = self.do_schedule_reminder(123456789, scheduled_delivery_timestamp)
        self.assert_json_error(result, "Invalid message(s)")
        message = self.last_message()
        # Check if the error message was sent to the user.
        self.assertEqual(
            message.content,
            "You asked for a reminder about a [message with ID 123456789](http://zulip.testserver/#narrow/near/123456789), but either the message has been deleted or you no longer have access to the message.",
        )
        self.assertEqual(message.sender, self.notification_bot(message.sender.realm))
        self.assertEqual(message.recipient.type_id, self.example_user("hamlet").id)

    def test_successful_deliver_direct_message_reminder(self) -> None:
        logger = mock.Mock()
        # No scheduled message
        result = try_deliver_one_scheduled_message(logger)
        self.assertFalse(result)

        content = "Test content"
        reminder = self.create_reminder(content)

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            result = try_deliver_one_scheduled_message(logger)
            self.assertTrue(result)
            logger.info.assert_called_once_with(
                "Sending scheduled message %s with date %s (sender: %s)",
                reminder.id,
                reminder.scheduled_timestamp,
                reminder.sender_id,
            )
            reminder.refresh_from_db()
            assert isinstance(reminder.delivered_message_id, int)
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            self.assertEqual(
                delivered_message.content,
                f"You requested a reminder for the following private message.\n\n@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/dm/10-King-Hamlet/near/{reminder.reminder_target_message_id}):\n```quote\nTest content\n```",
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_successful_deliver_stream_message_reminder(self) -> None:
        logger = mock.Mock()
        # No scheduled message
        result = try_deliver_one_scheduled_message(logger)
        self.assertFalse(result)

        content = "Test content"
        reminder = self.create_reminder(content, "stream")

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            result = try_deliver_one_scheduled_message(logger)
            self.assertTrue(result)
            logger.info.assert_called_once_with(
                "Sending scheduled message %s with date %s (sender: %s)",
                reminder.id,
                reminder.scheduled_timestamp,
                reminder.sender_id,
            )
            reminder.refresh_from_db()
            assert isinstance(reminder.delivered_message_id, int)
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            self.assertEqual(
                delivered_message.content,
                f"You requested a reminder for the following message sent to [Verona > test](http://zulip.testserver/#narrow/stream/1-Verona/topic/test).\n\n@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/stream/1-Verona/topic/test/near/{reminder.reminder_target_message_id}):\n```quote\nTest content\n```",
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_send_reminder_at_max_content_limit(self) -> None:
        logger = mock.Mock()
        # No scheduled message
        result = try_deliver_one_scheduled_message(logger)
        self.assertFalse(result)

        content = "x" * 10000
        reminder = self.create_reminder(content)

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with time_machine.travel(more_than_scheduled_delivery_datetime, tick=False):
            result = try_deliver_one_scheduled_message(logger)
            self.assertTrue(result)
            logger.info.assert_called_once_with(
                "Sending scheduled message %s with date %s (sender: %s)",
                reminder.id,
                reminder.scheduled_timestamp,
                reminder.sender_id,
            )
            reminder.refresh_from_db()
            assert isinstance(reminder.delivered_message_id, int)
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            # The reminder message is truncated to 10,000 characters if it exceeds the limit.
            assert delivered_message.content.endswith("[message truncated]")
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

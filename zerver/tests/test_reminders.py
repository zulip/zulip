import datetime
import time
from typing import TYPE_CHECKING

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
            message_id = self.send_channel_message_for_hamlet(content)
        else:
            message_id = self.send_dm_from_hamlet_to_othello(content)

        scheduled_delivery_timestamp = int(time.time() + 86400)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        return self.last_scheduled_reminder()

    def last_scheduled_reminder(self) -> ScheduledMessage:
        return ScheduledMessage.objects.filter(delivery_type=ScheduledMessage.REMIND).order_by(
            "-id"
        )[0]

    def send_channel_message_for_hamlet(self, content: str) -> int:
        return self.send_stream_message(self.example_user("hamlet"), "Verona", content)

    def send_dm_from_hamlet_to_othello(self, content: str) -> int:
        return self.send_personal_message(
            self.example_user("hamlet"), self.example_user("othello"), content
        )

    def get_dm_reminder_content(self, msg_content: str, msg_id: int) -> str:
        return (
            "You requested a reminder for the following direct message.\n\n"
            f"@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/dm/10,12/near/{msg_id}):\n```quote\n{msg_content}\n```"
        )

    def get_channel_message_reminder_content(self, msg_content: str, msg_id: int) -> str:
        return (
            f"You requested a reminder for #**Verona>test@{msg_id}**.\n\n"
            f"@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/channel/3-Verona/topic/test/near/{msg_id}):\n```quote\n{msg_content}\n```"
        )

    def test_schedule_reminder(self) -> None:
        self.login("hamlet")
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)

        # Scheduling a reminder to a channel you are subscribed is successful.
        message_id = self.send_channel_message_for_hamlet(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content,
            self.get_channel_message_reminder_content(content, message_id),
        )
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
        self.assertEqual(scheduled_message.topic_name(), Message.DM_TOPIC)

        # Scheduling a direct message with user IDs is successful.
        self.example_user("othello")
        message_id = self.send_dm_from_hamlet_to_othello(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content, self.get_dm_reminder_content(content, message_id)
        )
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
        self.assertEqual(scheduled_message.topic_name(), Message.DM_TOPIC)

    def test_schedule_reminder_with_bad_timestamp(self) -> None:
        self.login("hamlet")
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() - 86400)

        message_id = self.send_channel_message_for_hamlet(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_error(result, "Scheduled delivery time must be in the future.")

    def test_schedule_reminder_with_bad_message_id(self) -> None:
        self.login("hamlet")
        scheduled_delivery_timestamp = int(time.time() + 86400)

        result = self.do_schedule_reminder(123456789, scheduled_delivery_timestamp)
        self.assert_json_error(result, "Invalid message(s)")

    def test_successful_deliver_direct_message_reminder(self) -> None:
        # No scheduled message
        result = try_deliver_one_scheduled_message()
        self.assertFalse(result)

        content = "Test content"
        reminder = self.create_reminder(content)

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with (
            time_machine.travel(more_than_scheduled_delivery_datetime, tick=False),
            self.assertLogs(level="INFO") as logs,
        ):
            result = try_deliver_one_scheduled_message()
            self.assertTrue(result)
            reminder.refresh_from_db()
            self.assertEqual(
                logs.output,
                [
                    f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})"
                ],
            )
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            assert isinstance(reminder.delivered_message_id, int)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            assert isinstance(reminder.reminder_target_message_id, int)
            self.assertEqual(
                delivered_message.content,
                self.get_dm_reminder_content(content, reminder.reminder_target_message_id),
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_successful_deliver_channel_message_reminder(self) -> None:
        # No scheduled message
        result = try_deliver_one_scheduled_message()
        self.assertFalse(result)

        content = "Test content"
        reminder = self.create_reminder(content, "stream")

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with (
            time_machine.travel(more_than_scheduled_delivery_datetime, tick=False),
            self.assertLogs(level="INFO") as logs,
        ):
            result = try_deliver_one_scheduled_message()
            self.assertTrue(result)
            reminder.refresh_from_db()
            self.assertEqual(
                logs.output,
                [
                    f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})"
                ],
            )
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            assert isinstance(reminder.delivered_message_id, int)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            assert isinstance(reminder.reminder_target_message_id, int)
            self.assertEqual(
                delivered_message.content,
                self.get_channel_message_reminder_content(
                    content, reminder.reminder_target_message_id
                ),
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_send_reminder_at_max_content_limit(self) -> None:
        # No scheduled message
        result = try_deliver_one_scheduled_message()
        self.assertFalse(result)

        content = "x" * 10000
        reminder = self.create_reminder(content)

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with (
            time_machine.travel(more_than_scheduled_delivery_datetime, tick=False),
            self.assertLogs(level="INFO") as logs,
        ):
            result = try_deliver_one_scheduled_message()
            self.assertTrue(result)
            reminder.refresh_from_db()
            self.assertEqual(
                logs.output,
                [
                    f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})"
                ],
            )
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            assert isinstance(reminder.delivered_message_id, int)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            # The reminder message is truncated to 10,000 characters if it exceeds the limit.
            assert isinstance(reminder.reminder_target_message_id, int)
            length_of_reminder_content_wrapper = len(
                self.get_dm_reminder_content(
                    "\n[message truncated]", reminder.reminder_target_message_id
                )
            )
            self.assertEqual(
                delivered_message.content,
                self.get_dm_reminder_content(
                    content[:-length_of_reminder_content_wrapper] + "\n[message truncated]",
                    reminder.reminder_target_message_id,
                ),
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_scheduled_reminder_with_inaccessible_message(self) -> None:
        # No scheduled message
        result = try_deliver_one_scheduled_message()
        self.assertFalse(result)

        content = "Test content"
        reminder = self.create_reminder(content)

        # Delete the message to make it inaccessible.
        assert isinstance(reminder.reminder_target_message_id, int)
        Message.objects.filter(id=reminder.reminder_target_message_id).delete()

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )
        with (
            time_machine.travel(more_than_scheduled_delivery_datetime, tick=False),
            self.assertLogs(level="INFO") as logs,
        ):
            result = try_deliver_one_scheduled_message()
            self.assertTrue(result)
            reminder.refresh_from_db()
            self.assertEqual(
                logs.output,
                [
                    f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})"
                ],
            )
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            assert isinstance(reminder.delivered_message_id, int)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            self.assertEqual(
                delivered_message.content,
                self.get_dm_reminder_content(content, reminder.reminder_target_message_id),
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_delete_reminder(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        response = self.api_get(hamlet, "/api/v1/reminders")
        self.assert_json_success(response)
        response_data = response.json()
        self.assertEqual(response_data["reminders"], [])

        # Create a test message to schedule a reminder for.
        message_id = self.send_stream_message(
            hamlet,
            "Denmark",
        )

        # Schedule a reminder for the created message.
        deliver_at = int(time.time() + 86400)

        response = self.do_schedule_reminder(
            message_id=message_id,
            scheduled_delivery_timestamp=deliver_at,
        )
        self.assert_json_success(response)
        response_data = response.json()
        self.assertIn("reminder_id", response_data)
        reminder_id = response_data["reminder_id"]

        # Verify that the reminder was scheduled correctly.
        reminders_response = self.api_get(hamlet, "/api/v1/reminders")
        self.assert_json_success(reminders_response)
        reminders_data = reminders_response.json()
        self.assert_length(reminders_data["reminders"], 1)
        reminder = reminders_data["reminders"][0]
        self.assertEqual(reminder["reminder_id"], reminder_id)
        self.assertEqual(reminder["reminder_target_message_id"], message_id)

        # Test deleting the reminder with the wrong user.
        result = self.api_delete(cordelia, f"/api/v1/reminders/{reminder_id}")
        self.assert_json_error(result, "Reminder does not exist", status_code=404)

        # Test deleting the reminder.
        result = self.client_delete(f"/json/reminders/{reminder_id}")
        self.assert_json_success(result)

        # Verify that the reminder was deleted.
        self.assertEqual(response.status_code, 200)
        reminders_response = self.api_get(hamlet, "/api/v1/reminders")
        self.assert_json_success(reminders_response)
        reminders_data = reminders_response.json()
        self.assert_length(reminders_data["reminders"], 0)

        # Try deleting again to trigger failure.
        result = self.client_delete(f"/json/reminders/{reminder_id}")
        self.assert_json_error(result, "Reminder does not exist", status_code=404)

    def test_reminder_for_poll(self) -> None:
        content = "/poll What is your favorite color?"
        reminder = self.create_reminder(content)

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with (
            time_machine.travel(more_than_scheduled_delivery_datetime, tick=False),
            self.assertLogs(level="INFO") as logs,
        ):
            result = try_deliver_one_scheduled_message()
            self.assertTrue(result)
            reminder.refresh_from_db()
            self.assertEqual(
                logs.output,
                [
                    f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})"
                ],
            )
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            assert isinstance(reminder.delivered_message_id, int)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            assert isinstance(reminder.reminder_target_message_id, int)
            self.assertEqual(
                delivered_message.content,
                "You requested a reminder for the following direct message."
                "\n\n"
                f"@_**King Hamlet|10** [sent](http://zulip.testserver/#narrow/dm/10,12/near/{reminder.reminder_target_message_id}) a poll.",
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_reminder_for_todo(self) -> None:
        content = "/todo List of tasks"
        reminder = self.create_reminder(content)

        # mock current time to be greater than the scheduled time, so that the `scheduled_message` can be sent.
        more_than_scheduled_delivery_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=1
        )

        with (
            time_machine.travel(more_than_scheduled_delivery_datetime, tick=False),
            self.assertLogs(level="INFO") as logs,
        ):
            result = try_deliver_one_scheduled_message()
            self.assertTrue(result)
            reminder.refresh_from_db()
            self.assertEqual(
                logs.output,
                [
                    f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})"
                ],
            )
            self.assertEqual(reminder.delivered, True)
            self.assertEqual(reminder.failed, False)
            assert isinstance(reminder.delivered_message_id, int)
            delivered_message = Message.objects.get(id=reminder.delivered_message_id)
            assert isinstance(reminder.reminder_target_message_id, int)
            self.assertEqual(
                delivered_message.content,
                "You requested a reminder for the following direct message."
                "\n\n"
                f"@_**King Hamlet|10** [sent](http://zulip.testserver/#narrow/dm/10,12/near/{reminder.reminder_target_message_id}) a todo list.",
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

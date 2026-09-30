import datetime
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING
from unittest import mock

import time_machine

from zerver.actions.realm_settings import do_deactivate_realm
from zerver.actions.scheduled_messages import (
    SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES,
    try_deliver_one_scheduled_message,
)
from zerver.actions.users import change_user_is_active
from zerver.lib.message import get_user_mentions_for_display
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Message, ScheduledMessage
from zerver.models.recipients import Recipient, get_or_create_direct_message_group
from zerver.models.users import UserProfile

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class RemindersTest(ZulipTestCase):
    def do_schedule_reminder(
        self,
        message_id: int,
        scheduled_delivery_timestamp: int,
        note: str | None = None,
    ) -> "TestHttpResponse":
        self.login("hamlet")

        payload: dict[str, int | str] = {
            "message_id": message_id,
            "scheduled_delivery_timestamp": scheduled_delivery_timestamp,
        }
        if note is not None:
            payload["note"] = note

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

    def get_dm_reminder_content(
        self, msg_content: str, msg_id: int, dm_recipients: Sequence[UserProfile]
    ) -> str:
        recipient_mentions = get_user_mentions_for_display(list(dm_recipients))
        return (
            "You requested a reminder for the following direct message.\n\n"
            f"@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/dm/10,12/near/{msg_id}) to {recipient_mentions}:\n```quote\n{msg_content}\n```"
        )

    def get_channel_message_reminder_content(self, msg_content: str, msg_id: int) -> str:
        return (
            f"You requested a reminder for the following message.\n\n"
            f"@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/channel/3-Verona/topic/test/near/{msg_id}) in [#Verona > test](#narrow/channel/3-Verona/topic/test/with/{msg_id}):\n```quote\n{msg_content}\n```"
        )

    def test_schedule_reminder(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        self.login("hamlet")
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)

        # Create a direct message group for hamlet's self messages.
        hamlet_self_direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        # Scheduling a reminder to a channel you are subscribed is successful.
        message_id = self.send_channel_message_for_hamlet(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content,
            self.get_channel_message_reminder_content(content, message_id),
        )
        self.assertEqual(scheduled_message.recipient.type, Recipient.DIRECT_MESSAGE_GROUP)
        self.assertEqual(scheduled_message.recipient.type_id, hamlet_self_direct_message_group.id)
        self.assertEqual(scheduled_message.sender, hamlet)
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )
        self.assertEqual(
            scheduled_message.reminder_target_message_id,
            message_id,
        )
        self.assertEqual(scheduled_message.topic_name(), Message.DM_TOPIC)

        # Create a direct message group between hamlet and othello.
        get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        # Scheduling a direct message with user IDs is successful.
        message_id = self.send_dm_from_hamlet_to_othello(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content, self.get_dm_reminder_content(content, message_id, [othello])
        )
        self.assertEqual(scheduled_message.recipient.type, Recipient.DIRECT_MESSAGE_GROUP)
        self.assertEqual(scheduled_message.recipient.type_id, hamlet_self_direct_message_group.id)
        self.assertEqual(scheduled_message.sender, hamlet)
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
                self.get_dm_reminder_content(
                    content, reminder.reminder_target_message_id, [self.example_user("othello")]
                ),
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
            othello = self.example_user("othello")
            length_of_reminder_content_wrapper = len(
                self.get_dm_reminder_content(
                    "\n[message truncated]",
                    reminder.reminder_target_message_id,
                    [othello],
                )
            )
            self.assertEqual(
                delivered_message.content,
                self.get_dm_reminder_content(
                    content[:-length_of_reminder_content_wrapper] + "\n[message truncated]",
                    reminder.reminder_target_message_id,
                    [othello],
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
                self.get_dm_reminder_content(
                    content, reminder.reminder_target_message_id, [self.example_user("othello")]
                ),
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_reminder_still_fires_past_late_cutoff(self) -> None:
        # Reminders deliberately bypass the late-cutoff guard: a
        # reminder delivered late is strictly more useful to the
        # sender than one silently dropped.
        content = "Test content"
        reminder = self.create_reminder(content)

        too_late_datetime = reminder.scheduled_timestamp + datetime.timedelta(
            minutes=SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES + 1
        )
        with (
            time_machine.travel(too_late_datetime, tick=False),
            self.assertLogs(level="INFO") as logs,
        ):
            self.assertTrue(try_deliver_one_scheduled_message())

        reminder.refresh_from_db()
        self.assertTrue(reminder.delivered)
        self.assertFalse(reminder.failed)
        assert isinstance(reminder.delivered_message_id, int)
        self.assertEqual(
            logs.output,
            [
                f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})"
            ],
        )
        delivered_message = Message.objects.get(id=reminder.delivered_message_id)
        assert isinstance(reminder.reminder_target_message_id, int)
        self.assertEqual(
            delivered_message.content,
            self.get_dm_reminder_content(
                content, reminder.reminder_target_message_id, [self.example_user("othello")]
            ),
        )
        self.assertEqual(delivered_message.date_sent, too_late_datetime)

    def assert_reminder_dropped_silently(
        self,
        reminder: ScheduledMessage,
        expected_failure_message: str,
        message_before: Message,
        logs_output: list[str],
    ) -> None:
        # Reminders have their own notification system, so a failed
        # reminder is expected to be recorded on the row but NOT to
        # send a failure DM back to the sender.
        reminder.refresh_from_db()
        self.assertTrue(reminder.failed)
        self.assertFalse(reminder.delivered)
        self.assertIsNone(reminder.delivered_message_id)
        self.assertEqual(reminder.failure_message, expected_failure_message)
        self.assertEqual(
            logs_output,
            [
                f"INFO:root:Sending scheduled message {reminder.id} with date {reminder.scheduled_timestamp} (sender: {reminder.sender_id})",
                f"INFO:root:Failed with message: {expected_failure_message}",
            ],
        )
        self.assertEqual(most_recent_message(reminder.sender).id, message_before.id)

    def test_reminder_refused_for_deactivated_sender(self) -> None:
        expected_failure_message = "Account is deactivated"
        reminder = self.create_reminder("Test content")
        message_before = most_recent_message(reminder.sender)

        with (
            time_machine.travel(
                reminder.scheduled_timestamp + datetime.timedelta(minutes=1), tick=False
            ),
            self.assertLogs(level="INFO") as logs,
        ):
            change_user_is_active(reminder.sender, False)
            self.assertTrue(try_deliver_one_scheduled_message())

        self.assert_reminder_dropped_silently(
            reminder, expected_failure_message, message_before, logs.output
        )

    def test_reminder_refused_when_send_returns_none(self) -> None:
        # internal_send_private_message swallows JsonableError from
        # check_message and returns None; the worker must still mark
        # the row failed rather than delivered with a NULL message id.
        expected_failure_message = "Reminder could not be sent."
        reminder = self.create_reminder("Test content")
        message_before = most_recent_message(reminder.sender)

        with (
            time_machine.travel(
                reminder.scheduled_timestamp + datetime.timedelta(minutes=1), tick=False
            ),
            mock.patch(
                "zerver.actions.scheduled_messages.internal_send_private_message",
                return_value=None,
            ),
            self.assertLogs(level="INFO") as logs,
        ):
            self.assertTrue(try_deliver_one_scheduled_message())

        self.assert_reminder_dropped_silently(
            reminder, expected_failure_message, message_before, logs.output
        )

    def test_reminder_refused_for_deactivated_realm(self) -> None:
        expected_failure_message = "This organization has been deactivated"
        reminder = self.create_reminder("Test content")
        message_before = most_recent_message(reminder.sender)

        with (
            time_machine.travel(
                reminder.scheduled_timestamp + datetime.timedelta(minutes=1), tick=False
            ),
            self.assertLogs(level="INFO") as logs,
        ):
            do_deactivate_realm(
                reminder.realm,
                acting_user=None,
                deactivation_reason="owner_request",
                email_owners=False,
            )
            self.assertTrue(try_deliver_one_scheduled_message())

        self.assert_reminder_dropped_silently(
            reminder, expected_failure_message, message_before, logs.output
        )

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
            recipient_mentions = get_user_mentions_for_display([self.example_user("othello")])
            self.assertEqual(
                delivered_message.content,
                "You requested a reminder for the following direct message."
                "\n\n"
                f"@_**King Hamlet|10** [sent](http://zulip.testserver/#narrow/dm/10,12/near/{reminder.reminder_target_message_id}) a poll to {recipient_mentions}.",
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
            recipient_mentions = get_user_mentions_for_display([self.example_user("othello")])
            self.assertEqual(
                delivered_message.content,
                "You requested a reminder for the following direct message."
                "\n\n"
                f"@_**King Hamlet|10** [sent](http://zulip.testserver/#narrow/dm/10,12/near/{reminder.reminder_target_message_id}) a todo list to {recipient_mentions}.",
            )
            self.assertEqual(delivered_message.date_sent, more_than_scheduled_delivery_datetime)

    def test_notes_in_reminder(self) -> None:
        content = "Test message with notes"
        note = "This is a note for the reminder."
        scheduled_delivery_timestamp = int(time.time() + 86400)
        recipient_mentions = get_user_mentions_for_display([self.example_user("othello")])

        message_id = self.send_channel_message_for_hamlet(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp, note)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content,
            f"You requested a reminder for the following message. Note:\n > {note}\n\n"
            f"@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/channel/3-Verona/topic/test/near/{message_id}) in [#Verona > test](#narrow/channel/3-Verona/topic/test/with/{message_id}):\n```quote\n{content}\n```",
        )

        message_id = self.send_dm_from_hamlet_to_othello(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp, note)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content,
            f"You requested a reminder for the following direct message. Note:\n > {note}\n\n"
            f"@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/dm/10,12/near/{message_id}) to {recipient_mentions}:\n```quote\n{content}\n```",
        )

        # Test with no note
        message_id = self.send_dm_from_hamlet_to_othello(content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content,
            self.get_dm_reminder_content(content, message_id, [self.example_user("othello")]),
        )

        # Test with note exceeding maximum length
        note = "long note"
        with self.settings(MAX_REMINDER_NOTE_LENGTH=len(note) - 1):
            result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp, note)
            self.assert_json_error(
                result,
                f"Maximum reminder note length: {len(note) - 1} characters",
                status_code=400,
            )

        # Test with note containing formatting characters
        note = "{123}"
        content = "{456}"
        message_id = self.send_stream_message(
            self.example_user("hamlet"), "Verona", content, topic_name="{789}"
        )
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp, note)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()
        self.assertEqual(
            scheduled_message.content,
            "You requested a reminder for the following message. Note:\n > {123}\n\n"
            f"@_**King Hamlet|10** [said](http://zulip.testserver/#narrow/channel/3-Verona/topic/.7B789.7D/near/{message_id})"
            " in [#Verona > {789}](#narrow/channel/3-Verona/topic/.7B789.7D/with/"
            f"{message_id}):\n"
            f"```quote\n{content}\n```",
        )

    def test_schedule_reminder_ones_own_message(self) -> None:
        content = "Test message"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        hamlet = self.example_user("hamlet")

        message_id = self.send_personal_message(hamlet, hamlet, content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()

        self.assertEqual(
            scheduled_message.content,
            (
                "You requested a reminder for the following direct message.\n\n"
                f"You [sent](http://zulip.testserver/#narrow/dm/10/near/{message_id}) a note to yourself:\n```quote\n{content}\n```"
            ),
        )

        content = "/todo Test todo list"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        hamlet = self.example_user("hamlet")

        message_id = self.send_personal_message(hamlet, hamlet, content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()

        self.assertEqual(
            scheduled_message.content,
            (
                "You requested a reminder for the following direct message.\n\n"
                f"You [sent](http://zulip.testserver/#narrow/dm/10/near/{message_id}) yourself a todo list."
            ),
        )

        content = "/poll Test poll"
        scheduled_delivery_timestamp = int(time.time() + 86400)
        hamlet = self.example_user("hamlet")

        message_id = self.send_personal_message(hamlet, hamlet, content)
        result = self.do_schedule_reminder(message_id, scheduled_delivery_timestamp)
        self.assert_json_success(result)
        scheduled_message = self.last_scheduled_reminder()

        self.assertEqual(
            scheduled_message.content,
            (
                "You requested a reminder for the following direct message.\n\n"
                f"You [sent](http://zulip.testserver/#narrow/dm/10/near/{message_id}) yourself a poll."
            ),
        )

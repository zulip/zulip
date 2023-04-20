import datetime
import sys
from typing import TYPE_CHECKING, List, Union

import orjson
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import convert_to_UTC
from zerver.models import ScheduledMessage

if sys.version_info < (3, 9):  # nocoverage
    from backports import zoneinfo
else:  # nocoverage
    import zoneinfo

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
        deliver_at: str = "",
        tz_guess: str = "",
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
            "tz_guess": tz_guess,
            "deliver_at": deliver_at,
        }

        if scheduled_message_id:
            payload["scheduled_message_id"] = scheduled_message_id

        result = self.client_post("/json/scheduled_messages", payload)
        return result

    def test_schedule_message(self) -> None:
        content = "Test message"
        deliver_at = timezone_now().replace(tzinfo=None) + datetime.timedelta(days=1)
        deliver_at_str = str(deliver_at)
        verona_stream_id = self.get_stream_id("Verona")

        # Scheduling a message to a stream you are subscribed is successful.
        result = self.do_schedule_message(
            "stream", verona_stream_id, content + " 1", deliver_at_str
        )
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, "Test message 1")
        self.assertEqual(message.rendered_content, "<p>Test message 1</p>")
        self.assertEqual(message.topic_name(), "Test topic")
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(deliver_at))

        # Scheduling a private message is successful.
        othello = self.example_user("othello")
        result = self.do_schedule_message(
            "private", [othello.email], content + " 3", deliver_at_str
        )
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, "Test message 3")
        self.assertEqual(message.rendered_content, "<p>Test message 3</p>")
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(deliver_at))

        # Scheduling a message while guessing time zone.
        tz_guess = "Asia/Kolkata"
        result = self.do_schedule_message(
            "stream", verona_stream_id, content + " 6", deliver_at_str, tz_guess=tz_guess
        )
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, "Test message 6")
        local_tz = zoneinfo.ZoneInfo(tz_guess)
        utz_deliver_at = deliver_at.replace(tzinfo=local_tz)
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(utz_deliver_at))

        # Test with users time zone setting as set to some time zone rather than
        # empty. This will help interpret timestamp in users local time zone.
        user = self.example_user("hamlet")
        user.timezone = "US/Pacific"
        user.save(update_fields=["timezone"])
        result = self.do_schedule_message(
            "stream", verona_stream_id, content + " 7", deliver_at_str
        )
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, "Test message 7")
        local_tz = zoneinfo.ZoneInfo(user.timezone)
        utz_deliver_at = deliver_at.replace(tzinfo=local_tz)
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(utz_deliver_at))

    def test_scheduling_in_past(self) -> None:
        # Scheduling a message in past should fail.
        content = "Test message"
        deliver_at = timezone_now()
        deliver_at_str = str(deliver_at)
        verona_stream_id = self.get_stream_id("Verona")

        result = self.do_schedule_message(
            "stream", verona_stream_id, content + " 1", deliver_at_str
        )
        self.assert_json_error(result, "Time must be in the future.")

    def test_invalid_timestamp(self) -> None:
        # Scheduling a message from which timestamp couldn't be parsed
        # successfully should fail.
        content = "Test message"
        deliver_at = "Missed the timestamp"
        verona_stream_id = self.get_stream_id("Verona")

        result = self.do_schedule_message("stream", verona_stream_id, content + " 1", deliver_at)
        self.assert_json_error(result, "Invalid time format")

    def test_invalid_deliver_at(self) -> None:
        content = "Test message"
        verona_stream_id = self.get_stream_id("Verona")

        result = self.do_schedule_message("stream", verona_stream_id, content + " 1", "XYZ")
        self.assert_json_error(result, "Invalid time format")

    def test_edit_schedule_message(self) -> None:
        content = "Original test message"
        deliver_at = timezone_now().replace(tzinfo=None) + datetime.timedelta(days=1)
        deliver_at_str = str(deliver_at)
        verona_stream_id = self.get_stream_id("Verona")

        # Scheduling a message to a stream you are subscribed is successful.
        result = self.do_schedule_message("stream", verona_stream_id, content, deliver_at_str)
        message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(message.content, "Original test message")
        self.assertEqual(message.topic_name(), "Test topic")
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(deliver_at))

        # Edit content and time of scheduled message.
        edited_content = "Edited test message"
        new_deliver_at = deliver_at + datetime.timedelta(days=3)
        new_deliver_at_str = str(new_deliver_at)

        result = self.do_schedule_message(
            "stream",
            verona_stream_id,
            edited_content,
            new_deliver_at_str,
            scheduled_message_id=str(message.id),
        )
        message = self.get_scheduled_message(str(message.id))
        self.assert_json_success(result)
        self.assertEqual(message.content, edited_content)
        self.assertEqual(message.topic_name(), "Test topic")
        self.assertEqual(message.scheduled_timestamp, convert_to_UTC(new_deliver_at))

    def test_fetch_scheduled_messages(self) -> None:
        self.login("hamlet")
        # No scheduled message
        result = self.client_get("/json/scheduled_messages")
        self.assert_json_success(result)
        self.assert_length(orjson.loads(result.content)["scheduled_messages"], 0)

        verona_stream_id = self.get_stream_id("Verona")
        content = "Test message"
        deliver_at = timezone_now().replace(tzinfo=None) + datetime.timedelta(days=1)
        deliver_at_str = str(deliver_at)
        self.do_schedule_message("stream", verona_stream_id, content, deliver_at_str)

        # Single scheduled message
        result = self.client_get("/json/scheduled_messages")
        self.assert_json_success(result)
        scheduled_messages = orjson.loads(result.content)["scheduled_messages"]

        self.assert_length(scheduled_messages, 1)
        self.assertEqual(
            scheduled_messages[0]["scheduled_message_id"], self.last_scheduled_message().id
        )
        self.assertEqual(scheduled_messages[0]["content"], content)
        self.assertEqual(scheduled_messages[0]["to"], [verona_stream_id])
        self.assertEqual(scheduled_messages[0]["type"], "stream")
        self.assertEqual(scheduled_messages[0]["topic"], "Test topic")
        self.assertEqual(
            scheduled_messages[0]["deliver_at"], int(convert_to_UTC(deliver_at).timestamp() * 1000)
        )

        othello = self.example_user("othello")
        result = self.do_schedule_message(
            "private", [othello.email], content + " 3", deliver_at_str
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
        deliver_at = timezone_now().replace(tzinfo=None) + datetime.timedelta(days=1)
        deliver_at_str = str(deliver_at)

        self.do_schedule_message("stream", verona_stream_id, content, deliver_at_str)
        message = self.last_scheduled_message()
        self.logout()

        # Other user cannot delete it.
        othello = self.example_user("othello")
        result = self.api_delete(othello, f"/api/v1/scheduled_messages/{message.id}")
        self.assert_json_error(result, "Scheduled message does not exist", 404)

        self.login("hamlet")
        result = self.client_delete(f"/json/scheduled_messages/{message.id}")
        self.assert_json_success(result)

        # Already deleted.
        result = self.client_delete(f"/json/scheduled_messages/{message.id}")
        self.assert_json_error(result, "Scheduled message does not exist", 404)

import time
from typing import TYPE_CHECKING, List, Union

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import ScheduledMessage

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
            "direct", [othello.email], content + " 3", scheduled_delivery_timestamp
        )
        scheduled_message = self.last_scheduled_message()
        self.assert_json_success(result)
        self.assertEqual(scheduled_message.content, "Test message 3")
        self.assertEqual(scheduled_message.rendered_content, "<p>Test message 3</p>")
        self.assertEqual(
            scheduled_message.scheduled_timestamp,
            timestamp_to_datetime(scheduled_delivery_timestamp),
        )

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
            "direct", [othello.email], content + " 3", scheduled_delivery_timestamp
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

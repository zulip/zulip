import re
import time
from io import StringIO
from typing import TYPE_CHECKING, List, Union

import orjson

from zerver.actions.scheduled_messages import (
    extract_direct_message_recipient_ids,
    extract_stream_id,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Attachment, ScheduledMessage

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

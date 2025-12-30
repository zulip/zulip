import orjson
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Recipient

class MessageCountTest(ZulipTestCase):
    def test_message_count_basic(self) -> None:
        self.login("hamlet")
        stream_name = "Scotland"
        topic_name = "count test"
        
        # Send some messages
        for i in range(5):
            self.send_stream_message(self.example_user("hamlet"), stream_name, topic_name=topic_name)
        
        narrow = [
            {"operator": "channel", "operand": stream_name},
            {"operator": "topic", "operand": topic_name},
        ]
        
        # Test basic count
        result = self.client_get("/json/messages/count", {"narrow": orjson.dumps(narrow).decode()})
        self.assert_json_success(result)
        self.assertEqual(result.json()["count"], 5)
        
        # Test with anchor (last 2 messages)
        # We need to filter correctly to get the messages we just sent
        all_messages = Message.objects.filter(
            recipient__type=Recipient.STREAM, 
            subject=topic_name
        ).order_by("id")
        
        self.assertEqual(len(all_messages), 5)
        anchor_id = all_messages[3].id # The 4th message
        
        result = self.client_get("/json/messages/count", {
            "narrow": orjson.dumps(narrow).decode(),
            "anchor": anchor_id,
        })
        self.assert_json_success(result)
        # 4th and 5th messages = 2
        self.assertEqual(result.json()["count"], 2)
        
        # Test without include_anchor (only the 5th message)
        result = self.client_get("/json/messages/count", {
            "narrow": orjson.dumps(narrow).decode(),
            "anchor": anchor_id,
            "include_anchor": orjson.dumps(False).decode(),
        })
        self.assert_json_success(result)
        self.assertEqual(result.json()["count"], 1)

    def test_message_count_empty_topic(self) -> None:
        self.login("hamlet")
        narrow = [
            {"operator": "channel", "operand": "Scotland"},
            {"operator": "topic", "operand": "non-existent topic"},
        ]
        result = self.client_get("/json/messages/count", {"narrow": orjson.dumps(narrow).decode()})
        self.assert_json_success(result)
        self.assertEqual(result.json()["count"], 0)

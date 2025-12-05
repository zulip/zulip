from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_encoding import (
    encode_channel,
    encode_user_full_name_and_id,
    encode_user_ids,
    near_dm_message_url,
    near_message_url,
    near_stream_message_url,
)
from zerver.models import Message, Recipient, Stream


class URLEncodeTest(ZulipTestCase):
    def test_encode_channel(self) -> None:
        # We have more tests for this function in `test_topic_link_utils.py`
        self.assertEqual(encode_channel(9, "Verona"), "9-Verona")
        self.assertEqual(encode_channel(123, "General"), "123-General")
        self.assertEqual(encode_channel(7, "random_channel"), "7-random_channel")
        self.assertEqual(encode_channel(9, "Verona", with_operator=True), "channel/9-Verona")

    def test_encode_user_ids(self) -> None:
        # Group narrow URL has 3 or more user IDs
        self.assertEqual(encode_user_ids([1, 2, 3]), "1,2,3-group")
        self.assertEqual(encode_user_ids([3, 1, 2]), "1,2,3-group")

        # One-on-one narrow URL has 2 user IDs
        self.assertEqual(encode_user_ids([1, 2]), "1,2")

        # Narrow URL to ones own direct message conversation
        self.assertEqual(encode_user_ids([1]), "1")

        self.assertEqual(encode_user_ids([1, 2, 3], with_operator=True), "dm/1,2,3-group")
        with self.assertRaises(AssertionError):
            encode_user_ids([])

    def test_encode_user_full_name_and_id(self) -> None:
        self.assertEqual(encode_user_full_name_and_id("King Hamlet", 9), "9-King-Hamlet")
        self.assertEqual(
            encode_user_full_name_and_id("King Hamlet", 9, with_operator=True), "dm/9-King-Hamlet"
        )
        self.assertEqual(encode_user_full_name_and_id("ZOE", 1), "1-ZOE")
        self.assertEqual(encode_user_full_name_and_id("  User Name  ", 100), "100-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User  Name", 101), "101-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User/Name", 200), "200-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User%Name", 201), "201-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User<Name>", 202), "202-User-Name-")
        self.assertEqual(encode_user_full_name_and_id('User"Name`', 203), "203-User-Name-")
        self.assertEqual(encode_user_full_name_and_id('User/ % < > ` " Name', 204), "204-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User--Name", 205), "205-User--Name")
        self.assertEqual(encode_user_full_name_and_id("User%%Name", 206), "206-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User_Name", 5), "5-User_Name")


class MessageURLTest(ZulipTestCase):
    """Tests for type-safe Message-based URL functions (Issue #25021)."""

    def test_near_stream_message_url(self) -> None:
        # Send a message to a stream
        user = self.example_user("hamlet")
        stream = Stream.objects.get(name="Verona", realm=user.realm)
        message_id = self.send_stream_message(
            user,
            stream.name,
            topic_name="test topic",
            content="test content",
        )
        message = Message.objects.get(id=message_id)

        # Test basic URL generation
        url = near_stream_message_url(message)
        self.assertIn(f"#narrow/channel/{stream.id}-", url)
        self.assertIn("/topic/test.20topic", url)
        self.assertIn(f"/near/{message_id}", url)

        # Test with conversation_link=True
        url_with = near_stream_message_url(message, conversation_link=True)
        self.assertIn(f"/with/{message_id}", url_with)
        self.assertNotIn("/near/", url_with)

    def test_near_dm_message_url(self) -> None:
        # Send a direct message
        sender = self.example_user("hamlet")
        recipient = self.example_user("othello")
        message_id = self.send_personal_message(sender, recipient, content="test dm")
        message = Message.objects.get(id=message_id)

        # Test basic URL generation
        url = near_dm_message_url(message)
        self.assertIn("#narrow/dm/", url)
        self.assertIn(f"/near/{message_id}", url)

        # Test with conversation_link=True
        url_with = near_dm_message_url(message, conversation_link=True)
        self.assertIn(f"/with/{message_id}", url_with)

    def test_near_message_url_stream(self) -> None:
        # Test that near_message_url correctly dispatches to stream function
        user = self.example_user("hamlet")
        stream = Stream.objects.get(name="Verona", realm=user.realm)
        message_id = self.send_stream_message(user, stream.name, topic_name="test")
        message = Message.objects.get(id=message_id)

        url = near_message_url(message)
        self.assertIn("#narrow/channel/", url)
        self.assertEqual(message.recipient.type, Recipient.STREAM)

    def test_near_message_url_dm(self) -> None:
        # Test that near_message_url correctly dispatches to DM function
        sender = self.example_user("hamlet")
        recipient = self.example_user("othello")
        message_id = self.send_personal_message(sender, recipient)
        message = Message.objects.get(id=message_id)

        url = near_message_url(message)
        self.assertIn("#narrow/dm/", url)

    def test_near_stream_message_url_special_characters(self) -> None:
        # Test URL encoding with special characters in topic
        user = self.example_user("hamlet")
        stream = Stream.objects.get(name="Verona", realm=user.realm)
        message_id = self.send_stream_message(
            user,
            stream.name,
            topic_name="test/topic with spaces & special",
            content="test",
        )
        message = Message.objects.get(id=message_id)

        url = near_stream_message_url(message)
        # URL should be properly encoded
        self.assertNotIn(" ", url)
        self.assertIn("#narrow/channel/", url)

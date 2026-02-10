from zerver.lib.exceptions import JsonableError
from zerver.lib.recipient_parsing import extract_direct_message_recipient_ids, extract_stream_id
from zerver.lib.test_classes import ZulipTestCase


class TestRecipientParsing(ZulipTestCase):
    def test_extract_stream_id(self) -> None:
        # stream message recipient = single stream ID.
        stream_id = extract_stream_id(1)
        self.assertEqual(stream_id, 1)

        with self.assertRaisesRegex(JsonableError, "Invalid data type for channel ID"):
            extract_stream_id([1, 2])

        with self.assertRaisesRegex(JsonableError, "Invalid data type for channel ID"):
            extract_stream_id([1])

    def test_extract_recipient_ids(self) -> None:
        # direct message recipients = user IDs.
        user_ids = [3, 2, 1]
        result = sorted(extract_direct_message_recipient_ids(user_ids))
        self.assertEqual(result, [1, 2, 3])

        # list w/duplicates
        user_ids = [3, 3, 12]
        result = sorted(extract_direct_message_recipient_ids(user_ids))
        self.assertEqual(result, [3, 12])

        with self.assertRaisesRegex(JsonableError, "Invalid data type for recipients"):
            extract_direct_message_recipient_ids(1)

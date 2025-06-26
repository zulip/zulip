from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_encoding import encode_channel, encode_user_ids


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

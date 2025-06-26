from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_encoding import encode_stream


class URLEncodeTest(ZulipTestCase):
    def test_encode_stream(self) -> None:
        # We have more tests for this function in `test_topci_link_utils.py`
        self.assertEqual(encode_stream(9, "Verona"), "9-Verona")
        self.assertEqual(encode_stream(123, "General"), "123-General")
        self.assertEqual(encode_stream(7, "random_stream"), "7-random_stream")
        self.assertEqual(encode_stream(9, "Verona", with_operator=True), "channel/9-Verona")

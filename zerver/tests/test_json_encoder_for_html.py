import json
from zerver.lib.json_encoder_for_html import JSONEncoderForHTML
from zerver.lib.test_classes import ZulipTestCase

class TestJSONEncoder(ZulipTestCase):
    # Test EncoderForHTML
    # Taken from
    # https://github.com/simplejson/simplejson/blob/8edc82afcf6f7512b05fba32baa536fe756bd273/simplejson/tests/test_encode_for_html.py
    # License: MIT
    decoder = json.JSONDecoder()
    encoder = JSONEncoderForHTML()

    def test_basic_encode(self) -> None:
        self.assertEqual(r'"\u0026"', self.encoder.encode('&'))
        self.assertEqual(r'"\u003c"', self.encoder.encode('<'))
        self.assertEqual(r'"\u003e"', self.encoder.encode('>'))

    def test_basic_roundtrip(self) -> None:
        for char in '&<>':
            self.assertEqual(
                char, self.decoder.decode(
                    self.encoder.encode(char)))

    def test_prevent_script_breakout(self) -> None:
        bad_string = '</script><script>alert("gotcha")</script>'
        self.assertEqual(
            r'"\u003c/script\u003e\u003cscript\u003e'
            r'alert(\"gotcha\")\u003c/script\u003e"',
            self.encoder.encode(bad_string))
        self.assertEqual(
            bad_string, self.decoder.decode(
                self.encoder.encode(bad_string)))

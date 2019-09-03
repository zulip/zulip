from urllib.parse import urlencode

from zerver.lib.test_classes import WebhookTestCase

class PapertrailHookTests(WebhookTestCase):
    STREAM_NAME = 'papertrail'
    URL_TEMPLATE = "/api/v1/external/papertrail?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'papertrail'

    def test_short_message(self) -> None:
        expected_topic = u"logs"
        expected_message = """
[Search for "Important stuff"](https://papertrailapp.com/searches/42) found **2** matches:

May 18 20:30:02 - abc - cron OR server1:
``` quote
message body
```
May 18 20:30:02 - server1 - cron OR server1:
``` quote
A short event
```
""".strip()

        self.send_and_test_stream_message('short_post', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_long_message(self) -> None:
        expected_topic = u"logs"
        expected_message = """
[Search for "Important stuff"](https://papertrailapp.com/searches/42) found **5** matches:

May 18 20:30:02 - abc - cron OR server1:
``` quote
message body 1
```
May 18 20:30:02 - abc - cron OR server1:
``` quote
message body 2
```
May 18 20:30:02 - abc - cron OR server1:
``` quote
message body 3
```
May 18 20:30:02 - abc - cron OR server1:
``` quote
message body 4
```
[See more](https://papertrailapp.com/searches/42)
""".strip()

        self.send_and_test_stream_message('long_post', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_incorrect_message(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.send_and_test_stream_message('incorrect_post', '', '',
                                              content_type="application/x-www-form-urlencoded")

        self.assertIn("Missing expected keys", e.exception.args[0])

    def get_body(self, fixture_name: str) -> str:
        # Papertrail webhook sends a POST request with payload parameter
        # containing the JSON body. Documented here:
        # https://help.papertrailapp.com/kb/how-it-works/web-hooks#encoding
        body = self.webhook_fixture_data("papertrail", fixture_name, file_type="json")
        return urlencode({'payload': body})

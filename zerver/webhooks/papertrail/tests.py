from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class PapertrailHookTests(WebhookTestCase):
    STREAM_NAME = 'papertrail'
    URL_TEMPLATE = "/api/v1/external/papertrail?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'papertrail'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_short_message(self) -> None:
        expected_subject = u"logs"
        expected_message = u'''**"Important stuff"** search found **2** matches - https://papertrailapp.com/searches/42
```
May 18 20:30:02 abc cron OR server1:
  message body
May 18 20:30:02 server1 cron OR server1:
  A short event
```'''

        # use fixture named papertrail_logs
        self.send_and_test_stream_message('short_post', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_long_message(self) -> None:
        expected_subject = u"logs"
        expected_message = u'''**"Important stuff"** search found **5** matches - https://papertrailapp.com/searches/42
```
May 18 20:30:02 abc cron OR server1:
  message body 1
May 18 20:30:02 abc cron OR server1:
  message body 2
May 18 20:30:02 abc cron OR server1:
  message body 3
May 18 20:30:02 abc cron OR server1:
  message body 4
```
[See more](https://papertrailapp.com/searches/42)'''
        # use fixture named papertrail_logs
        self.send_and_test_stream_message('long_post', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("papertrail", fixture_name, file_type="json")

# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.test_classes import WebhookTestCase

class HelloWorldHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'hello'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self):
        # type: () -> None
        expected_subject = u"Hello World"
        expected_message = u"Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**"

        # use fixture named helloworld_hello
        self.send_and_test_stream_message('hello', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_goodbye_message(self):
        # type: () -> None
        expected_subject = u"Hello World"
        expected_message = u"Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        # use fixture named helloworld_goodbye
        self.send_and_test_stream_message('goodbye', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        # type: (Text) -> Text
        return self.fixture_data("helloworld", fixture_name, file_type="json")

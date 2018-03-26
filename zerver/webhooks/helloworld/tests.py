# -*- coding: utf-8 -*-
from django.conf import settings
from typing import Text

from zerver.lib.test_classes import WebhookTestCase
from zerver.models import get_system_bot

class HelloWorldHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}&stream={stream}"
    PM_URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'hello'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self) -> None:
        expected_subject = u"Hello World"
        expected_message = u"Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**"

        # use fixture named helloworld_hello
        self.send_and_test_stream_message('hello', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_goodbye_message(self) -> None:
        expected_subject = u"Hello World"
        expected_message = u"Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        # use fixture named helloworld_goodbye
        self.send_and_test_stream_message('goodbye', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_pm_to_bot_owner(self) -> None:
        # Note that this is really just a test for check_send_webhook_message
        self.URL_TEMPLATE = self.PM_URL_TEMPLATE
        self.url = self.build_webhook_url()
        expected_message = u"Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        self.send_and_test_private_message('goodbye', expected_message=expected_message,
                                           content_type="application/x-www-form-urlencoded")

    def test_stream_error_pm_to_bot_owner(self) -> None:
        # Note taht this is really just a test for check_send_webhook_message
        self.STREAM_NAME = 'nonexistent'
        self.url = self.build_webhook_url()
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT)
        expected_message = "Hi there! We thought you'd like to know that your bot **Zulip Webhook Bot** just tried to send a message to stream `nonexistent`, but that stream does not yet exist. To create it, click the gear in the left-side stream list."
        self.send_and_test_private_message('goodbye', expected_message=expected_message,
                                           content_type='application/x-www-form-urlencoded',
                                           sender=notification_bot)

    def test_custom_topic(self) -> None:
        # Note that this is really just a test for check_send_webhook_message
        expected_subject = u"Custom Topic"
        self.url = self.build_webhook_url(topic=expected_subject)
        expected_message = u"Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        self.send_and_test_stream_message('goodbye', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("helloworld", fixture_name, file_type="json")

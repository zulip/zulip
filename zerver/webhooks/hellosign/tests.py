# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class HelloSignHookTests(WebhookTestCase):
    STREAM_NAME = 'hellosign'
    URL_TEMPLATE = "/api/v1/external/hellosign?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'hellosign'

    def test_signatures_message(self) -> None:
        expected_subject = "NDA with Acme Co."
        expected_message = ("The NDA with Acme Co. is awaiting the signature of "
                            "Jack and was just signed by Jill.")
        self.send_and_test_stream_message('signatures', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_signatures_message_with_own_subject(self) -> None:
        expected_subject = "Our own subject."
        self.url = self.build_webhook_url(topic=expected_subject)
        expected_message = ("The NDA with Acme Co. is awaiting the signature of "
                            "Jack and was just signed by Jill.")
        self.send_and_test_stream_message('signatures_with_own_subject', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded", topic=expected_subject)

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("hellosign", fixture_name, file_type="json")

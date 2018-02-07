# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

# Tests for the Desk.com webhook integration.
#
# The stream name must be provided in the url-encoded test fixture data,
# and must match STREAM_NAME set here.
#
# Example:
#
# stream=deskdotcom&topic=static%20text%20notification&data=This%20is%20a%20custom%20action.
#

class DeskDotComHookTests(WebhookTestCase):
    STREAM_NAME = 'deskdotcom'
    URL_TEMPLATE = "/api/v1/external/deskdotcom"
    FIXTURE_DIR_NAME = 'deskdotcom'

    def test_static_text_message(self) -> None:

        expected_subject = "static text notification"
        expected_message = "This is a custom action."

        self.api_stream_message(self.TEST_USER_EMAIL, 'static_text', expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_case_updated_message(self) -> None:
        expected_subject = "case updated notification"
        expected_message = ("Case 2 updated. "
                            "Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
                            "I have a question</a>")

        self.api_stream_message(self.TEST_USER_EMAIL, 'case_updated', expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_unicode_text_italian(self) -> None:

        expected_subject = "case updated notification"
        expected_message = ("Case 2 updated. "
                            "Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
                            "Il mio hovercraft è pieno di anguille.</a>")

        self.api_stream_message(self.TEST_USER_EMAIL, 'unicode_text_italian', expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_unicode_text_japanese(self) -> None:

        expected_subject = "case updated notification"
        expected_message = ("Case 2 updated. "
                            "Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
                            "私のホバークラフトは鰻でいっぱいです</a>")

        self.api_stream_message(self.TEST_USER_EMAIL, 'unicode_text_japanese', expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("deskdotcom", fixture_name, file_type="txt")

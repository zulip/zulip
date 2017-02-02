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

    def test_static_text_message(self):
        # type: () -> None

        expected_subject = u"static text notification"
        expected_message = u"This is a custom action."

        self.send_and_test_stream_message('static_text', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_case_updated_message(self):
        # type: () -> None
        expected_subject = u"case updated notification"
        expected_message = (u"Case 2 updated. "
                            u"Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
                            u"I have a question</a>")

        self.send_and_test_stream_message('case_updated', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_unicode_text_italian(self):
        # type: () -> None

        expected_subject = u"case updated notification"
        expected_message = (u"Case 2 updated. "
                            u"Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
                            u"Il mio hovercraft è pieno di anguille.</a>")

        self.send_and_test_stream_message('unicode_text_italian', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_unicode_text_japanese(self):
        # type: () -> None

        expected_subject = u"case updated notification"
        expected_message = (u"Case 2 updated. "
                            u"Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
                            u"私のホバークラフトは鰻でいっぱいです</a>")

        self.send_and_test_stream_message('unicode_text_japanese', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def get_body(self, fixture_name):
        # type: (Text) -> Text
        return self.fixture_data("deskdotcom", fixture_name, file_type="txt")

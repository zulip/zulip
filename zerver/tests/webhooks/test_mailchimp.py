from typing import Text
from zerver.lib.test_classes import WebhookTestCase
class MailChimpHookTests(WebhookTestCase):
    STREAM_NAME = 'mailchimp'
    URL_TEMPLATE = "/api/v1/external/mailchimp?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'unsubscribe'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self):
        # type: () -> None
        expected_subject = u"[2016-12-02 12:20:11]|unsubscribed|noahcristino@yahoo.com";
        expected_message = u"Noah Cristino (noahcristino@yahoo.com) unsubscribed!";

        # use fixture named helloworld_hello
        self.send_and_test_stream_message('unsubscribe', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        # type: (text_type) -> text_type
        return self.fixture_data('mailchimp', fixture_name, file_type="json")

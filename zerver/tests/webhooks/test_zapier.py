from zerver.lib.test_classes import WebhookTestCase


class ZapierHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/zapier?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'zapier'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self):
        # type: () -> None
        expected_subject = u"Weather Update"
        expected_message = u"Good Morning! Here is your weather update for the day\nFoggy in the morning. Minimium and Maximum expected temperature to be 16.21 and 26.99 respectively"

        self.send_and_test_stream_message('weather', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        # type: (Text) -> Text
        return self.fixture_data("zapier", fixture_name, file_type="json")
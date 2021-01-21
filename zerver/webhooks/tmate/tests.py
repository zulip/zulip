from zerver.lib.test_classes import WebhookTestCase


class TmateHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/tmate?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'tmate'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self) -> None:
        expected_topic = "Hello World";
        expected_message = "Hello! I am happy to be here! :smile: \nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**";

        # use fixture named tmate_hello
        self.check_webhook('session_open', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")

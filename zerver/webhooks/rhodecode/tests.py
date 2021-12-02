from zerver.lib.test_classes import WebhookTestCase

class RhodecodeHookTests(WebhookTestCase):
    STREAM_NAME = "rhodecode"
    URL_TEMPLATE = "/api/v1/external/rhodecode?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "rhodecode"

    def test_push_event_message(self) -> None:
        expected_topic = "Test"
        expected_message = "HELLO JI"
        self.check_webhook("push_hook", expected_topic, expected_message)

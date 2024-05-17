from zerver.lib.test_classes import WebhookTestCase


class ErrBitHookTests(WebhookTestCase):
    CHANNEL_NAME = "errbit"
    URL_TEMPLATE = "/api/v1/external/errbit?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "errbit"

    def test_errbit_error_message(self) -> None:
        expected_topic_name = "ZulipIntegrationTest / ErrbitEnvName"
        expected_message = '[IllegalStateException](https://errbit.example.com/apps/5e1ed1ff1a603f3916f4f0de/problems/5e1fe93e1a603f3916f4f0e3): "Invalid state error" occurred.'
        self.check_webhook("error_message", expected_topic_name, expected_message)

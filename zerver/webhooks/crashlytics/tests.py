from zerver.lib.test_classes import WebhookTestCase


class CrashlyticsHookTests(WebhookTestCase):
    CHANNEL_NAME = "crashlytics"
    URL_TEMPLATE = "/api/v1/external/crashlytics?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "crashlytics"

    def test_crashlytics_verification_message(self) -> None:
        expected_topic_name = "Setup"
        expected_message = "Webhook has been successfully configured."
        self.check_webhook("verification", expected_topic_name, expected_message)

    def test_crashlytics_build_in_success_status(self) -> None:
        expected_topic_name = "123: Issue Title"
        expected_message = (
            "[Issue](http://crashlytics.com/full/url/to/issue) impacts at least 16 device(s)."
        )
        self.check_webhook("issue_message", expected_topic_name, expected_message)

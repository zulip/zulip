from zerver.lib.test_classes import WebhookTestCase


class CrashlyticsHookTests(WebhookTestCase):
    STREAM_NAME = 'crashlytics'
    URL_TEMPLATE = "/api/v1/external/crashlytics?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'crashlytics'

    def test_crashlytics_verification_message(self) -> None:
        expected_topic = "Setup"
        expected_message = "Webhook has been successfully configured."
        self.check_webhook("verification", expected_topic, expected_message)

    def test_crashlytics_build_in_success_status(self) -> None:
        expected_topic = "123: Issue Title"
        expected_message = "[Issue](http://crashlytics.com/full/url/to/issue) impacts at least 16 device(s)."
        self.check_webhook("issue_message", expected_topic, expected_message)

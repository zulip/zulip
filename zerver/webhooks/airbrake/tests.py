from zerver.lib.test_classes import WebhookTestCase


class AirbrakeHookTests(WebhookTestCase):
    CHANNEL_NAME = "airbrake"
    URL_TEMPLATE = "/api/v1/external/airbrake?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "airbrake"

    def test_airbrake_error_message(self) -> None:
        expected_topic_name = "ZulipIntegrationTest"
        expected_message = '[ZeroDivisionError](https://zulip.airbrake.io/projects/125209/groups/1705190192091077626): "Error message from logger" occurred.'
        self.check_webhook("error_message", expected_topic_name, expected_message)

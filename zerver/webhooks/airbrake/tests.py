from zerver.lib.test_classes import WebhookTestCase


class AirbrakeHookTests(WebhookTestCase):
    def test_airbrake_error_message(self) -> None:
        expected_topic_name = "ZulipIntegrationTest"
        expected_message = '[ZeroDivisionError](https://zulip.airbrake.io/projects/125209/groups/1705190192091077626): "Error message from logger" occurred.'
        self.check_webhook("error_message", expected_topic_name, expected_message)

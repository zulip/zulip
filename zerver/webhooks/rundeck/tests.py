from zerver.lib.test_classes import WebhookTestCase


class RundeckHookTests(WebhookTestCase):
    STREAM_NAME = "Rundeck"
    URL_TEMPLATE = "/api/v1/external/rundeck?&api_key={api_key}"
    WEBHOOK_DIR_NAME = "rundeck"

    def test_start_message(self) -> None:
        expected_topic = "alerts"
        expected_message = "**Global Log Filter Usage** - STARTED - [E12](https://rundeck.com/project/MyProject/execution/follow/12)"

        self.check_webhook(
            "start",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_success_message(self) -> None:
        expected_topic = "alerts"
        expected_message = "**Global Log Filter Usage** - SUCCEEDED - [E12](https://rundeck.com/project/MyProject/execution/follow/12)"

        self.check_webhook(
            "success",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_failure_message(self) -> None:
        expected_topic = "alerts"
        expected_message = "**Global Log Filter Usage** - FAILED - [E13](https://rundeck.com/project/MyProject/execution/follow/13)"

        self.check_webhook(
            "failure",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_duration_message(self) -> None:
        expected_topic = "alerts"
        expected_message = "**Global Log Filter Usage** - RUNNING LONG - [E13](https://rundeck.com/project/MyProject/execution/follow/13)"

        self.check_webhook(
            "duration",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

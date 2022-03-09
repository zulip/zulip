from zerver.lib.test_classes import WebhookTestCase


class RundeckHookTests(WebhookTestCase):
    STREAM_NAME = "Rundeck"
    TOPIC_NAME = "Global Log Filter Usage"
    URL_TEMPLATE = "/api/v1/external/rundeck?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "rundeck"

    def test_start_message(self) -> None:
        expected_message = "Job Execution [STARTED](https://rundeck.com/project/myproject/execution/follow/12) :running:"

        self.check_webhook(
            "start",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_success_message(self) -> None:
        expected_message = "Job Execution [SUCCEEDED](https://rundeck.com/project/myproject/execution/follow/12) :check:"

        self.check_webhook(
            "success",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_failure_message(self) -> None:
        expected_message = "Job Execution [FAILED](https://rundeck.com/project/myproject/execution/follow/13) :cross_mark:"

        self.check_webhook(
            "failure",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_duration_message(self) -> None:
        expected_message = "Job Execution [RUNNING LONG](https://rundeck.com/project/myproject/execution/follow/13) :time_ticking:"

        self.check_webhook(
            "duration",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

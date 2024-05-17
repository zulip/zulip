from zerver.lib.test_classes import WebhookTestCase


class RundeckHookTests(WebhookTestCase):
    CHANNEL_NAME = "Rundeck"
    TOPIC_NAME = "Global Log Filter Usage"
    URL_TEMPLATE = "/api/v1/external/rundeck?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "rundeck"

    def test_start_message(self) -> None:
        expected_message = "[Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#3](http://localhost:4440/project/welcome-project-community/execution/show/3) for welcome-project-community has started. :running:"

        self.check_webhook(
            "start",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_success_message(self) -> None:
        expected_message = "[Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#3](http://localhost:4440/project/welcome-project-community/execution/show/3) for welcome-project-community has succeeded. :check:"

        self.check_webhook(
            "success",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_failure_message(self) -> None:
        expected_message = "[Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#7](http://localhost:4440/project/welcome-project-community/execution/show/7) for welcome-project-community has failed. :cross_mark:"

        self.check_webhook(
            "failure",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_duration_message(self) -> None:
        expected_message = "[Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#6](http://localhost:4440/project/welcome-project-community/execution/show/6) for welcome-project-community is running long. :time_ticking:"

        self.check_webhook(
            "duration",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_scheduled_start_message(self) -> None:
        expected_message = "[Global Log Filter Usage](https://rundeck.com/project/myproject/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#12](https://rundeck.com/project/myproject/execution/follow/12) for myproject has started. :running:"

        self.check_webhook(
            "scheduled_start",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

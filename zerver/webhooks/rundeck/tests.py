from unittest.mock import patch

import orjson

from zerver.lib.test_classes import WebhookTestCase


class RundeckHookTests(WebhookTestCase):
    TOPIC_NAME = "welcome-project-community - Global Log Filter Usage"

    def test_start_message(self) -> None:
        expected_message = ":running: [Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#3](http://localhost:4440/project/welcome-project-community/execution/show/3) for welcome-project-community has started."

        self.check_webhook(
            "start",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_success_message(self) -> None:
        expected_message = ":check: [Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#3](http://localhost:4440/project/welcome-project-community/execution/show/3) for welcome-project-community has succeeded."

        self.check_webhook(
            "success",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_failure_message(self) -> None:
        expected_message = ":warning: [Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#7](http://localhost:4440/project/welcome-project-community/execution/show/7) for welcome-project-community has failed."

        self.check_webhook(
            "failure",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_duration_message(self) -> None:
        expected_message = ":time_ticking: [Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#6](http://localhost:4440/project/welcome-project-community/execution/show/6) for welcome-project-community is running long."

        self.check_webhook(
            "duration",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_scheduled_start_message(self) -> None:
        expected_message = ":clock: [Global Log Filter Usage](https://rundeck.com/project/myproject/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#12](https://rundeck.com/project/myproject/execution/follow/12) for welcome-project-community is scheduled."

        self.check_webhook(
            "scheduled_start",
            RundeckHookTests.TOPIC_NAME,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_message_with_custom_status(self) -> None:
        def custom_get_payload(fixture_name: str) -> str:
            payload = orjson.loads(self.webhook_fixture_data(self.webhook_dir_name, fixture_name))
            payload["status"] = "other"
            payload["execution"]["status"] = "other"
            payload["execution"]["customStatus"] = "waiting for approval"
            return orjson.dumps(payload).decode()

        expected_message = "[Global Log Filter Usage](http://localhost:4440/project/welcome-project-community/job/show/a0296d93-4b10-48d7-8b7d-86ad3f603b85) execution [#7](http://localhost:4440/project/welcome-project-community/execution/show/7) for welcome-project-community has status: waiting for approval."

        with patch.object(self, "get_payload", side_effect=custom_get_payload):
            self.check_webhook(
                "failure",
                RundeckHookTests.TOPIC_NAME,
                expected_message,
                content_type="application/x-www-form-urlencoded",
            )

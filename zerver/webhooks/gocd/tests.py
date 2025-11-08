from zerver.lib.test_classes import WebhookTestCase


class GocdHookTests(WebhookTestCase):
    CHANNEL_NAME = "gocd"
    URL_TEMPLATE = "/api/v1/external/gocd?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "gocd"

    def test_building_pipeline(self) -> None:
        expected_topic = "Pipeline / Stage"
        expected_message = """**Pipeline building**: Pipeline / Stage
- **Commit**: [`59f3c6e4540`](https://github.com/swayam0322/Test/commit/59f3c6e4540) on branch `main`
- **Started**: Feb 1, 2024, 1:58:13 AM"""

        self.check_webhook(
            "pipeline_building",
            expected_topic,
            expected_message,
        )

    def test_completed_pipeline_success(self) -> None:
        expected_topic = "Pipeline / Stage"
        expected_message = """:green_circle: **Build passed**: Pipeline / Stage
- **Commit**: [`59f3c6e4540`](https://github.com/swayam0322/Test/commit/59f3c6e4540) on branch `main`
- **Started**: Feb 1, 2024, 1:58:13 AM
- **Finished**: Feb 1, 2024, 1:58:40 AM
- **Passed**: `Job`"""

        self.check_webhook("pipeline_passed", expected_topic, expected_message)

    def test_completed_pipeline_fail(self) -> None:
        expected_topic = "pipeline-one / stage-two"
        expected_message = """:red_circle: **Build failed**: pipeline-one / stage-two
- **Commit**: [`963eb239c7b`](https://github.com/PieterCK/getting-started-repo.git/commit/963eb239c7b) on branch `master`
- **Started**: Aug 28, 2024, 9:30:19 PM
- **Finished**: Aug 28, 2024, 9:31:00 PM
- **Failed**: `task-two`"""
        self.check_webhook("pipeline_failed", expected_topic, expected_message)

    def test_completed_pipeline_with_mixed_result(self) -> None:
        expected_topic = "test-pipeline / backend-tests"
        expected_message = """:red_circle: **Build failed**: test-pipeline / backend-tests
- **Commit**: [`963eb239c7b`](https://github.com/PieterCK/getting-started-repo.git/commit/963eb239c7b) on branch `master`
- **Started**: Aug 29, 2024, 3:59:18 PM
- **Finished**: Aug 29, 2024, 4:00:15 PM
- **Failed**: `check-backend-lints`, `test-frontend-js`
- **Passed**: `check-backend-tests`, `zulip-ci-debian-12`"""
        self.check_webhook("pipeline_with_mixed_job_result", expected_topic, expected_message)

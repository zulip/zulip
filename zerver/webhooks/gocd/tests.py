from zerver.lib.test_classes import WebhookTestCase


class GocdHookTests(WebhookTestCase):
    STREAM_NAME = "gocd"
    URL_TEMPLATE = "/api/v1/external/gocd?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "gocd"
    TOPIC = "Pipeline / Stage"

    def test_gocd_message(self) -> None:
        expected_message = """**Build** Pipeline/Stage: Passed :thumbs_up:.
- **Commit**: Triggered on [`59f3c6e4540`](https://github.com/swayam0322/Test/commit/59f3c6e4540) on branch `main`.
- **Started**: Feb 1, 2024, 1:58:13 AM
- **Finished**: Feb 1, 2024, 1:58:40 AM"""

        self.check_webhook(
            "pipeline",
            self.TOPIC,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_gocd_build(self) -> None:
        expected_message = """**Pipeline** Pipeline/Stage: Building.
- **Commit**: Triggered on [`59f3c6e4540`](https://github.com/swayam0322/Test/commit/59f3c6e4540) on branch `main`.
- **Started**: Feb 1, 2024, 1:58:13 AM"""

        self.check_webhook(
            "pipeline_build",
            self.TOPIC,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

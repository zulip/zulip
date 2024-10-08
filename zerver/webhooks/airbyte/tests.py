from zerver.lib.test_classes import WebhookTestCase


class AirbyteHookTests(WebhookTestCase):
    STREAM_NAME = "airbyte"
    URL_TEMPLATE = "/api/v1/external/airbyte?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "airbyte"
    CHANNEL_NAME = "test"
    WEBHOOK_DIR_NAME = "airbyte"

    def test_airbyte_job_success(self) -> None:
        expected_topic = "Workspace1 - Connection - Source - Destination"
        expected_message = (
            "Job 9988 succeeded in 1 hours 0 min. Bytes Emitted: 1000 B, Bytes Committed: 90 B. "
            "Records Emitted: 89, Records Committed: 89. Started at: 2024-01-01T00:00:00Z, Finished at: 2024-01-01T01:00:00Z. "
            "Bytes Emitted: 1000, Bytes Committed: 1000. Duration In Seconds: 3600"
        )

        self.check_webhook(
            "job_success",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_airbyte_job_failure(self) -> None:
        expected_topic = "Workspace1 - Connection - Source - Destination"
        expected_message = (
            "Job 9988 failed with error: Connection timeout while trying to sync data."
        )

        self.check_webhook(
            "job_failure",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

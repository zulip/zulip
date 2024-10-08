from zerver.lib.test_classes import WebhookTestCase


class AirbyteHookTests(WebhookTestCase):
    STREAM_NAME = "airbyte"
    URL_TEMPLATE = "/api/v1/external/airbyte?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "airbyte"
    CHANNEL_NAME = "test"
    WEBHOOK_DIR_NAME = "airbyte"

    def test_airbyte_job_success(self) -> None:
        expected_topic = "Workspace1 - Connection - PostgreSQL - BigQuery"
        expected_message = (
            "**Job 9988 succeeded** in 1 hours 0 min.\n\n"
            "**Details:**\n"
            "* **Source:** PostgreSQL\n"
            "* **Destination:** BigQuery\n"
            "* **Bytes Emitted:** 1000 B\n"
            "* **Bytes Committed:** 90 B\n"
            "* **Records Emitted:** 89\n"
            "* **Records Committed:** 89"
        )

        self.check_webhook(
            "job_success",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_airbyte_job_failure(self) -> None:
        expected_topic = "Workspace1 - Connection - PostgreSQL - BigQuery"
        expected_message = (
            "**Job 9988 failed.**\n"
            "* **Error Message:** Connection timeout while trying to sync data"
        )

        self.check_webhook(
            "job_failure",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

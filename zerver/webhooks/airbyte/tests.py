from zerver.lib.test_classes import WebhookTestCase


class AirbyteHookTests(WebhookTestCase):
    STREAM_NAME = "airbyte"
    URL_TEMPLATE = "/api/v1/external/airbyte?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "airbyte"
    CHANNEL_NAME = "test"
    WEBHOOK_DIR_NAME = "airbyte"

    def test_airbyte_job_success(self) -> None:
        expected_topic = "Workspace1 - Connection - PostgreSQL - BigQuery"

        expected_message = """Airbyte job 9988 **succeeded** in 1 hours 0 min.

Connection: [Connection](https://link/to/connection)
**Details:**
* **Source:** [PostgreSQL](https://link/to/source)
* **Destination:** [BigQuery](https://link/to/destination)
* **Records:** 89 emitted, 89 committed
* **Bytes:** 1000 B emitted, 90 B committed"""

        self.check_webhook(
            "airbyte_job_payload_success",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_airbyte_job_failure(self) -> None:
        expected_topic = "Workspace1 - Connection - PostgreSQL - BigQuery"
        expected_message = """Airbyte job 9988 **failed** in 1 hours 0 min.

Connection: [Connection](https://link/to/connection)
**Details:**
* **Source:** [PostgreSQL](https://link/to/source)
* **Destination:** [BigQuery](https://link/to/destination)
* **Records:** 89 emitted, 89 committed
* **Bytes:** 1000 B emitted, 90 B committed
* **Error message:** Connection timeout while trying to sync data"""

        self.check_webhook(
            "airbyte_job_payload_failure",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

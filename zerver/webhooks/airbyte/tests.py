from zerver.lib.test_classes import WebhookTestCase


class AirbyteHookTests(WebhookTestCase):
    STREAM_NAME = "airbyte"
    URL_TEMPLATE = "/api/v1/external/airbyte?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "airbyte"
    CHANNEL_NAME = "test"
    WEBHOOK_DIR_NAME = "airbyte"

    def test_airbyte_job_success(self) -> None:
        expected_topic = "Zulip Airbyte Integration - Google Sheets → Postgres"

        expected_message = """:green_circle: Airbyte sync **succeeded** for [Google Sheets → Postgres](https://cloud.airbyte.com/workspaces/84d2dd6e-82aa-406e-91f3-bf8dbf176e69/connections/aa941643-07ea-48a2-9035-024575491720).


* **Source:** [Google Sheets](https://cloud.airbyte.com/workspaces/84d2dd6e-82aa-406e-91f3-bf8dbf176e69/source/363c0ea3-e989-4051-9f54-d41b794d6621)
* **Destination:** [Postgres](https://cloud.airbyte.com/workspaces/84d2dd6e-82aa-406e-91f3-bf8dbf176e69/destination/b3a05072-e3c8-435a-8e6e-4a5c601039c6)
* **Records:** 1400 emitted, 1400 committed
* **Bytes:** 281 kB emitted, 281 kB committed
* **Duration:** 1 min 23 sec"""

        self.check_webhook(
            "airbyte_job_payload_success",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_airbyte_job_failure(self) -> None:
        expected_topic = "Zulip Airbyte Integration - Google Sheets → Postgres"
        expected_message = """:red_circle: Airbyte sync **failed** for [Google Sheets → Postgres](https://cloud.airbyte.com/workspaces/84d2dd6e-82aa-406e-91f3-bf8dbf176e69/connections/aa941643-07ea-48a2-9035-024575491720).


* **Source:** [Google Sheets](https://cloud.airbyte.com/workspaces/84d2dd6e-82aa-406e-91f3-bf8dbf176e69/source/363c0ea3-e989-4051-9f54-d41b794d6621)
* **Destination:** [Postgres](https://cloud.airbyte.com/workspaces/84d2dd6e-82aa-406e-91f3-bf8dbf176e69/destination/b3a05072-e3c8-435a-8e6e-4a5c601039c6)
* **Records:** 0 emitted, 0 committed
* **Bytes:** 0 B emitted, 0 B committed
* **Duration:** 28 sec

**Error message:** Checking source connection failed - please review this connection's configuration to prevent future syncs from failing"""

        self.check_webhook(
            "airbyte_job_payload_failure",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_airbyte_job_hello_world_success(self) -> None:
        expected_topic = "Airbyte notification"
        expected_message = """Hello World! This is a test from Airbyte to try slack notification settings for sync successes."""

        self.check_webhook(
            "test_airbyte_job_hello_world_success",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_airbyte_job_hello_world_failure(self) -> None:
        expected_topic = "Airbyte notification"
        expected_message = """Hello World! This is a test from Airbyte to try slack notification settings for sync failures."""

        self.check_webhook(
            "test_airbyte_job_hello_world_failure",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

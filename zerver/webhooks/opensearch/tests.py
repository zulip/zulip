from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class OpensearchHookTests(WebhookTestCase):
    CHANNEL_NAME = "Opensearch Alerts"
    TOPIC_NAME = "subject"
    URL_TEMPLATE = "/api/v1/external/opensearch?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "opensearch"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.url = self.build_webhook_url(topic=self.TOPIC_NAME)

    @override
    def get_body(self, fixture_name: str) -> str:
        body = self.webhook_fixture_data(self.WEBHOOK_DIR_NAME, fixture_name, file_type="txt")
        return body

    def test_test_notification(self) -> None:
        message = "Test message content body for config id Uz5bK5UBeE4fYdADfbg0"
        self.check_webhook("test", self.TOPIC_NAME, message, content_type="text/plain")

    def test_alert_notification(self) -> None:
        message = (
            "Monitor Storage size monitor just entered alert status. Please investigate the issue.\n"
            "- Trigger: Storage size over 1TB\n"
            "- Severity: 1\n"
            "- Period start: 2025-02-25T00:58:39.607Z UTC\n"
            "- Period end: 2025-02-25T00:59:39.607Z UTC"
        )
        self.check_webhook("alert", self.TOPIC_NAME, message, content_type="text/plain")

from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class OpensearchHookTests(WebhookTestCase):
    TOPIC_NAME = "OpenSearch alerts"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.url = self.build_webhook_url()

    @override
    def get_body(self, fixture_name: str) -> str:
        body = self.webhook_fixture_data(self.webhook_dir_name, fixture_name, file_type="txt")
        return body

    def test_test_notification_from_channel(self) -> None:
        """
        Tests the message template that OpenSearch uses for
        test-notifications when setting up the webhook.
        """
        message = "Test message content body for config id Uz5bK5UBeE4fYdADfbg0"
        self.check_webhook("test_notification", self.TOPIC_NAME, message, content_type="text/plain")

    def test_test_notification_from_monitor_action(self) -> None:
        """Tests the default message template provided by OpenSearch."""
        message = (
            "Monitor Storage size monitor just entered alert status. Please investigate the issue.\n"
            "- Trigger: Storage size over 1TB\n"
            "- Severity: 1\n"
            "- Period start: 2025-02-25T00:58:39.607Z\n"
            "- Period end: 2025-02-25T00:59:39.607Z"
        )
        self.check_webhook("default_template", self.TOPIC_NAME, message, content_type="text/plain")

    def test_example_template_notification(self) -> None:
        """
        Tests the copyable example message template we provide in the integration documentation.
        """
        message = "Alert of severity **3** triggered by **Insufficient memory**."
        expected_topic = "Resource Monitor"
        self.check_webhook("example_template", expected_topic, message, content_type="text/plain")

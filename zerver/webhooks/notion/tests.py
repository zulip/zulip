from zerver.lib.test_classes import WebhookTestCase


class NotionWebhookTest(WebhookTestCase):
    def test_verification_request(self) -> None:
        expected_topic = "Verification"
        expected_message = """
Notion webhook has been successfully configured.
Your verification token is: `secret_tMrlL1qK5vuQAh1b6cZGhFChZTSYJlce98V0pYn7yBl`
Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()
        self.check_webhook("verification", expected_topic, expected_message)

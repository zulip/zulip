from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase


class BeeminderHookTests(WebhookTestCase):
    CHANNEL_NAME = "beeminder"
    URL_TEMPLATE = "/api/v1/external/beeminder?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "beeminder"

    @patch("zerver.webhooks.beeminder.view.time.time")
    def test_beeminder_derail(self, time: MagicMock) -> None:
        time.return_value = 1517739100  # 5.6 hours from fixture value
        expected_topic_name = "beekeeper"
        expected_message = """
You are going to derail from goal **gainweight** in **5.6 hours**. You need **+2 in 7 days (60)** to avoid derailing.
* Pledge: **0$** :relieved:
""".strip()

        self.check_webhook(
            "derail",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    @patch("zerver.webhooks.beeminder.view.time.time")
    def test_beeminder_derail_worried(self, time: MagicMock) -> None:
        time.return_value = 1517739100  # 5.6 hours from fixture value
        expected_topic_name = "beekeeper"
        expected_message = """
You are going to derail from goal **gainweight** in **5.6 hours**. You need **+2 in 7 days (60)** to avoid derailing.
* Pledge: **5$** :worried:
""".strip()

        self.check_webhook(
            "derail_worried", expected_topic_name, expected_message, content_type="application/json"
        )

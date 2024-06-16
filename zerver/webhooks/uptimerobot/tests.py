from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import Recipient
from zerver.webhooks.uptimerobot.view import MISCONFIGURED_PAYLOAD_ERROR_MESSAGE


class UptimeRobotHookTests(WebhookTestCase):
    CHANNEL_NAME = "uptimerobot"
    URL_TEMPLATE = "/api/v1/external/uptimerobot?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "uptimerobot"

    def test_uptimerobot_monitor_down(self) -> None:
        """
        Tests if uptimerobot monitor down is handled correctly
        """
        expected_topic_name = "Web Server"
        expected_message = "Web Server (server1.example.com) is DOWN (Host Is Unreachable)."
        self.check_webhook("uptimerobot_monitor_down", expected_topic_name, expected_message)

    def test_uptimerobot_monitor_up(self) -> None:
        """
        Tests if uptimerobot monitor up is handled correctly
        """
        expected_topic_name = "Mail Server"
        expected_message = """
Mail Server (server2.example.com) is back UP (Host Is Reachable).
It was down for 44 minutes and 37 seconds.
""".strip()
        self.check_webhook("uptimerobot_monitor_up", expected_topic_name, expected_message)

    def test_uptimerobot_invalid_payload_with_missing_data(self) -> None:
        """
        Tests if invalid UptimeRobot payloads are handled correctly
        """
        self.url = self.build_webhook_url()
        payload = self.get_body("uptimerobot_invalid_payload_with_missing_data")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_error(result, "Invalid payload")

        expected_message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=self.test_user.full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()

        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)

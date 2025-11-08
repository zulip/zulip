from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.gosquared.view import CHAT_MESSAGE_TEMPLATE


class GoSquaredHookTests(WebhookTestCase):
    CHANNEL_NAME = "gosquared"
    URL_TEMPLATE = "/api/v1/external/gosquared?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "gosquared"

    # Note: Include a test function per each distinct message condition your integration supports
    def test_traffic_message(self) -> None:
        expected_topic_name = "GoSquared - requestb.in"
        expected_message = (
            "[requestb.in](https://www.gosquared.com/now/GSN-595854-T) has 33 visitors online."
        )

        self.check_webhook(
            "traffic_spike",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_chat_message(self) -> None:
        expected_topic_name = "Live chat session - Zulip Chat"
        expected_message = CHAT_MESSAGE_TEMPLATE.format(
            status="visitor",
            name="John Smith",
            content="Zulip is awesome!",
        )

        self.check_webhook(
            "chat_message",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

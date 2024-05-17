from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase

EXPECTED_TOPIC = "Message from Slack"
EXPECTED_MESSAGE = "**slack_user**: test"


class SlackWebhookTests(WebhookTestCase):
    CHANNEL_NAME = "slack"
    URL_TEMPLATE = "/api/v1/external/slack?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "slack"

    def test_slack_only_stream_parameter(self) -> None:
        self.check_webhook(
            "message_info",
            EXPECTED_TOPIC,
            EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_with_user_specified_topic(self) -> None:
        self.url = self.build_webhook_url(topic="test")
        expected_topic_name = "test"
        self.check_webhook(
            "message_info",
            expected_topic_name,
            EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_true(self) -> None:
        self.url = self.build_webhook_url(channels_map_to_topics="1")
        expected_topic_name = "channel: general"
        self.check_webhook(
            "message_info",
            expected_topic_name,
            EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_true_and_user_specified_topic(self) -> None:
        self.url = self.build_webhook_url(topic="test", channels_map_to_topics="1")
        expected_topic_name = "test"
        self.check_webhook(
            "message_info",
            expected_topic_name,
            EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_false(self) -> None:
        self.CHANNEL_NAME = "general"
        self.url = self.build_webhook_url(channels_map_to_topics="0")
        self.check_webhook(
            "message_info",
            EXPECTED_TOPIC,
            EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_false_and_user_specified_topic(self) -> None:
        self.CHANNEL_NAME = "general"
        self.url = self.build_webhook_url(topic="test", channels_map_to_topics="0")
        expected_topic_name = "test"
        self.check_webhook(
            "message_info",
            expected_topic_name,
            EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_missing_data_user_name(self) -> None:
        payload = self.get_body("message_info_missing_user_name")
        url = self.build_webhook_url()
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Missing 'user_name' argument")

    def test_missing_data_channel_name(self) -> None:
        payload = self.get_body("message_info_missing_channel_name")
        url = self.build_webhook_url()
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Missing 'channel_name' argument")

    def test_missing_data_text(self) -> None:
        payload = self.get_body("message_info_missing_text")
        url = self.build_webhook_url()
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Missing 'text' argument")

    def test_invalid_channels_map_to_topics(self) -> None:
        payload = self.get_body("message_info")
        url = self.build_webhook_url(channels_map_to_topics="abc")
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Error: channels_map_to_topics parameter other than 0 or 1")

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("slack", fixture_name, file_type="txt")

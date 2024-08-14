from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase

EXPECTED_TOPIC = "Message from Slack"

MESSAGE_WITH_NORMAL_TEXT = "Hello, this is a normal text message"
USER = "U06NU4E26M9"
CHANNEL = "C06NRA6JLER"
EXPECTED_MESSAGE = "**{user}**: {message}"
TOPIC_WITH_CHANNEL = "channel: {channel}"

LEGACY_USER = "slack_user"


class SlackWebhookTests(WebhookTestCase):
    CHANNEL_NAME = "slack"
    URL_TEMPLATE = "/api/v1/external/slack?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "slack"

    def test_slack_only_stream_parameter(self) -> None:
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_slack_with_user_specified_topic(self) -> None:
        expected_topic_name = "test"
        self.url = self.build_webhook_url(topic=expected_topic_name)
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_slack_channels_map_to_topics_true(self) -> None:
        self.url = self.build_webhook_url(channels_map_to_topics="1")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        expected_topic_name = TOPIC_WITH_CHANNEL.format(channel=CHANNEL)
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_slack_channels_map_to_topics_true_and_user_specified_topic(self) -> None:
        expected_topic_name = "test"
        self.url = self.build_webhook_url(topic=expected_topic_name, channels_map_to_topics="1")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_slack_channels_map_to_topics_false(self) -> None:
        self.CHANNEL_NAME = CHANNEL
        self.url = self.build_webhook_url(channels_map_to_topics="0")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_slack_channels_map_to_topics_false_and_user_specified_topic(self) -> None:
        self.CHANNEL_NAME = CHANNEL
        expected_topic_name = "test"
        self.url = self.build_webhook_url(topic=expected_topic_name, channels_map_to_topics="0")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_invalid_channels_map_to_topics(self) -> None:
        payload = self.get_body("message_with_normal_text")
        url = self.build_webhook_url(channels_map_to_topics="abc")
        result = self.client_post(url, payload, content_type="application/json")
        self.assert_json_error(result, "Error: channels_map_to_topics parameter other than 0 or 1")

    def test_challenge_handshake_payload(self) -> None:
        url = self.build_webhook_url(channels_map_to_topics="1")
        payload = self.get_body("challenge_handshake_payload")
        result = self.client_post(url, payload, content_type="application/json")
        expected_challenge_response = {
            "msg": "",
            "result": "success",
            "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P",
        }

        self.assertJSONEqual(result.content.decode("utf-8"), expected_challenge_response)

    def test_block_message_from_slack_bridge_bot(self) -> None:
        self.check_webhook(
            "message_from_slack_bridge_bot",
            "",
            "",
            content_type="application/json",
            expect_noop=True,
        )

    def test_message_with_bullet_points(self) -> None:
        message_body = "• list three\n• list two"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_bullet_points",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_channel_and_user_mentions(self) -> None:
        # TODO
        pass

    def test_message_with_channel_mentions(self) -> None:
        message_body = "**#zulip-mirror** **#general** message with channel mentions"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_channel_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_formatted_texts(self) -> None:
        message_body = "**Bold text** *italic text* ~~strikethrough~~"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_formatted_texts",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_image_files(self) -> None:
        message_body = """
*[5e44bcbc-e43c-4a2e-85de-4be126f392f4.jpg](https://ds-py62195.slack.com/files/U06NU4E26M9/F079E4173BL/5e44bcbc-e43c-4a2e-85de-4be126f392f4.jpg)*
*[notif_bot.png](https://ds-py62195.slack.com/files/U06NU4E26M9/F079GJ49X4L/notif_bot.png)*
*[books.jpg](https://ds-py62195.slack.com/files/U06NU4E26M9/F07A2TA6PPS/books.jpg)*"""
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_image_files",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_inline_code(self) -> None:
        message_body = "`asdasda this is a code block`"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_inline_code",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_ordered_list(self) -> None:
        message_body = "1. point one\n2. point two\n3. mix both\n4. pour water\n5. etc"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_ordered_list",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_user_mentions(self) -> None:
        # TODO
        message_body = (
            "<@U074VRHQ11T> <@U074G5E1ANR> <@U06NU4E26M9> hello, this is a message with mentions"
        )
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_user_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_variety_files(self) -> None:
        message_body = """Message with an assortment of file types
*[postman-agent-0.4.25-linux-x64.tar.gz](https://ds-py62195.slack.com/files/U06NU4E26M9/F079E4CMY5Q/postman-agent-0.4.25-linux-x64.tar.gz)*
*[discord-0.0.55.deb](https://ds-py62195.slack.com/files/U06NU4E26M9/F079SQ33CBT/discord-0.0.55.deb)*
*[Slack-bot-scopes-List.xlsx](https://ds-py62195.slack.com/files/U06NU4E26M9/F079SQ721A5/slack-bot-scopes-list.xlsx)*
*[wallpaper.jpg](https://ds-py62195.slack.com/files/U06NU4E26M9/F079B7G7NUD/wallpaper.jpg)*
*[TestPDFfile.pdf](https://ds-py62195.slack.com/files/U06NU4E26M9/F07A2TVKNQ0/testpdffile.pdf)*
*[channels.json](https://ds-py62195.slack.com/files/U06NU4E26M9/F07A2TVQ7C0/channels.json)*"""
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_variety_files",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_with_workspace_mentions(self) -> None:
        message_body = "@**all** @**all** Sorry for mentioning. This is for the test fixtures for the Slack integration update PR I'm working on and can't be done in a private channel. :bow:"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_workspace_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_message_from_slack_integration_bot(self) -> None:
        self.check_webhook(
            "message_from_slack_integration_bot",
            "",
            "",
            content_type="application/json",
            expect_noop=True,
        )


class SlackLegacyWebhookTests(WebhookTestCase):
    CHANNEL_NAME = "slack"
    URL_TEMPLATE = "/api/v1/external/slack?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "slack"

    def test_slack_only_stream_parameter(self) -> None:
        expected_topic_name = "Message from Slack"
        expected_message = EXPECTED_MESSAGE.format(user=LEGACY_USER, message="test")
        self.check_webhook(
            "message_info",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_with_user_specified_topic(self) -> None:
        self.url = self.build_webhook_url(topic="test")
        expected_topic_name = "test"
        expected_message = EXPECTED_MESSAGE.format(user=LEGACY_USER, message="test")
        self.check_webhook(
            "message_info",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_true(self) -> None:
        self.url = self.build_webhook_url(channels_map_to_topics="1")
        expected_topic_name = "channel: general"
        expected_message = EXPECTED_MESSAGE.format(user=LEGACY_USER, message="test")
        self.check_webhook(
            "message_info",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_true_and_user_specified_topic(self) -> None:
        self.url = self.build_webhook_url(topic="test", channels_map_to_topics="1")
        expected_topic_name = "test"
        expected_message = EXPECTED_MESSAGE.format(user=LEGACY_USER, message="test")
        self.check_webhook(
            "message_info",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_false(self) -> None:
        self.CHANNEL_NAME = "general"
        self.url = self.build_webhook_url(channels_map_to_topics="0")
        expected_topic_name = "Message from Slack"
        expected_message = EXPECTED_MESSAGE.format(user=LEGACY_USER, message="test")
        self.check_webhook(
            "message_info",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_slack_channels_map_to_topics_false_and_user_specified_topic(self) -> None:
        self.CHANNEL_NAME = "general"
        self.url = self.build_webhook_url(topic="test", channels_map_to_topics="0")
        expected_topic_name = "test"
        expected_message = EXPECTED_MESSAGE.format(user=LEGACY_USER, message="test")
        self.check_webhook(
            "message_info",
            expected_topic_name,
            expected_message,
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

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("slack", fixture_name, file_type="txt")

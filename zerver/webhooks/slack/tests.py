from collections.abc import Callable
from functools import wraps
from typing import Concatenate
from unittest.mock import patch

import responses
from typing_extensions import ParamSpec, override

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.slack.view import INVALID_SLACK_TOKEN_MESSAGE

EXPECTED_TOPIC = "Message from Slack"

MESSAGE_WITH_NORMAL_TEXT = "Hello, this is a normal text message"
USER = "John Doe"
CHANNEL = "general"
API_CHANNEL_NAME = "Slack general"
EXPECTED_MESSAGE = "**{user}**: {message}"
TOPIC_WITH_CHANNEL = "channel: {channel}"
DEFAULT_TOPIC_NAME = "Message from Slack"
LEGACY_USER = "slack_user"

ParamT = ParamSpec("ParamT")


def mock_slack_api_calls(
    test_func: Callable[Concatenate["SlackWebhookTests", ParamT], None],
) -> Callable[Concatenate["SlackWebhookTests", ParamT], None]:
    @wraps(test_func)
    @responses.activate
    def _wrapped(self: "SlackWebhookTests", /, *args: ParamT.args, **kwargs: ParamT.kwargs) -> None:
        self.make_stream(API_CHANNEL_NAME)
        responses.add(
            responses.GET,
            "https://slack.com/api/users.info",
            self.webhook_fixture_data("slack", "slack_users_info_api_response"),
        )
        responses.add(
            responses.GET,
            "https://slack.com/api/conversations.info",
            self.webhook_fixture_data("slack", "slack_conversations_info_api_response"),
        )
        test_func(self, *args, **kwargs)

    return _wrapped


class SlackWebhookTests(WebhookTestCase):
    URL_TEMPLATE = "/api/v1/external/slack?stream={stream}&api_key={api_key}&slack_app_token=xoxp-XXXXXXXXXXXXXXXXXXXXX"

    @mock_slack_api_calls
    def test_slack_only_stream_parameter(self) -> None:
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
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

    @mock_slack_api_calls
    def test_slack_channels_map_to_topics_true(self) -> None:
        self.url = self.build_webhook_url(channels_map_to_topics="1")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        expected_topic_name = TOPIC_WITH_CHANNEL.format(channel=API_CHANNEL_NAME)
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
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

    @mock_slack_api_calls
    def test_slack_channels_map_to_topics_false(self) -> None:
        self.channel_name = API_CHANNEL_NAME
        self.url = self.build_webhook_url(channels_map_to_topics="0")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_url_options_channels_mapping_true(self) -> None:
        self.channel_name = API_CHANNEL_NAME
        self.url = self.build_webhook_url(mapping="channels")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        expected_topic_name = DEFAULT_TOPIC_NAME
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_slack_channels_map_to_topics_false_and_user_specified_topic(self) -> None:
        self.channel_name = API_CHANNEL_NAME
        expected_topic_name = "test"
        self.url = self.build_webhook_url(topic=expected_topic_name, channels_map_to_topics="0")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_url_options_map_to_channels_and_user_specified_topic(self) -> None:
        self.channel_name = API_CHANNEL_NAME
        expected_topic_name = DEFAULT_TOPIC_NAME
        self.url = self.build_webhook_url(topic=expected_topic_name, mapping="channels")
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=MESSAGE_WITH_NORMAL_TEXT)
        self.check_webhook(
            "message_with_normal_text",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_invalid_channels_map_to_topics(self) -> None:
        payload = self.get_body("message_with_normal_text")
        url = self.build_webhook_url(channels_map_to_topics="abc")
        result = self.client_post(url, payload, content_type="application/json")
        self.assert_json_error(result, "Error: channels_map_to_topics parameter other than 0 or 1")

    @mock_slack_api_calls
    def test_challenge_handshake_payload(self) -> None:
        url = self.build_webhook_url(channels_map_to_topics="1")
        payload = self.get_body("challenge_handshake_payload")
        with self.assertLogs(level="INFO") as info_logs:
            result = self.client_post(url, payload, content_type="application/json")
        expected_challenge_response = {
            "msg": "",
            "result": "success",
            "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P",
        }
        self.assertTrue(
            "INFO:root:This is a Slack user token, which grants all rights the user has!"
            in info_logs.output[0]
        )
        self.assertJSONEqual(result.content.decode("utf-8"), expected_challenge_response)

    @mock_slack_api_calls
    def test_block_message_from_slack_bridge_bot(self) -> None:
        self.check_webhook(
            "message_from_slack_bridge_bot",
            "",
            "",
            content_type="application/json",
            expect_noop=True,
        )

    @mock_slack_api_calls
    def test_message_with_bullet_points(self) -> None:
        message_body = "• list three\n• list two"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_bullet_points",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_channel_and_user_mentions(self) -> None:
        message_body = "@**John Doe** **#general** message with both channel and user mentions"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_channel_and_user_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_channel_mentions(self) -> None:
        message_body = "**#zulip-mirror** **#general** message with channel mentions"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_channel_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_formatted_texts(self) -> None:
        message_body = "**Bold text** *italic text* ~~strikethrough~~"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_formatted_texts",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
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

    @mock_slack_api_calls
    def test_message_with_inline_code(self) -> None:
        message_body = "`asdasda this is a code block`"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_inline_code",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_ordered_list(self) -> None:
        message_body = "1. point one\n2. point two\n3. mix both\n4. pour water\n5. etc"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_ordered_list",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_user_mentions(self) -> None:
        message_body = (
            "@**John Doe** @**John Doe** @**John Doe** hello, this is a message with mentions"
        )
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_user_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
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

    @mock_slack_api_calls
    def test_message_with_workspace_mentions(self) -> None:
        message_body = "@**all** @**all** Sorry for mentioning. This is for the test fixtures for the Slack integration update PR I'm working on and can't be done in a private channel. :bow:"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_workspace_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_from_slack_integration_bot(self) -> None:
        self.check_webhook(
            "message_from_slack_integration_bot",
            "",
            "",
            content_type="application/json",
            expect_noop=True,
        )

    @mock_slack_api_calls
    def test_message_with_code_block(self) -> None:
        message_body = """```def is_bot_message(payload: WildValue) -&gt; bool:\n    app_api_id = payload.get(\"api_app_id\").tame(check_none_or(check_string))\n    bot_app_id = (\n        payload.get(\"event\", {})\n        .get(\"bot_profile\", {})\n        .get(\"app_id\")\n        .tame(check_none_or(check_string))\n    )\n    return bot_app_id is not None and app_api_id == bot_app_id```"""
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_code_block",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_complex_formatted_texts(self) -> None:
        message_body = "this is text messages with overlapping formatting\n***bold with italic***\n~~**bold with strike through**~~\n~~*italic with strike through*~~\n~~***all three***~~"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_complex_formatted_texts",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_complex_formatted_mentions(self) -> None:
        message_body = "@**John Doe** **#general** ~~***@**all*****~~"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_complex_formatted_mentions",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_message_with_quote_block(self) -> None:
        message_body = "&gt; This is a quote"
        expected_message = EXPECTED_MESSAGE.format(user=USER, message=message_body)
        self.check_webhook(
            "message_with_quote_block",
            EXPECTED_TOPIC,
            expected_message,
            content_type="application/json",
        )

    @mock_slack_api_calls
    def test_block_slack_retries(self) -> None:
        payload = self.get_body("message_with_normal_text")
        with patch("zerver.webhooks.slack.view.check_send_webhook_message") as m:
            result = self.client_post(
                self.url,
                payload,
                headers={"X-Slack-Retry-Num": 1},
                content_type="application/json",
            )
        self.assertFalse(m.called)
        self.assert_json_success(result)

    @mock_slack_api_calls
    def test_missing_api_token_scope(self) -> None:
        error_message = "Slack token is missing the following required scopes: ['users:read', 'users:read.email']"
        user_facing_error_message = INVALID_SLACK_TOKEN_MESSAGE.format(error_message=error_message)
        # We tested how `check_slack_token_access` may raise these errors in
        # `test_slack_importer.py`. So, for simplicitys sake the function
        # is directly mocked here to raise the ValueError we expect.
        with (
            patch("zerver.webhooks.slack.view.check_slack_token_access") as e,
            patch("zerver.webhooks.slack.view.send_rate_limited_pm_notification_to_bot_owner") as s,
        ):
            e.side_effect = ValueError(error_message)
            self.check_webhook(
                "challenge_handshake_payload",
                expect_noop=True,
                content_type="application/json",
            )

        s.assert_called_once()
        _, _, actual_error_message = s.call_args[0]

        self.assertEqual(actual_error_message, user_facing_error_message)

    @mock_slack_api_calls
    def test_missing_slack_api_token(self) -> None:
        error_message = "slack_app_token is missing."
        self.url = self.build_webhook_url(slack_app_token="")
        user_facing_error_message = INVALID_SLACK_TOKEN_MESSAGE.format(error_message=error_message)
        with (
            patch("zerver.webhooks.slack.view.send_rate_limited_pm_notification_to_bot_owner") as s,
        ):
            self.check_webhook(
                "challenge_handshake_payload",
                expect_noop=True,
                content_type="application/json",
            )

        s.assert_called_once()
        _, _, actual_error_message = s.call_args[0]

        self.assertEqual(actual_error_message, user_facing_error_message)


class SlackLegacyWebhookTests(WebhookTestCase):
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
        self.channel_name = "general"
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
        self.channel_name = "general"
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

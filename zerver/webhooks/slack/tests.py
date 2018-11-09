# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class SlackWebhookTests(WebhookTestCase):
    STREAM_NAME = 'slack'
    URL_TEMPLATE = "/api/v1/external/slack?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'slack'

    def test_slack_channel_to_topic(self) -> None:

        expected_topic = u"channel: general"
        expected_message = u"**slack_user**: `test\n`"
        self.send_and_test_stream_message('message_info', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_slack_channel_to_stream(self) -> None:

        self.STREAM_NAME = 'general'
        self.url = "{}{}".format(self.url, "&channels_map_to_topics=0")
        expected_topic = u"Message from Slack"
        expected_message = u"**slack_user**: `test\n`"
        self.send_and_test_stream_message('message_info', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_missing_data_user_name(self) -> None:

        payload = self.get_body('message_info_missing_user_name')
        url = self.build_webhook_url()
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Missing 'user_name' argument")

    def test_missing_data_channel_name(self) -> None:

        payload = self.get_body('message_info_missing_channel_name')
        url = self.build_webhook_url()
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Missing 'channel_name' argument")

    def test_missing_data_text(self) -> None:

        payload = self.get_body('message_info_missing_text')
        url = self.build_webhook_url()
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Missing 'text' argument")

    def test_invalid_channels_map_to_topics(self) -> None:

        payload = self.get_body('message_info')
        url = "{}{}".format(self.url, "&channels_map_to_topics=abc")
        result = self.client_post(url, payload, content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, 'Error: channels_map_to_topics parameter other than 0 or 1')

    def get_body(self, fixture_name: str) -> str:

        return self.webhook_fixture_data("slack", fixture_name, file_type="txt")

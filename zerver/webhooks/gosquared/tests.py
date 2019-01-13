# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase

from zerver.webhooks.gosquared.view import CHAT_MESSAGE_TEMPLATE

class GoSquaredHookTests(WebhookTestCase):
    STREAM_NAME = 'gosquared'
    URL_TEMPLATE = "/api/v1/external/gosquared?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'gosquared'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_traffic_message(self) -> None:
        expected_topic = "GoSquared - requestb.in"
        expected_message = u"[requestb.in](https://www.gosquared.com/now/GSN-595854-T) has 33 visitors online."

        self.send_and_test_stream_message('traffic_spike', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_chat_message(self) -> None:
        expected_topic = "Live Chat Session - Zulip Chat"
        expected_message = CHAT_MESSAGE_TEMPLATE.format(
            status='visitor',
            name='John Smith',
            content='Zulip is awesome!'
        )

        self.send_and_test_stream_message('chat_message', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("gosquared", fixture_name, file_type="json")

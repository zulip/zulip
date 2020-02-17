# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase


class UptimeRobotHookTests(WebhookTestCase):
    STREAM_NAME = 'uptimerobot'
    TOPIC = "subject"
    URL_TEMPLATE = "/api/v1/external/uptimerobot?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'uptimerobot'

    def setUp(self) -> None:
        super().setUp()
        self.url = self.build_webhook_url(topic=self.TOPIC)

    def test_uptimerobot_monitor_down(self) -> None:
        message = 'ZUTesting (http://7d398dfc.ngrok.io) is DOWN (HTTP 502 - Bad Gateway).'
        self.send_and_test_stream_message("monitor_down", self.TOPIC, message)

    def test_uptimerobot_monitor_up(self) -> None:
        message = 'ZUTesting (http://7d398dfc.ngrok.io) is back UP (HTTP 200 - OK). It was down for 1 minutes and 0 seconds.'
        self.send_and_test_stream_message("monitor_up", self.TOPIC, message)

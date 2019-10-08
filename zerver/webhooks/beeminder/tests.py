# -*- coding: utf-8 -*-
from unittest.mock import patch
from typing import Any
from zerver.lib.test_classes import WebhookTestCase

class BeeminderHookTests(WebhookTestCase):
    STREAM_NAME = 'beeminder'
    URL_TEMPLATE = u"/api/v1/external/beeminder?api_key={api_key}&stream={stream}"

    @patch('zerver.webhooks.beeminder.view.time.time')
    def test_beeminder_derail(self, time: Any) -> None:
        time.return_value = 1517739100  # 5.6 hours from fixture value
        expected_topic = u"beekeeper"
        expected_message = '\n'.join([
            'You are going to derail from goal **gainweight** in **{:0.1f} hours**'.format(5.6),
            ' You need **+2 in 7 days (60)** to avoid derailing',
            ' * Pledge: **0$** :relieved:'
        ])

        self.send_and_test_stream_message('derail',
                                          expected_topic,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    @patch('zerver.webhooks.beeminder.view.time.time')
    def test_beeminder_derail_worried(self, time: Any) -> None:
        time.return_value = 1517739100  # 5.6 hours from fixture value
        expected_topic = u"beekeeper"
        expected_message = '\n'.join([
            'You are going to derail from goal **gainweight** in **{:0.1f} hours**'.format(5.6),
            ' You need **+2 in 7 days (60)** to avoid derailing',
            ' * Pledge: **5$** :worried:'
        ])
        self.send_and_test_stream_message('derail_worried',
                                          expected_topic,
                                          expected_message,
                                          content_type="application/json")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("beeminder", fixture_name, file_type="json")

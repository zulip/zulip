# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase


class GrafanaHookTests(WebhookTestCase):
    STREAM_NAME = 'grafana'
    URL_TEMPLATE = u"/api/v1/external/grafana?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'grafana'

    def test_grafana_notifications_message(self) -> None:
        expected_topic = "My alert: alerting"
        expected_message = "Load peaking!: Load is peaking. Make sure the traffic is real and spin up more webfronts. Please check out the details [here](http://url.to.grafana/db/dashboard/my_dashboard?panelId=2) for the abnormal metrics: requests: 122;"
        self.send_and_test_stream_message('notifications', expected_topic=expected_topic, expected_message=expected_message)

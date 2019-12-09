# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class GrafanaHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/grafana?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'grafana'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_grafana_message(self) -> None:
        expected_topic = "Grafana alert: My alert"
        expected_message = "Rule: **[Load peaking!](http://url.to.grafana/db/dashboard/my_dashboard?panelId=2)**\n"
        expected_message += "Rule ID: 1\n"
        expected_message += "State: alerting\n"
        expected_message += "Message: Load is peaking. Make sure the traffic is real and spin up more webfronts"

        self.send_and_test_stream_message('grafana', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        print(fixture_name)
        return self.webhook_fixture_data("grafana", fixture_name, file_type="json")

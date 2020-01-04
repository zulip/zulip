
from zerver.lib.test_classes import WebhookTestCase

class GrafanaHookTests(WebhookTestCase):
    STREAM_NAME = 'grafana'
    URL_TEMPLATE = "/api/v1/external/grafana?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'grafana'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_standard_response_message(self) -> None:
        expected_topic = u"[alerting]My alert"
        expected_message = u"\nLoad peaking!\nLoad is peaking. Make sure the traffic is real and spin up more webfronts\nFor more information, visit the [dashboard](http://url.to.grafana/db/dashboard/my_dashboard?panelId=2)"

        # use fixture named grafana_standard_response
        self.send_and_test_stream_message('standard_response', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

from zerver.lib.test_classes import WebhookTestCase

class GrafanaHookTests(WebhookTestCase):
    STREAM_NAME = 'grafana'
    URL_TEMPLATE = u"/api/v1/external/grafana?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'grafana'

    def test_message_sample(self) -> None:
        expected_topic = "My alert"
        expected_message = (u"Rule Name : **Load peaking!**\n"
                            u"Current State is `alerting`\n"
                            u"Metric : **requests** and its value is **122**"
                            )

        self.send_and_test_stream_message(
            'sample',
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded"
        )

    def test_message_alert(self) -> None:
        expected_topic = "[OK] Panel Title alert"
        expected_message = (u"Rule Name : **Panel Title alert**\n"
                            u"Current State is `ok`\n"
                            u"Metric : **A-series** and its value is **58.12**\n"
                            u"Metric : **B-series** and its value is **10000**"
                            )

        self.send_and_test_stream_message(
            'alert',
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded"
        )

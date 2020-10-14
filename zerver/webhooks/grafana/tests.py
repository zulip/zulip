from zerver.lib.test_classes import WebhookTestCase


class GrafanaHookTests(WebhookTestCase):
    STREAM_NAME = 'grafana'
    URL_TEMPLATE = "/api/v1/external/grafana?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'grafana'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_alert(self) -> None:
        expected_topic = "[Alerting] Test notification"
        expected_message = """
[Test rule](http://localhost:3000/)

Someone is testing the alert notification within grafana.

**High value:** 100
**Higher Value:** 200

[Click to view visualization](https://grafana.com/assets/img/blog/mixed_styles.png)
""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "alert",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_no_data_alert(self) -> None:
        expected_topic = "[Alerting] No Data alert"
        expected_message = """
[No Data alert](http://localhost:3000/d/GG2qhR3Wz/alerttest?fullscreen&edit&tab=alert&panelId=6&orgId=1)

The panel has no data.

""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "no_data_alert",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_no_message_alert(self) -> None:
        expected_topic = "[Alerting] No Message alert"
        expected_message = """
[No Message alert](http://localhost:3000/d/GG2qhR3Wz/alerttest?fullscreen&edit&tab=alert&panelId=8&orgId=1)

**A-series:** 21.573108436586445
""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "no_message_alert",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

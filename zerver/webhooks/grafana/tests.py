from zerver.lib.test_classes import WebhookTestCase


class GrafanaHookTests(WebhookTestCase):
    STREAM_NAME = "grafana"
    URL_TEMPLATE = "/api/v1/external/grafana?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "grafana"

    # Note: Include a test function per each distinct message condition your integration supports
    def test_alert(self) -> None:
        expected_topic_name = "[Alerting] Test notification"
        expected_message = """
:alert: **ALERTING**

[Test rule](http://localhost:3000/)

Someone is testing the alert notification within grafana.

**High value:** 100
**Higher Value:** 200

[Click to view visualization](https://grafana.com/assets/img/blog/mixed_styles.png)
""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "alert",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_no_data_alert(self) -> None:
        expected_topic_name = "[Alerting] No Data alert"
        expected_message = """
:alert: **ALERTING**

[No Data alert](http://localhost:3000/d/GG2qhR3Wz/alerttest?fullscreen&edit&tab=alert&panelId=6&orgId=1)

The panel has no data.

""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "no_data_alert",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_no_message_alert(self) -> None:
        expected_topic_name = "[Alerting] No Message alert"
        expected_message = """
:alert: **ALERTING**

[No Message alert](http://localhost:3000/d/GG2qhR3Wz/alerttest?fullscreen&edit&tab=alert&panelId=8&orgId=1)

**A-series:** 21.573108436586445
""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "no_message_alert",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # Note: Include a test function per each distinct message condition your integration supports
    def test_alert_ok(self) -> None:
        expected_topic_name = "[Ok] Test notification"
        expected_message = """
:squared_ok: **OK**

[Test rule](http://localhost:3000/)

Someone is testing the alert notification within grafana.

**High value:** 0

[Click to view visualization](https://grafana.com/assets/img/blog/mixed_styles.png)
""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "alert_ok",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # Note: Include a test function per each distinct message condition your integration supports
    def test_alert_paused(self) -> None:
        expected_topic_name = "[Paused] Test notification"
        expected_message = """
:info: **PAUSED**

[Test rule](http://localhost:3000/)

Someone is testing the alert notification within grafana.


[Click to view visualization](https://grafana.com/assets/img/blog/mixed_styles.png)
""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "alert_paused",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # Note: Include a test function per each distinct message condition your integration supports
    def test_alert_pending(self) -> None:
        expected_topic_name = "[Pending] Test notification"
        expected_message = """
:info: **PENDING**

[Test rule](http://localhost:3000/)

Someone is testing the alert notification within grafana.

**High value:** 100
**Higher Value:** 200

[Click to view visualization](https://grafana.com/assets/img/blog/mixed_styles.png)
""".strip()

        # use fixture named helloworld_hello
        self.check_webhook(
            "alert_pending",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_alert_new(self) -> None:
        expected_topic_name = "[TestAlert]"
        expected_message = """
:checkbox: **RESOLVED**

**TestAlert**

This alert was fired at <time:2022-08-31T05:54:04.52289368Z>.

This alert was resolved at <time:2022-08-31T10:30:00.52288431Z>.

Labels:
- alertname: TestAlert
- instance: Grafana

Values:
- foo: 10

Annotations:
- summary: Notification test

[Silence](https://zuliptestingwh2.grafana.net/alerting/silence/new?alertmanager=grafana&matcher=alertname%3DTestAlert&matcher=instance%3DGrafana)
[Image](https://grafana.com/assets/img/blog/mixed_styles.png)
""".strip()

        self.check_webhook(
            "alert_new",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_alert_new_no_labels(self) -> None:
        expected_topic_name = "[57c6d9296de2ad39]"  # fingerprint
        expected_message = """
:checkbox: **RESOLVED**

This alert was fired at <time:2022-08-31T05:54:04.52289368Z>.

This alert was resolved at <time:2022-08-31T10:30:00.52288431Z>.

""".strip()

        self.check_webhook(
            "alert_new_no_labels",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_alert_new_multiple(self) -> None:
        expected_topic_name_1 = "[High memory usage]"
        expected_topic_name_2 = "[High CPU usage]"
        expected_message_1 = """
:alert: **FIRING**

**High memory usage**

This alert was fired at <time:2021-10-12T09:51:03.157076+02:00>.

Labels:
- alertname: High memory usage
- team: blue
- zone: us-1

Values:
- B: 44.23943737541908
- C: 1

Annotations:
- description: The system has high memory usage
- runbook_url: https://myrunbook.com/runbook/1234
- summary: This alert was triggered for zone us-1

[Generator](https://play.grafana.org/alerting/1afz29v7z/edit)
[Silence](https://play.grafana.org/alerting/silence/new?alertmanager=grafana&matchers=alertname%3DT2%2Cteam%3Dblue%2Czone%3Dus-1)
""".strip()
        expected_message_2 = """
:alert: **FIRING**

**High CPU usage**

This alert was fired at <time:2021-10-12T09:56:03.157076+02:00>.

Labels:
- alertname: High CPU usage
- team: blue
- zone: eu-1

Values:
- B: 44.23943737541908
- C: 1

Annotations:
- description: The system has high CPU usage
- runbook_url: https://myrunbook.com/runbook/1234
- summary: This alert was triggered for zone eu-1

[Generator](https://play.grafana.org/alerting/d1rdpdv7k/edit)
[Silence](https://play.grafana.org/alerting/silence/new?alertmanager=grafana&matchers=alertname%3DT1%2Cteam%3Dblue%2Czone%3Deu-1)
""".strip()

        self.subscribe(self.test_user, self.STREAM_NAME)
        payload = self.get_body("alert_new_multiple")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
        )

        msg = self.get_second_to_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=expected_topic_name_1,
            content=expected_message_1,
        )

        msg = self.get_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=expected_topic_name_2,
            content=expected_message_2,
        )

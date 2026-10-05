import orjson

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.alertmanager.view import ALERTMANAGER_SEVERITY_EMOJI


class AlertmanagerHookTests(WebhookTestCase):
    URL_TEMPLATE = "/api/v1/external/alertmanager?&api_key={api_key}&stream={stream}&name=topic&desc=description"

    def test_error_issue_message(self) -> None:
        expected_topic_name = "andromeda"
        expected_message = """
:alert: **FIRING**
* CPU core temperature is 34.75C ([source](http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0))
* CPU core temperature is 17.625C ([source](http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0))
""".strip()

        self.check_webhook(
            "alert",
            expected_topic_name,
            expected_message,
            "application/json",
        )

    def test_single_error_issue_message(self) -> None:
        expected_topic_name = "andromeda"
        expected_message = """
:squared_ok: **Resolved** CPU core temperature is 34.75C ([source](http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0))
""".strip()

        self.check_webhook(
            "single_alert",
            expected_topic_name,
            expected_message,
            "application/json",
        )

    def test_single_alert_no_generator_url(self) -> None:
        expected_topic_name = "andromeda"
        expected_message = ":alert: **FIRING** CPU core temperature is 34.75C"

        self.check_webhook(
            "single_alert_no_url",
            expected_topic_name,
            expected_message,
            "application/json",
        )

    def test_all_severity_emojis(self) -> None:
        expected_message_template = "{emoji} **FIRING** CPU core temperature is 34.75C"
        payload = orjson.loads(self.get_body("single_alert_no_url"))

        for severity, emoji in ALERTMANAGER_SEVERITY_EMOJI.items():
            with self.subTest(severity=severity):
                payload["alerts"][0]["labels"]["severity"] = severity
                self.check_webhook(
                    "single_alert_no_url",
                    "andromeda",
                    expected_message_template.format(emoji=emoji, severity=severity),
                    custom_payload=payload,
                )

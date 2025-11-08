from zerver.lib.test_classes import WebhookTestCase


class AlertmanagerHookTests(WebhookTestCase):
    CHANNEL_NAME = "alertmanager"
    URL_TEMPLATE = "/api/v1/external/alertmanager?&api_key={api_key}&stream={stream}&name=topic&desc=description"
    WEBHOOK_DIR_NAME = "alertmanager"

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

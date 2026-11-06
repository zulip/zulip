from zerver.lib.test_classes import WebhookTestCase


class AlertmanagerHookTests(WebhookTestCase):
    URL_TEMPLATE = "/api/v1/external/alertmanager?&api_key={api_key}&stream={stream}&name=topic&desc=description"

    def test_error_issue_message(self) -> None:
        expected_topic_name = "andromeda"
        expected_message = """
:alert: **CRITICAL: High CPU core temperature ([source](http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0))**
``` spoiler Details
**Description:**
CPU core temperature is 17.625C

**Labels:**
- alertname: High CPU Temperature
- host: andromeda
- severity: critical

**Annotations:**
- description: CPU core temperature is 17.625C
- summary: High CPU core temperature
- topic: andromeda
```
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
:squared_ok: **RESOLVED: High CPU core temperature ([source](http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0))**
``` spoiler Details
**Description:**
CPU core temperature is 34.75C

**Labels:**
- alertname: High CPU Temperature
- host: andromeda
- severity: critical

**Annotations:**
- description: CPU core temperature is 34.75C
- summary: High CPU core temperature
- topic: andromeda
```
""".strip()

        self.check_webhook(
            "single_alert",
            expected_topic_name,
            expected_message,
            "application/json",
        )

    def test_single_alert_no_generator_url(self) -> None:
        expected_topic_name = "andromeda"
        expected_message = """:alert: **CRITICAL: High CPU core temperature**
``` spoiler Details
**Description:**
CPU core temperature is 34.75C

**Labels:**
- alertname: High CPU Temperature
- host: andromeda
- severity: critical

**Annotations:**
- description: CPU core temperature is 34.75C
- summary: High CPU core temperature
- topic: andromeda
```"""

        self.check_webhook(
            "single_alert_no_url",
            expected_topic_name,
            expected_message,
            "application/json",
        )

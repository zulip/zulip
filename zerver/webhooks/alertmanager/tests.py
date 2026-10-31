from unittest.mock import MagicMock, call, patch

import orjson

from zerver.lib.test_classes import WebhookTestCase


class AlertmanagerHookTests(WebhookTestCase):
    URL_TEMPLATE = "/api/v1/external/alertmanager?&api_key={api_key}&stream={stream}"

    @patch("zerver.webhooks.alertmanager.view.check_send_webhook_message")
    def test_multiple_alerts_send_all_messages(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(name="topic", desc="description")
        payload = self.get_body("alert")
        self.client_post(self.url, payload, content_type="application/json")
        expected_topic_name = "andromeda"
        expected_messages = [
            f""":alert: **CRITICAL: High CPU core temperature ([source]({"http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0"}))**
``` spoiler Details
**Description:**
CPU core temperature is 34.75C

**Labels:**
- alertname: High CPU Temperature
- host: andromeda

**Annotations:**
- topic: andromeda
```""",
            f""":alert: **CRITICAL: High CPU core temperature ([source]({"http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0"}))**
``` spoiler Details
**Description:**
CPU core temperature is 17.625C

**Labels:**
- alertname: High CPU Temperature
- host: andromeda

**Annotations:**
- topic: andromeda
```""",
        ]
        request, user_profile = (
            check_send_webhook_message_mock.call_args_list[0][0][0],
            check_send_webhook_message_mock.call_args_list[0][0][1],
        )
        expected_list = [
            call(request, user_profile, expected_topic_name, expected_message)
            for expected_message in expected_messages
        ]
        self.assertEqual(check_send_webhook_message_mock.call_args_list, expected_list)

    def test_single_alert_resolved(self) -> None:
        self.url = self.build_webhook_url(name="topic", desc="description")
        expected_topic_name = "andromeda"
        expected_message = f""":squared_ok: **RESOLVED: High CPU core temperature ([source]({"http://cobalt:9090/graph?g0.expr=avg+by%28host%29+%28sensors_temp_input%7Bfeature%3D~%22core_%5B0-9%5D%2B%22%7D%29+%3E+15&g0.tab=0"}))**
``` spoiler Details
**Description:**
CPU core temperature is 34.75C

**Labels:**
- alertname: High CPU Temperature
- host: andromeda

**Annotations:**
- topic: andromeda
```"""

        self.check_webhook("single_alert_resolved", expected_topic_name, expected_message)

    def test_single_alert_no_generator_url(self) -> None:
        self.url = self.build_webhook_url(name="topic", desc="description")
        expected_topic_name = "andromeda"
        expected_message = """:alert: **CRITICAL: High CPU core temperature**
``` spoiler Details
**Description:**
CPU core temperature is 34.75C

**Labels:**
- alertname: High CPU Temperature
- host: andromeda

**Annotations:**
- topic: andromeda
```"""

        self.check_webhook("single_alert_no_url", expected_topic_name, expected_message)

    def test_single_alert_firing(self) -> None:
        expected_topic_name = "web-prod-02"
        expected_message = f""":alert: **WARNING: Disk space running low on  ([source]({"http://archlinux:9090/graph?g0.expr=vector%281%29+%3E+0&g0.tab=0"}))**
``` spoiler Details
**Description:**
DiskSpaceRunningLow

**Labels:**
- instance: web-prod-02
- team: devops

**Annotations:**
- description: Storage on instance  breached threshold (value: 1).
```"""

        self.check_webhook("single_alert_firing", expected_topic_name, expected_message)

    def test_missing_instance(self) -> None:
        expected_topic_name = "(unknown)"
        expected_message = f""":alert: **WARNING: Disk space running low on  ([source]({"http://archlinux:9090/graph?g0.expr=vector%281%29+%3E+0&g0.tab=0"}))**
``` spoiler Details
**Description:**
DiskSpaceRunningLow

**Labels:**
- team: devops

**Annotations:**
- description: Storage on instance  breached threshold (value: 1).
```"""
        payload = orjson.loads(self.get_body("single_alert_firing"))
        del payload["alerts"][0]["labels"]["instance"]

        self.check_webhook(
            "single_alert_firing", expected_topic_name, expected_message, custom_payload=payload
        )

    def test_missing_alertname(self) -> None:
        expected_topic_name = "web-prod-02"
        expected_message = f""":alert: **WARNING: Disk space running low on  ([source]({"http://archlinux:9090/graph?g0.expr=vector%281%29+%3E+0&g0.tab=0"}))**
``` spoiler Details
**Description:**
<missing field: alertname>

**Labels:**
- instance: web-prod-02
- team: devops

**Annotations:**
- description: Storage on instance  breached threshold (value: 1).
```"""
        payload = orjson.loads(self.get_body("single_alert_firing"))
        del payload["alerts"][0]["labels"]["alertname"]

        self.check_webhook(
            "single_alert_firing", expected_topic_name, expected_message, custom_payload=payload
        )

    def test_missing_summary(self) -> None:
        expected_topic_name = "web-prod-02"
        expected_message = f""":alert: **WARNING: DiskSpaceRunningLow ([source]({"http://archlinux:9090/graph?g0.expr=vector%281%29+%3E+0&g0.tab=0"}))**
``` spoiler Details
**Description:**
DiskSpaceRunningLow

**Labels:**
- instance: web-prod-02
- team: devops

**Annotations:**
- description: Storage on instance  breached threshold (value: 1).
```"""
        payload = orjson.loads(self.get_body("single_alert_firing"))
        del payload["alerts"][0]["annotations"]["summary"]

        self.check_webhook(
            "single_alert_firing", expected_topic_name, expected_message, custom_payload=payload
        )

    def test_missing_severity(self) -> None:
        expected_topic_name = "web-prod-02"
        expected_message = f""":alert: **FIRING: Disk space running low on  ([source]({"http://archlinux:9090/graph?g0.expr=vector%281%29+%3E+0&g0.tab=0"}))**
``` spoiler Details
**Description:**
DiskSpaceRunningLow

**Labels:**
- instance: web-prod-02
- team: devops

**Annotations:**
- description: Storage on instance  breached threshold (value: 1).
```"""
        payload = orjson.loads(self.get_body("single_alert_firing"))
        del payload["alerts"][0]["labels"]["severity"]

        self.check_webhook(
            "single_alert_firing", expected_topic_name, expected_message, custom_payload=payload
        )

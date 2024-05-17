from zerver.lib.test_classes import WebhookTestCase


class StatuspageHookTests(WebhookTestCase):
    CHANNEL_NAME = "statuspage-test"
    URL_TEMPLATE = "/api/v1/external/statuspage?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "statuspage"

    def test_statuspage_incident(self) -> None:
        expected_topic_name = "Database query delays: All Systems Operational"
        expected_message = """
**Database query delays**:
* State: **identified**
* Description: We just encountered that database queries are timing out resulting in inconvenience to our end users...we'll do quick fix latest by tomorrow !!!
""".strip()
        self.check_webhook(
            "incident_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_statuspage_incident_update(self) -> None:
        expected_topic_name = "Database query delays: All Systems Operational"
        expected_message = """
**Database query delays**:
* State: **resolved**
* Description: The database issue is resolved.
""".strip()
        self.check_webhook(
            "incident_update",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_statuspage_component(self) -> None:
        expected_topic_name = "Database component: Service Under Maintenance"
        expected_message = "**Database component** has changed status from **operational** to **under_maintenance**."
        self.check_webhook(
            "component_status_update",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_statuspage_anomalous_payload(self) -> None:
        result = self.client_post(
            self.url,
            {},
            content_type="application/json",
        )
        self.assert_json_error(
            result, "Unable to parse request: Did Statuspage generate this event?", 400
        )

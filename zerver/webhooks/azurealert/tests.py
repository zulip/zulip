from zerver.lib.test_classes import WebhookTestCase


class AzurealertHookTests(WebhookTestCase):
    def test_metric_alert_fired(self) -> None:
        expected_topic_name = "test-metricAlertRule"
        expected_message = """
:alert: Alert rule **test-metricAlertRule** was fired.

* **Signal type**: Metric
* **Severity**: Sev3
* **Monitoring service**: Platform
* **Affected resources**: test-storageAccount
* **Fired at**: 2021-11-15T09:35:24.3468506Z
* **Description**: Alert rule description
""".strip()
        self.check_webhook("metric_alert_fired", expected_topic_name, expected_message)

    def test_metric_alert_resolved(self) -> None:
        expected_topic_name = "test-metricAlertRule"
        expected_message = """
:squared_ok: Alert rule **test-metricAlertRule** was resolved.

* **Signal type**: Metric
* **Severity**: Sev3
* **Monitoring service**: Platform
* **Affected resources**: test-storageAccount
* **Resolved at**: 2021-11-15T10:00:00.0000000Z
* **Description**: Alert rule description
""".strip()
        self.check_webhook("metric_alert_resolved", expected_topic_name, expected_message)

    def test_log_alert_fired(self) -> None:
        """Log Alerts V2 format (API version 2021-08-01+)."""
        expected_topic_name = "AcmeRule"
        expected_message = """
:alert: Alert rule **AcmeRule** was fired.

* **Signal type**: Log
* **Severity**: Sev4
* **Monitoring service**: Log Alerts V2
* **Affected resources**: testvm
* **Fired at**: 2020-07-09T14:04:49.99645Z
* **Description**: log alert rule V2
""".strip()
        self.check_webhook("log_alert_fired", expected_topic_name, expected_message)

    def test_log_alert_legacy_fired(self) -> None:
        """Legacy Log Analytics format (API version up to 2018-04-16).

        Older alert rules created before the 2021-08-01 API use a flat
        alertContext with SearchQuery/SearchIntervalStartTimeUtc fields
        instead of the new LogQueryCriteria conditionType. The essentials
        block is identical, so we handle both transparently.
        """
        expected_topic_name = "test-logAlertRule-v1-metricMeasurement"
        expected_message = """
:alert: Alert rule **test-logAlertRule-v1-metricMeasurement** was fired.

* **Signal type**: Log
* **Severity**: Sev3
* **Monitoring service**: Log Analytics
* **Affected resources**: None
* **Fired at**: 2021-11-16T15:17:21.9232467Z
* **Description**: Alert rule description
""".strip()
        self.check_webhook("log_alert_legacy_fired", expected_topic_name, expected_message)

    def test_activity_log_alert_fired(self) -> None:
        expected_topic_name = "test-activityLogAlertRule"
        expected_message = """
:alert: Alert rule **test-activityLogAlertRule** was fired.

* **Signal type**: Activity Log
* **Severity**: Sev4
* **Monitoring service**: Activity Log - Administrative
* **Affected resources**: test-VM
* **Fired at**: 2021-11-16T08:29:01.2932462Z
* **Description**: Alert rule description
""".strip()
        self.check_webhook("activity_log_alert_fired", expected_topic_name, expected_message)

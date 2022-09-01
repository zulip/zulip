from zerver.lib.test_classes import WebhookTestCase


class AzureAlertHookTests(WebhookTestCase):
    STREAM_NAME = "devel"
    URL_TEMPLATE = "/api/v1/external/azurealert?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "azurealert"

    def test_azurealert_metric_alert(self) -> None:
        expected_topic = "Metric"
        expected_message = """\
A sev3 alert was fired on 2021-11-15 09:35 UTC by service - 'Platform' on the following configuration items - ['test-storageAccount']
Description -
Alert rule description
""".strip()
        self.check_webhook("metric_alert", expected_topic, expected_message)

    def test_azurealert_log_alert(self) -> None:
        expected_topic = "Log"
        expected_message = """
A sev3 alert was fired on 2021-11-16 15:17 UTC by service - 'Log Analytics' on the following configuration items - []
Description -
Alert rule description
""".strip()
        self.check_webhook("log_alert", expected_topic, expected_message)

    def test_azurealert_activity_log_alert(self) -> None:
        expected_topic = "Activity Log"
        expected_message = """
A sev4 alert was fired on 2021-11-16 08:29 UTC by service - 'Activity Log - Administrative' on the following configuration items - ['test-VM']
Description -
Alert rule description
""".strip()
        self.check_webhook("activity_log_alert", expected_topic, expected_message)

from zerver.lib.test_classes import WebhookTestCase


class AzuremonitorHookTests(WebhookTestCase):
    def test_metric_alert_fired(self) -> None:
        expected_topic_name = "WCUS-R2-Gen2"
        expected_message = (
            ":alert: **FIRING** (severity Sev3)\n\n"
            "**Percentage CPU** (Average) is **31.1105**, "
            "which is greater than the threshold of **25**."
        )
        self.check_webhook("metric_alert_fired", expected_topic_name, expected_message)

    def test_metric_alert_resolved(self) -> None:
        expected_topic_name = "WCUS-R2-Gen2"
        expected_message = (
            ":squared_ok: **RESOLVED**\n\n"
            "**Percentage CPU** (Average) is **7.727**, "
            "no longer greater than the threshold of **25**."
        )
        self.check_webhook("metric_alert_resolved", expected_topic_name, expected_message)

    def test_metric_alert_dynamic_fired(self) -> None:
        expected_topic_name = "Egress-Alert"
        expected_message = (
            ":alert: **FIRING** (severity Sev3)\n\n"
            "**Egress** (Total) is **50101**, "
            "which is greater than the threshold of **47658**."
        )
        self.check_webhook("metric_alert_dynamic_fired", expected_topic_name, expected_message)

    def test_metric_alert_availability_fired(self) -> None:
        expected_topic_name = "Availability-Test-Alert"
        expected_message = (
            ":alert: **FIRING** (severity Sev1)\n\n"
            "**Failed Location** (Sum) is **5**, "
            "which is greater than the threshold of **2**."
        )
        self.check_webhook("metric_alert_availability_fired", expected_topic_name, expected_message)

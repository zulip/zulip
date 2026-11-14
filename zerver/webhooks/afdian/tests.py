from zerver.lib.test_classes import WebhookTestCase


class AfdianHookTests(WebhookTestCase):
    def test_order(self) -> None:
        expected_topic = "Afdian"
        expected_message = """**New Afdian order**
- Amount: 5.00
- Months: 1
- Status: paid
- Order: `202106232138371083454010626`"""

        self.check_webhook(
            "order",
            expected_topic,
            expected_message,
        )

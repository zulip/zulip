from unittest import mock
from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase


class StripeHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/stripe?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "stripe"

    def test_charge_dispute_closed(self) -> None:
        expected_topic_name = "disputes"
        expected_message = "[Dispute](https://dashboard.stripe.com/disputes/dp_00000000000000) closed. Current status: won."
        self.check_webhook(
            "charge_dispute_closed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_charge_dispute_created(self) -> None:
        expected_topic_name = "disputes"
        expected_message = "[Dispute](https://dashboard.stripe.com/disputes/dp_00000000000000) created. Current status: needs response."
        self.check_webhook(
            "charge_dispute_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_charge_failed(self) -> None:
        expected_topic_name = "charges"
        expected_message = (
            "[Charge](https://dashboard.stripe.com/charges/ch_00000000000000) for 1.00 AUD failed"
        )
        self.check_webhook(
            "charge_failed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # Credit card charge
    def test_charge_succeeded__card(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = "[Charge](https://dashboard.stripe.com/charges/ch_000000000000000000000000) for 1.00 AUD succeeded"
        self.check_webhook(
            "charge_succeeded__card",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # ACH payment (really a 'payment', rather than a 'charge')
    def test_charge_succeeded__invoice(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = "[Payment](https://dashboard.stripe.com/payments/py_000000000000000000000000) for $1.00 succeeded"
        self.check_webhook(
            "charge_succeeded__invoice",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_created(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = (
            "[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) created"
        )
        self.check_webhook(
            "customer_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_created_email(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = "[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) created\nEmail: example@abc.com"
        self.check_webhook(
            "customer_created_email",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_deleted(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = (
            "[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) deleted"
        )
        self.check_webhook(
            "customer_deleted",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_subscription_created(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = """\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_E6STM5w5EX3K28) created
Plan: [flatrate](https://dashboard.stripe.com/plans/plan_E6SQ6RAtmLVtzg)
Quantity: 800
Billing method: send invoice"""
        self.check_webhook(
            "customer_subscription_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_subscription_created_no_nickname(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = """\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_E6STM5w5EX3K28) created
Plan: https://dashboard.stripe.com/plans/plan_E6SQ6RAtmLVtzg
Quantity: 800
Billing method: send invoice"""
        self.check_webhook(
            "customer_subscription_created_no_nickname",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_subscription_deleted(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = (
            "[Subscription](https://dashboard.stripe.com/subscriptions/sub_00000000000000) deleted"
        )
        self.check_webhook(
            "customer_subscription_deleted",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_subscription_updated(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = """\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_E6STM5w5EX3K28) updated
* Billing cycle anchor is now Nov 01, 2019, 12:00:00 UTC
* Current period end is now Nov 01, 2019, 12:00:00 UTC
* Current period start is now Dec 06, 2018, 05:53:55 UTC
* Start is now Dec 06, 2018, 05:53:55 UTC
* Status is now trialing
* Trial end is now Nov 01, 2019, 12:00:00 UTC
* Trial start is now Dec 06, 2018, 05:53:55 UTC"""
        self.check_webhook(
            "customer_subscription_updated",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_subscription_trial_will_end(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = "[Subscription](https://dashboard.stripe.com/subscriptions/sub_00000000000000) trial will end in 3 days"
        # 3 days before the end of the trial, plus a little bit to make sure the rounding is working
        with mock.patch("time.time", return_value=1480892861 - 3 * 3600 * 24 + 100):
            # use fixture named stripe_customer_subscription_trial_will_end
            self.check_webhook(
                "customer_subscription_trial_will_end",
                expected_topic_name,
                expected_message,
                content_type="application/x-www-form-urlencoded",
            )

    def test_customer_updated__account_balance(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = (
            "[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) updated"
            "\n* Account balance is now 100"
        )
        self.check_webhook(
            "customer_updated__account_balance",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_discount_created(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = "Discount created ([25.5% off](https://dashboard.stripe.com/coupons/25_00000000000000))."
        self.check_webhook(
            "customer_discount_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_invoice_payment_failed(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = (
            "[Invoice](https://dashboard.stripe.com/invoices/in_00000000000000) payment failed"
        )
        self.check_webhook(
            "invoice_payment_failed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_invoice_created(self) -> None:
        expected_topic_name = "cus_HH97asvHvaYQYp"
        expected_message = """
[Invoice](https://dashboard.stripe.com/invoices/in_1GpmuuHLwdCOCoR7ghzQDQLW) created (manual)
Total: 0.00 INR
Amount due: 0.00 INR
""".strip()
        self.check_webhook("invoice_created", expected_topic_name, expected_message)

    def test_invoiceitem_created(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = "[Invoice item](https://dashboard.stripe.com/invoiceitems/ii_00000000000000) created for 10.00 CAD"
        self.check_webhook(
            "invoiceitem_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_invoice_paid(self) -> None:
        expected_topic_name = "cus_FDmrSwQt9Fck5M"
        expected_message = "[Invoice](https://dashboard.stripe.com/invoices/in_1EjLINHuGUuNWDDZjDf2WNqd) is now paid"
        self.check_webhook(
            "invoice_updated__paid",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_refund_event(self) -> None:
        expected_topic_name = "refunds"
        expected_message = "A [refund](https://dashboard.stripe.com/refunds/re_1Gib6ZHLwdCOCoR7VrzCnXlj) for a [charge](https://dashboard.stripe.com/charges/ch_1Gib61HLwdCOCoR71rnkccye) of 300000.00 INR was updated."
        self.check_webhook("refund_event", expected_topic_name, expected_message)

    def test_pseudo_refund_event(self) -> None:
        expected_topic_name = "refunds"
        expected_message = "A [refund](https://dashboard.stripe.com/refunds/pyr_abcde12345ABCDF) for a [payment](https://dashboard.stripe.com/payments/py_abcde12345ABCDG) of 12.34 EUR was updated."
        self.check_webhook("pseudo_refund_event", expected_topic_name, expected_message)

    @patch("zerver.webhooks.stripe.view.check_send_webhook_message")
    def test_account_updated_without_previous_attributes_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("account_updated_without_previous_attributes")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

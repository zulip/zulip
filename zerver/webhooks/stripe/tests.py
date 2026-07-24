from unittest import mock
from unittest.mock import MagicMock, patch

import orjson

from zerver.lib.test_classes import WebhookTestCase


class StripeHookTests(WebhookTestCase):
    def test_charge_dispute_closed(self) -> None:
        expected_topic_name = "disputes"
        expected_message = "[Dispute](https://dashboard.stripe.com/payments/ch_00000000000000) closed. Current status: won."
        self.check_webhook(
            "charge_dispute_closed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_charge_dispute_closed_with_pi(self) -> None:
        expected_topic_name = "disputes"
        expected_message = "[Dispute](https://dashboard.stripe.com/payments/pi_3TbG44JEe0yY0QKr0OnHpigY) closed. Current status: lost."
        self.check_webhook(
            "charge_dispute_closed_with_pi",
            expected_topic_name,
            expected_message,
        )

    def test_charge_dispute_created(self) -> None:
        expected_topic_name = "disputes"
        expected_message = "[Dispute](https://dashboard.stripe.com/payments/ch_00000000000000) created. Current status: needs response."
        self.check_webhook(
            "charge_dispute_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_charge_dispute_created_pdp_prefix(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = orjson.loads(self.get_body("charge_dispute_created"))
        payload["data"]["object"]["id"] = "pdp_00000000000000"
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/x-www-form-urlencoded",
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="disputes",
            content="[Dispute](https://dashboard.stripe.com/payments/ch_00000000000000) created. Current status: needs response.",
        )

    def test_charge_dispute_created_with_pi(self) -> None:
        expected_topic_name = "disputes"
        expected_message = "[Dispute](https://dashboard.stripe.com/payments/pi_3TbG44JEe0yY0QKr0OnHpigY) created. Current status: needs response."
        self.check_webhook(
            "charge_dispute_created_with_pi",
            expected_topic_name,
            expected_message,
        )

    def test_charge_failed(self) -> None:
        expected_topic_name = "charges"
        expected_message = (
            "[Charge](https://dashboard.stripe.com/payments/ch_00000000000000) for 1.00 AUD failed"
        )
        self.check_webhook(
            "charge_failed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_charge_failed_with_pi(self) -> None:
        expected_topic_name = "charges"
        expected_message = "[Charge](https://dashboard.stripe.com/payments/pi_3TbGfyJEe0yY0QKr0V9PBbP9) for $22.00 failed. Failure code: card_declined"
        self.check_webhook(
            "charge_failed_with_pi",
            expected_topic_name,
            expected_message,
        )

    # Credit card charge
    def test_charge_succeeded__card(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = "[Charge](https://dashboard.stripe.com/payments/ch_000000000000000000000000) for 1.00 AUD succeeded"
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

    def test_charge_succeeded_with_pi(self) -> None:
        expected_topic_name = "charges"
        expected_message = "[Charge](https://dashboard.stripe.com/payments/pi_3TbGBUJEe0yY0QKr1NhtlhQp) for $222.00 succeeded"
        self.check_webhook(
            "charge_succeeded_with_pi",
            expected_topic_name,
            expected_message,
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

    def test_customer_subscription_created_with_collection_method(self) -> None:
        expected_topic_name = "cus_UZ11RVzkmLf6Cf"
        expected_message = """\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_1TbGh3JEe0yY0QKrmHd5I4l8) created
Plan: https://dashboard.stripe.com/plans/price_1TZtAjJEe0yY0QKr27Tj0mDA
Quantity: 1
Billing method: charge automatically"""
        self.check_webhook(
            "customer_subscription_created_with_collection_method",
            expected_topic_name,
            expected_message,
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

    def test_customer_subscription_deleted_with_collection_method(self) -> None:
        expected_topic_name = "cus_UZ11RVzkmLf6Cf"
        expected_message = "[Subscription](https://dashboard.stripe.com/subscriptions/sub_1TbGh3JEe0yY0QKrmHd5I4l8) deleted"
        self.check_webhook(
            "customer_subscription_deleted_with_collection_method",
            expected_topic_name,
            expected_message,
        )

    def test_customer_subscription_updated(self) -> None:
        expected_topic_name = "cus_00000000000000"
        expected_message = """\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_E6STM5w5EX3K28) updated
* Billing cycle anchor is now <time:2019-11-01T12:00:00+00:00>
* Current period end is now <time:2019-11-01T12:00:00+00:00>
* Current period start is now <time:2018-12-06T05:53:55+00:00>
* Start is now <time:2018-12-06T05:53:55+00:00>
* Status is now trialing
* Trial end is now <time:2019-11-01T12:00:00+00:00>
* Trial start is now <time:2018-12-06T05:53:55+00:00>"""
        self.check_webhook(
            "customer_subscription_updated",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customer_subscription_updated_with_collection_method(self) -> None:
        expected_topic_name = "cus_UZ11RVzkmLf6Cf"
        expected_message = """\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_1TZtDLJEe0yY0QKroHU9hRvx) updated
* Billing cycle anchor is now <time:2026-05-27T08:53:52+00:00>
* Status is now trialing
* Trial end is now <time:2026-05-27T08:53:52+00:00>
* Trial start is now <time:2026-05-26T08:54:07+00:00>"""
        self.check_webhook(
            "customer_subscription_updated_with_collection_method",
            expected_topic_name,
            expected_message,
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

    def test_customer_subscription_trial_will_end_with_collection_method(self) -> None:
        expected_topic_name = "cus_UZ11RVzkmLf6Cf"
        expected_message = "[Subscription](https://dashboard.stripe.com/subscriptions/sub_1TZtDLJEe0yY0QKroHU9hRvx) trial will end in 3 days"
        with mock.patch("time.time", return_value=1779872032 - 3 * 3600 * 24 + 100):
            self.check_webhook(
                "customer_subscription_trial_will_end_with_collection_method",
                expected_topic_name,
                expected_message,
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
        expected_message = "Invoice item created for 10.00 CAD"
        self.check_webhook(
            "invoiceitem_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_invoiceitem_created_with_intent(self) -> None:
        expected_topic_name = "cus_UZ11RVzkmLf6Cf"
        expected_message = "[Invoice item](https://dashboard.stripe.com/invoices/in_1TceefJEe0yY0QKrKgc29TeP) created for $121.00"
        self.check_webhook(
            "invoiceitem_created_with_invoice",
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
        expected_message = "A refund for a [charge](https://dashboard.stripe.com/payments/pi_1Gib60HLwdCOCoR7KJbTO3U7) of 300000.00 INR failed."
        self.check_webhook("refund_event", expected_topic_name, expected_message)

    def test_pseudo_refund_event(self) -> None:
        expected_topic_name = "refunds"
        expected_message = "A refund for a [payment](https://dashboard.stripe.com/payments/pi_abcd1234ABCDH) of 12.34 EUR succeeded."
        self.check_webhook("pseudo_refund_event", expected_topic_name, expected_message)

    def test_refund_event_requires_action(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = orjson.loads(self.get_body("refund_event"))
        payload["data"]["object"]["status"] = "requires_action"
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="refunds",
            content="A refund for a [charge](https://dashboard.stripe.com/payments/pi_1Gib60HLwdCOCoR7KJbTO3U7) of 300000.00 INR requires action.",
        )

    @patch("zerver.webhooks.stripe.view.check_send_webhook_message")
    def test_account_updated_without_previous_attributes_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("account_updated_without_previous_attributes")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

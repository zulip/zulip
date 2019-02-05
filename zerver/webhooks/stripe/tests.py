# -*- coding: utf-8 -*-

import mock

from zerver.lib.test_classes import WebhookTestCase

class StripeHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/stripe?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'stripe'

    def test_charge_dispute_closed(self) -> None:
        expected_topic = u"disputes"
        expected_message = u"[Dispute](https://dashboard.stripe.com/disputes/dp_00000000000000) closed. Current status: won."
        self.send_and_test_stream_message('charge_dispute_closed', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_charge_dispute_created(self) -> None:
        expected_topic = u"disputes"
        expected_message = u"[Dispute](https://dashboard.stripe.com/disputes/dp_00000000000000) created. Current status: needs response."
        self.send_and_test_stream_message('charge_dispute_created', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_charge_failed(self) -> None:
        expected_topic = u"charges"
        expected_message = u"[Charge](https://dashboard.stripe.com/charges/ch_00000000000000) for 1.00 AUD failed"
        self.send_and_test_stream_message('charge_failed', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    # Credit card charge
    def test_charge_succeeded__card(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Charge](https://dashboard.stripe.com/charges/ch_000000000000000000000000) for 1.00 AUD succeeded"
        self.send_and_test_stream_message('charge_succeeded__card', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    # ACH payment (really a 'payment', rather than a 'charge')
    def test_charge_succeeded__invoice(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Payment](https://dashboard.stripe.com/payments/py_000000000000000000000000) for $1.00 succeeded"
        self.send_and_test_stream_message('charge_succeeded__invoice', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_created(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) created"
        self.send_and_test_stream_message('customer_created', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_created_email(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) created\nEmail: example@abc.com"
        self.send_and_test_stream_message('customer_created_email', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_deleted(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) deleted"
        self.send_and_test_stream_message('customer_deleted', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_subscription_created(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"""\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_E6STM5w5EX3K28) created
Plan: [flatrate](https://dashboard.stripe.com/plans/plan_E6SQ6RAtmLVtzg)
Quantity: 800
Billing method: send invoice"""
        self.send_and_test_stream_message('customer_subscription_created', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_subscription_deleted(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Subscription](https://dashboard.stripe.com/subscriptions/sub_00000000000000) deleted"
        self.send_and_test_stream_message('customer_subscription_deleted', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_subscription_updated(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = """\
[Subscription](https://dashboard.stripe.com/subscriptions/sub_E6STM5w5EX3K28) updated
* Billing cycle anchor is now Nov 01, 2019, 12:00:00 UTC
* Current period end is now Nov 01, 2019, 12:00:00 UTC
* Current period start is now Dec 06, 2018, 05:53:55 UTC
* Start is now Dec 06, 2018, 05:53:55 UTC
* Status is now trialing
* Trial end is now Nov 01, 2019, 12:00:00 UTC
* Trial start is now Dec 06, 2018, 05:53:55 UTC"""
        self.send_and_test_stream_message('customer_subscription_updated', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_subscription_trial_will_end(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Subscription](https://dashboard.stripe.com/subscriptions/sub_00000000000000) trial will end in 3 days"
        # 3 days before the end of the trial, plus a little bit to make sure the rounding is working
        with mock.patch('time.time', return_value=1480892861 - 3*3600*24 + 100):
            # use fixture named stripe_customer_subscription_trial_will_end
            self.send_and_test_stream_message('customer_subscription_trial_will_end',
                                              expected_topic, expected_message,
                                              content_type="application/x-www-form-urlencoded")

    def test_customer_updated__account_balance(self) -> None:
        expected_topic = "cus_00000000000000"
        expected_message = "[Customer](https://dashboard.stripe.com/customers/cus_00000000000000) updated" + \
                           "\n* Account balance is now 100"
        self.send_and_test_stream_message('customer_updated__account_balance', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_discount_created(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"Discount created ([25.5% off](https://dashboard.stripe.com/coupons/25_00000000000000))."
        self.send_and_test_stream_message('customer_discount_created', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_invoice_payment_failed(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Invoice](https://dashboard.stripe.com/invoices/in_00000000000000) payment failed"
        self.send_and_test_stream_message('invoice_payment_failed', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_invoiceitem_created(self) -> None:
        expected_topic = u"cus_00000000000000"
        expected_message = u"[Invoice item](https://dashboard.stripe.com/invoiceitems/ii_00000000000000) created for 10.00 CAD"
        self.send_and_test_stream_message(
            'invoiceitem_created',
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded"
        )

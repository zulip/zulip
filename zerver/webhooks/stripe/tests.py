# -*- coding: utf-8 -*-
from typing import Text

import mock

from zerver.lib.test_classes import WebhookTestCase

class StripeHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/stripe?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'stripe'

    def test_charge_dispute_closed(self) -> None:
        expected_subject = u"Charge ch_00000000000000"
        expected_message = u"A charge dispute for **10.01aud** has been closed as **won**.\nThe charge in dispute was **[ch_00000000000000](https://dashboard.stripe.com/payments/ch_00000000000000)**."

        # use fixture named stripe_charge_dispute_closed
        self.send_and_test_stream_message('charge_dispute_closed', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_charge_dispute_created(self) -> None:
        expected_subject = u"Charge ch_00000000000000"
        expected_message = u"A charge dispute for **1000jpy** has been created.\nThe charge in dispute is **[ch_00000000000000](https://dashboard.stripe.com/payments/ch_00000000000000)**."

        # use fixture named stripe_charge_dispute_created
        self.send_and_test_stream_message('charge_dispute_created', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_charge_failed(self) -> None:
        expected_subject = u"Charge ch_00000000000000"
        expected_message = u"A charge with id **[ch_00000000000000](https://dashboard.stripe.com/payments/ch_00000000000000)** for **1.00aud** has failed."

        # use fixture named stripe_charge_failed
        self.send_and_test_stream_message('charge_failed', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_charge_succeeded(self) -> None:
        expected_subject = u"Charge ch_00000000000000"
        expected_message = u"A charge with id **[ch_00000000000000](https://dashboard.stripe.com/payments/ch_00000000000000)** for **1.00aud** has succeeded."

        # use fixture named stripe_charge_succeeded
        self.send_and_test_stream_message('charge_succeeded', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_created_email(self) -> None:
        expected_subject = u"Customer cus_00000000000000"
        expected_message = u"A new customer with id **[cus_00000000000000](https://dashboard.stripe.com/customers/cus_00000000000000)** and email **example@abc.com** has been created."

        # use fixture named stripe_customer_created_email
        self.send_and_test_stream_message('customer_created_email', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_created(self) -> None:
        expected_subject = u"Customer cus_00000000000000"
        expected_message = u"A new customer with id **[cus_00000000000000](https://dashboard.stripe.com/customers/cus_00000000000000)** has been created."

        # use fixture named stripe_customer_created
        self.send_and_test_stream_message('customer_created', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_deleted(self) -> None:
        expected_subject = u"Customer cus_00000000000000"
        expected_message = u"A customer with id **[cus_00000000000000](https://dashboard.stripe.com/customers/cus_00000000000000)** has been deleted."

        # use fixture named stripe_customer_deleted
        self.send_and_test_stream_message('customer_deleted', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_subscription_created(self) -> None:
        expected_subject = u"Customer sub_00000000000000"
        expected_message = u"A new customer subscription for **20.00aud** every **month** has been created.\nThe subscription has id **[sub_00000000000000](https://dashboard.stripe.com/subscriptions/sub_00000000000000)**."

        # use fixture named stripe_customer_subscription_created
        self.send_and_test_stream_message('customer_subscription_created', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_subscription_deleted(self) -> None:
        expected_subject = u"Customer sub_00000000000000"
        expected_message = u"The customer subscription with id **[sub_00000000000000](https://dashboard.stripe.com/subscriptions/sub_00000000000000)** was deleted."

        # use fixture named stripe_customer_subscription_deleted
        self.send_and_test_stream_message('customer_subscription_deleted', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customer_subscription_trial_will_end(self) -> None:
        expected_subject = u"Customer sub_00000000000000"
        expected_message = u"The customer subscription trial with id **[sub_00000000000000](https://dashboard.stripe.com/subscriptions/sub_00000000000000)** will end in 3 days."

        # 3 days before the end of the trial, plus a little bit to make sure the rounding is working
        with mock.patch('time.time', return_value=1480892861 - 3*3600*24 + 100):
            # use fixture named stripe_customer_subscription_trial_will_end
            self.send_and_test_stream_message('customer_subscription_trial_will_end',
                                              expected_subject, expected_message,
                                              content_type="application/x-www-form-urlencoded")

    def test_invoice_payment_failed(self) -> None:
        expected_subject = u"Invoice in_00000000000000"
        expected_message = u"An invoice payment on invoice with id **[in_00000000000000](https://dashboard.stripe.com/invoices/in_00000000000000)** and with **0.00aud** due has failed."

        # use fixture named stripe_invoice_payment_failed
        self.send_and_test_stream_message('invoice_payment_failed', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_order_payment_failed(self) -> None:
        expected_subject = u"Order or_00000000000000"
        expected_message = u"An order payment on order with id **[or_00000000000000](https://dashboard.stripe.com/orders/or_00000000000000)** for **15.00aud** has failed."

        # use fixture named stripe_order_payment_failed
        self.send_and_test_stream_message('order_payment_failed', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_order_payment_succeeded(self) -> None:
        expected_subject = u"Order or_00000000000000"
        expected_message = u"An order payment on order with id **[or_00000000000000](https://dashboard.stripe.com/orders/or_00000000000000)** for **15.00aud** has succeeded."

        # use fixture named stripe_order_payment_succeeded
        self.send_and_test_stream_message('order_payment_succeeded', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_order_updated(self) -> None:
        expected_subject = u"Order or_00000000000000"
        expected_message = u"The order with id **[or_00000000000000](https://dashboard.stripe.com/orders/or_00000000000000)** for **15.00aud** has been updated."

        # use fixture named stripe_order_updated
        self.send_and_test_stream_message('order_updated', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_transfer_failed(self) -> None:
        expected_subject = u"Transfer tr_00000000000000"
        expected_message = u"The transfer with description **Transfer to test@example.com** and id **[tr_00000000000000](https://dashboard.stripe.com/transfers/tr_00000000000000)** for amount **11.00aud** has failed."

        # use fixture named stripe_transfer_failed
        self.send_and_test_stream_message('transfer_failed', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_transfer_paid(self) -> None:
        expected_subject = u"Transfer tr_00000000000000"
        expected_message = u"The transfer with description **Transfer to test@example.com** and id **[tr_00000000000000](https://dashboard.stripe.com/transfers/tr_00000000000000)** for amount **11.00aud** has been paid."

        # use fixture named stripe_transfer_paid
        self.send_and_test_stream_message('transfer_paid', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("stripe", fixture_name, file_type="json")

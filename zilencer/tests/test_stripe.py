import mock
import os
from typing import Any
import ujson

import stripe
from stripe.api_resources.list_object import ListObject

from zerver.lib.actions import do_deactivate_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Realm, UserProfile, get_realm
from zilencer.lib.stripe import StripeError, catch_stripe_errors, \
    do_create_customer_with_payment_source, do_subscribe_customer_to_plan, \
    get_seat_count
from zilencer.models import Customer, Plan

fixture_data_file = open(os.path.join(os.path.dirname(__file__), 'stripe_fixtures.json'), 'r')
fixture_data = ujson.load(fixture_data_file)

def mock_create_customer(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["create_customer"])

def mock_create_subscription(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["create_subscription"])

def mock_retrieve_customer(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["retrieve_customer"])

def mock_upcoming_invoice(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["upcoming_invoice"])

class StripeTest(ZulipTestCase):
    def setUp(self) -> None:
        self.user = self.example_user("hamlet")
        self.realm = self.user.realm
        self.token = 'token'
        # The values below should be copied from stripe_fixtures.json
        self.stripe_customer_id = 'cus_D7OT2jf5YAtZQL'
        self.stripe_plan_id = 'plan_D7Nh2BtpTvIzYp'
        self.quantity = 8
        Plan.objects.create(nickname=Plan.CLOUD_ANNUAL, stripe_plan_id=self.stripe_plan_id)

    @mock.patch("zilencer.lib.stripe.STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key")
    @mock.patch("zilencer.lib.stripe.billing_logger.error")
    def test_errors(self, mock_billing_logger_error: mock.Mock) -> None:
        @catch_stripe_errors
        def raise_invalid_request_error() -> None:
            raise stripe.error.InvalidRequestError("Request req_oJU621i6H6X4Ez: No such token: x",
                                                   None)
        with self.assertRaisesRegex(StripeError, "Something went wrong. Please try again or "):
            raise_invalid_request_error()
        mock_billing_logger_error.assert_called()

        @catch_stripe_errors
        def raise_card_error() -> None:
            error_message = "The card number is not a valid credit card number."
            json_body = {"error": {"message": error_message}}
            raise stripe.error.CardError(error_message, "number", "invalid_number",
                                         json_body=json_body)
        with self.assertRaisesRegex(StripeError,
                                    "The card number is not a valid credit card number."):
            raise_card_error()
        mock_billing_logger_error.assert_called()

        @catch_stripe_errors
        def raise_exception() -> None:
            raise Exception
        with self.assertRaises(Exception):
            raise_exception()
        mock_billing_logger_error.assert_called()

    @mock.patch("zilencer.lib.stripe.STRIPE_PUBLISHABLE_KEY", None)
    def test_no_stripe_keys(self) -> None:
        @catch_stripe_errors
        def foo() -> None:
            pass  # nocoverage
        with self.assertRaisesRegex(StripeError, "Missing Stripe config."):
            foo()

    @mock.patch("zilencer.lib.stripe.STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key")
    @mock.patch("zilencer.views.STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key")
    @mock.patch("stripe.Customer.create", side_effect=mock_create_customer)
    @mock.patch("stripe.Subscription.create", side_effect=mock_create_subscription)
    def test_initial_upgrade(self, mock_create_subscription: mock.Mock,
                             mock_create_customer: mock.Mock) -> None:
        self.login(self.user.email)
        response = self.client_get("/upgrade/")
        self.assert_in_success_response(['We can also bill by invoice'], response)
        # Click "Make payment" in Stripe Checkout
        response = self.client_post("/upgrade/", {
            'stripeToken': self.token,
            'seat_count': self.quantity,
            'plan': Plan.CLOUD_ANNUAL})
        # Check that we created a customer and subscription in stripe, and a
        # Customer object in zulip
        mock_create_customer.assert_called_once_with(
            description="zulip (Zulip Dev)",
            metadata={'realm_id': self.realm.id, 'realm_str': 'zulip'},
            source=self.token)
        mock_create_subscription.assert_called_once_with(
            customer=self.stripe_customer_id,
            billing='charge_automatically',
            items=[{
                'plan': self.stripe_plan_id,
                'quantity': str(self.quantity),
            }],
            prorate=True,
            tax_percent=0)
        self.assertEqual(1, Customer.objects.filter(realm=self.realm,
                                                    stripe_customer_id=self.stripe_customer_id,
                                                    billing_user=self.user).count())
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/billing/', response.url)

    @mock.patch("stripe.Customer.retrieve", side_effect=mock_retrieve_customer)
    @mock.patch("stripe.Invoice.upcoming", side_effect=mock_upcoming_invoice)
    def test_billing_home(self, mock_upcoming_invoice: mock.Mock,
                          mock_retrieve_customer: mock.Mock) -> None:
        self.login(self.user.email)
        # No Customer yet; check that we are redirected to /upgrade
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

        Customer.objects.create(
            realm=self.realm, stripe_customer_id=self.stripe_customer_id, billing_user=self.user)
        response = self.client_get("/billing/")
        self.assert_not_in_success_response(['We can also bill by invoice'], response)
        for substring in ['Your plan will renew on', 'for $%s.00' % (80 * self.quantity,),
                          'Card ending in 4242']:
            self.assert_in_response(substring, response)

    def test_get_seat_count(self) -> None:
        initial_count = get_seat_count(self.realm)
        user1 = UserProfile.objects.create(realm=self.realm, email='user1@zulip.com', pointer=-1)
        user2 = UserProfile.objects.create(realm=self.realm, email='user2@zulip.com', pointer=-1)
        self.assertEqual(get_seat_count(self.realm), initial_count + 2)

        # Test that bots aren't counted
        user1.is_bot = True
        user1.save(update_fields=['is_bot'])
        self.assertEqual(get_seat_count(self.realm), initial_count + 1)

        # Test that inactive users aren't counted
        do_deactivate_user(user2)
        self.assertEqual(get_seat_count(self.realm), initial_count)

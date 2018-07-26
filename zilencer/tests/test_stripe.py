import mock
import os
from typing import Any
import ujson

from django.core import signing

import stripe

from zerver.lib.actions import do_deactivate_user, do_create_user, \
    do_activate_user, do_reactivate_user, activity_change_requires_seat_update
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Realm, UserProfile, get_realm, RealmAuditLog
from zilencer.lib.stripe import StripeError, catch_stripe_errors, \
    do_create_customer_with_payment_source, do_subscribe_customer_to_plan, \
    get_seat_count, extract_current_subscription, sign_string, unsign_string
from zilencer.models import Customer, Plan

fixture_data_file = open(os.path.join(os.path.dirname(__file__), 'stripe_fixtures.json'), 'r')
fixture_data = ujson.load(fixture_data_file)

def mock_create_customer(*args: Any, **kwargs: Any) -> stripe.Customer:
    return stripe.util.convert_to_stripe_object(fixture_data["create_customer"])

def mock_create_subscription(*args: Any, **kwargs: Any) -> stripe.Subscription:
    return stripe.util.convert_to_stripe_object(fixture_data["create_subscription"])

def mock_customer_with_active_subscription(*args: Any, **kwargs: Any) -> stripe.Customer:
    return stripe.util.convert_to_stripe_object(fixture_data["customer_with_active_subscription"])

def mock_customer_with_canceled_subscription(*args: Any, **kwargs: Any) -> stripe.Customer:
    customer = mock_customer_with_active_subscription()
    customer.subscriptions.data[0].status = "canceled"
    customer.subscriptions.data[0].canceled_at = 1532602160
    return customer

def mock_customer_with_cancel_at_period_end_subscription(*args: Any, **kwargs: Any) -> stripe.Customer:
    customer = mock_customer_with_active_subscription()
    customer.subscriptions.data[0].canceled_at = 1532602243
    customer.subscriptions.data[0].cancel_at_period_end = True
    return customer

def mock_upcoming_invoice(*args: Any, **kwargs: Any) -> stripe.Invoice:
    return stripe.util.convert_to_stripe_object(fixture_data["upcoming_invoice"])

class StripeTest(ZulipTestCase):
    def setUp(self) -> None:
        self.token = 'token'
        # The values below should be copied from stripe_fixtures.json
        self.stripe_customer_id = 'cus_D7OT2jf5YAtZQL'
        self.customer_created = 1529990750
        self.stripe_plan_id = 'plan_D7Nh2BtpTvIzYp'
        self.subscription_created = 1529990751
        self.quantity = 8

        self.signed_seat_count, self.salt = sign_string(str(self.quantity))
        Plan.objects.create(nickname=Plan.CLOUD_ANNUAL, stripe_plan_id=self.stripe_plan_id)

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

    @mock.patch("stripe.Customer.create", side_effect=mock_create_customer)
    @mock.patch("stripe.Subscription.create", side_effect=mock_create_subscription)
    def test_initial_upgrade(self, mock_create_subscription: mock.Mock,
                             mock_create_customer: mock.Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        response = self.client_get("/upgrade/")
        self.assert_in_success_response(['We can also bill by invoice'], response)
        self.assertFalse(user.realm.has_seat_based_plan)
        # Click "Make payment" in Stripe Checkout
        response = self.client_post("/upgrade/", {
            'stripeToken': self.token,
            # TODO: get these values from the response
            'signed_seat_count': self.signed_seat_count,
            'salt': self.salt,
            'plan': Plan.CLOUD_ANNUAL})
        # Check that we created a customer and subscription in stripe
        mock_create_customer.assert_called_once_with(
            description="zulip (Zulip Dev)",
            metadata={'realm_id': user.realm.id, 'realm_str': 'zulip'},
            source=self.token)
        mock_create_subscription.assert_called_once_with(
            customer=self.stripe_customer_id,
            billing='charge_automatically',
            items=[{
                'plan': self.stripe_plan_id,
                'quantity': self.quantity,
            }],
            prorate=True,
            tax_percent=0)
        # Check that we correctly populated Customer and RealmAuditLog in Zulip
        self.assertEqual(1, Customer.objects.filter(realm=user.realm,
                                                    stripe_customer_id=self.stripe_customer_id,
                                                    billing_user=user).count())
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', 'event_time').order_by('id'))
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.REALM_STRIPE_INITIALIZED, timestamp_to_datetime(self.customer_created)),
            (RealmAuditLog.REALM_CARD_ADDED, timestamp_to_datetime(self.customer_created)),
            (RealmAuditLog.REALM_PLAN_STARTED, timestamp_to_datetime(self.subscription_created)),
        ])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertTrue(realm.has_seat_based_plan)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/billing/', response.url)

    @mock.patch("stripe.Invoice.upcoming", side_effect=mock_upcoming_invoice)
    @mock.patch("stripe.Customer.retrieve", side_effect=mock_customer_with_active_subscription)
    @mock.patch("stripe.Customer.create", side_effect=mock_create_customer)
    @mock.patch("stripe.Subscription.create", side_effect=mock_create_subscription)
    def test_billing_page_permissions(self, mock_create_subscription: mock.Mock,
                                      mock_create_customer: mock.Mock,
                                      mock_customer_with_active_subscription: mock.Mock,
                                      mock_upcoming_invoice: mock.Mock) -> None:
        # Check that non-admins can access /upgrade via /billing, when there is no Customer object
        self.login(self.example_email('hamlet'))
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)
        # Check that non-admins can sign up and pay
        self.client_post("/upgrade/", {'stripeToken': self.token,
                                       'signed_seat_count': self.signed_seat_count,
                                       'salt': self.salt,
                                       'plan': Plan.CLOUD_ANNUAL})
        # Check that the non-admin hamlet can still access /billing
        response = self.client_get("/billing/")
        self.assert_in_success_response(["for billing history or to make changes"], response)
        # Check admins can access billing, even though they are not the billing_user
        self.login(self.example_email('iago'))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["for billing history or to make changes"], response)
        # Check that non-admin, non-billing_user does not have access
        self.login(self.example_email("cordelia"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["You must be an organization administrator"], response)

    @mock.patch("stripe.Customer.create", side_effect=mock_create_customer)
    @mock.patch("stripe.Subscription.create", side_effect=mock_create_subscription)
    def test_upgrade_with_outdated_seat_count(self, mock_create_subscription: mock.Mock,
                                              mock_create_customer: mock.Mock) -> None:
        self.login(self.example_email("hamlet"))
        new_seat_count = 123
        # Change the seat count while the user is going through the upgrade flow
        with mock.patch('zilencer.lib.stripe.get_seat_count', return_value=new_seat_count):
            self.client_post("/upgrade/", {'stripeToken': self.token,
                                           'signed_seat_count': self.signed_seat_count,
                                           'salt': self.salt,
                                           'plan': Plan.CLOUD_ANNUAL})
        # Check that the subscription call used the old quantity, not new_seat_count
        mock_create_subscription.assert_called_once_with(
            customer=self.stripe_customer_id,
            billing='charge_automatically',
            items=[{
                'plan': self.stripe_plan_id,
                'quantity': self.quantity,
            }],
            prorate=True,
            tax_percent=0)
        # Check that we have the REALM_PLAN_QUANTITY_RESET entry, and that we
        # correctly handled the requires_billing_update field
        audit_log_entries = list(RealmAuditLog.objects.order_by('-id')
                                 .values_list('event_type', 'event_time',
                                              'requires_billing_update')[:4])[::-1]
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.REALM_STRIPE_INITIALIZED, timestamp_to_datetime(self.customer_created), False),
            (RealmAuditLog.REALM_CARD_ADDED, timestamp_to_datetime(self.customer_created), False),
            (RealmAuditLog.REALM_PLAN_STARTED, timestamp_to_datetime(self.subscription_created), False),
            (RealmAuditLog.REALM_PLAN_QUANTITY_RESET, timestamp_to_datetime(self.subscription_created), True),
        ])
        self.assertEqual(ujson.loads(RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_PLAN_QUANTITY_RESET).values_list('extra_data', flat=True).first()),
            {'quantity': new_seat_count})

    def test_upgrade_with_tampered_seat_count(self) -> None:
        self.login(self.example_email("hamlet"))
        result = self.client_post("/upgrade/", {
            'stripeToken': self.token,
            'signed_seat_count': "randomsalt",
            'salt': self.salt,
            'plan': Plan.CLOUD_ANNUAL
        })
        self.assert_in_success_response(["Something went wrong. Please contact"], result)

    def test_upgrade_with_tampered_plan(self) -> None:
        self.login(self.example_email("hamlet"))
        result = self.client_post("/upgrade/", {
            'stripeToken': self.token,
            'signed_seat_count': self.signed_seat_count,
            'salt': self.salt,
            'plan': "invalid"
        })
        self.assert_in_success_response(["Something went wrong. Please contact"], result)

    @mock.patch("stripe.Customer.retrieve", side_effect=mock_customer_with_active_subscription)
    @mock.patch("stripe.Invoice.upcoming", side_effect=mock_upcoming_invoice)
    def test_billing_home_with_active_subscription(self, mock_upcoming_invoice: mock.Mock,
                                                   mock_customer_with_active_subscription: mock.Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        # No Customer yet; check that we are redirected to /upgrade
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

        Customer.objects.create(
            realm=user.realm, stripe_customer_id=self.stripe_customer_id, billing_user=user)
        response = self.client_get("/billing/")
        self.assert_not_in_success_response(['We can also bill by invoice'], response)
        for substring in ['Your plan will renew on', '$%s.00' % (80 * self.quantity,),
                          'Card ending in 4242']:
            self.assert_in_response(substring, response)

    @mock.patch("stripe.Customer.retrieve", side_effect=mock_customer_with_cancel_at_period_end_subscription)
    @mock.patch("stripe.Invoice.upcoming", side_effect=mock_upcoming_invoice)
    def test_billing_home_with_canceled_subscription_going_to_end(self, mock_upcoming_invoice: mock.Mock,
                                                                  mock_retrieve_customer: mock.Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        # No Customer yet; check that we are redirected to /upgrade
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

        Customer.objects.create(
            realm=user.realm, stripe_customer_id=self.stripe_customer_id, billing_user=user)
        response = self.client_get("/billing/")
        self.assert_not_in_success_response(['We can also bill by invoice'], response)
        for substring in ['for Zulip Premium is ending on <strong>June 26, 2019',
                          'downgraded to Zulip Free when the subscription']:
            self.assert_in_response(substring, response)

    def test_get_seat_count(self) -> None:
        realm = get_realm("zulip")
        initial_count = get_seat_count(realm)
        user1 = UserProfile.objects.create(realm=realm, email='user1@zulip.com', pointer=-1)
        user2 = UserProfile.objects.create(realm=realm, email='user2@zulip.com', pointer=-1)
        self.assertEqual(get_seat_count(realm), initial_count + 2)

        # Test that bots aren't counted
        user1.is_bot = True
        user1.save(update_fields=['is_bot'])
        self.assertEqual(get_seat_count(realm), initial_count + 1)

        # Test that inactive users aren't counted
        do_deactivate_user(user2)
        self.assertEqual(get_seat_count(realm), initial_count)

    def test_extract_current_subscription(self) -> None:
        self.assertIsNone(extract_current_subscription(mock_create_customer()))
        subscription = extract_current_subscription(mock_customer_with_active_subscription())
        self.assertEqual(subscription["id"][:4], "sub_")
        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["cancel_at_period_end"], False)
        self.assertIsNone(subscription["canceled_at"])

        self.assertIsNone(extract_current_subscription(mock_customer_with_canceled_subscription()))

        subscription = extract_current_subscription(mock_customer_with_cancel_at_period_end_subscription())
        self.assertEqual(subscription["id"][:4], "sub_")
        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["cancel_at_period_end"], True)
        self.assertIsNotNone(subscription["canceled_at"])

    @mock.patch("stripe.Customer.retrieve", side_effect=mock_customer_with_active_subscription)
    def test_subscribe_customer_to_second_plan(self, mock_customer_with_active_subscription: mock.Mock) -> None:
        with self.assertRaisesRegex(AssertionError, "Customer already has an active subscription."):
            do_subscribe_customer_to_plan(stripe.Customer.retrieve(),  # type: ignore # Mocked out function call
                                          self.stripe_plan_id, self.quantity, 0)

    def test_sign_string(self) -> None:
        string = "abc"
        signed_string, salt = sign_string(string)
        self.assertEqual(string, unsign_string(signed_string, salt))

        with self.assertRaises(signing.BadSignature):
            unsign_string(signed_string, "randomsalt")

class BillingUpdateTest(ZulipTestCase):
    def test_activity_change_requires_seat_update(self) -> None:
        # Realm doesn't have a seat based plan
        self.assertFalse(activity_change_requires_seat_update(self.example_user("hamlet")))
        realm = get_realm("zulip")
        realm.has_seat_based_plan = True
        realm.save(update_fields=['has_seat_based_plan'])
        # seat based plan + user not a bot
        user = self.example_user("hamlet")
        self.assertTrue(activity_change_requires_seat_update(user))
        user.is_bot = True
        user.save(update_fields=['is_bot'])
        # seat based plan but user is a bot
        self.assertFalse(activity_change_requires_seat_update(user))

    def test_requires_billing_update_for_is_active_changes(self) -> None:
        count = RealmAuditLog.objects.count()
        realm = get_realm("zulip")
        user1 = do_create_user('user1@zulip.com', 'password', realm, 'full name', 'short name')
        do_deactivate_user(user1)
        do_reactivate_user(user1)
        # Not a proper use of do_activate_user, but it's fine to call it like this for this test
        do_activate_user(user1)
        self.assertEqual(count + 4,
                         RealmAuditLog.objects.filter(requires_billing_update=False).count())

        realm.has_seat_based_plan = True
        realm.save(update_fields=['has_seat_based_plan'])
        user2 = do_create_user('user2@zulip.com', 'password', realm, 'full name', 'short name')
        do_deactivate_user(user2)
        do_reactivate_user(user2)
        do_activate_user(user2)
        self.assertEqual(4, RealmAuditLog.objects.filter(requires_billing_update=True).count())

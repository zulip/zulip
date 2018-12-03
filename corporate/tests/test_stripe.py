import datetime
from functools import wraps
from mock import Mock, patch
import operator
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, TypeVar, Tuple, cast
import ujson
import json

from django.core import signing
from django.core.management import call_command
from django.core.urlresolvers import get_resolver
from django.http import HttpResponse
from django.utils.timezone import utc as timezone_utc

import stripe

from zerver.lib.actions import do_deactivate_user, do_create_user, \
    do_activate_user, do_reactivate_user, activity_change_requires_seat_update, \
    do_create_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zerver.models import Realm, UserProfile, get_realm, RealmAuditLog
from corporate.lib.stripe import catch_stripe_errors, \
    do_subscribe_customer_to_plan, attach_discount_to_realm, \
    get_seat_count, extract_current_subscription, sign_string, unsign_string, \
    get_next_billing_log_entry, run_billing_processor_one_step, \
    BillingError, StripeCardError, StripeConnectionError, stripe_get_customer, \
    DEFAULT_INVOICE_DAYS_UNTIL_DUE, MIN_INVOICED_SEAT_COUNT, do_create_customer, \
    process_downgrade
from corporate.models import Customer, Plan, Coupon, BillingProcessor
from corporate.views import payment_method_string
import corporate.urls

CallableT = TypeVar('CallableT', bound=Callable[..., Any])

GENERATE_STRIPE_FIXTURES = False
STRIPE_FIXTURES_DIR = "corporate/tests/stripe_fixtures"

# TODO: check that this creates a token similar to what is created by our
# actual Stripe Checkout flows
def stripe_create_token(card_number: str="4242424242424242") -> stripe.Token:
    return stripe.Token.create(
        card={
            "number": card_number,
            "exp_month": 3,
            "exp_year": 2033,
            "cvc": "333",
            "name": "Ada Starr",
            "address_line1": "Under the sea,",
            "address_city": "Pacific",
            "address_zip": "33333",
            "address_country": "United States",
        })

def stripe_fixture_path(decorated_function_name: str, mocked_function_name: str, call_count: int) -> str:
    # Make the eventual filename a bit shorter, and also we conventionally
    # use test_* for the python test files
    if decorated_function_name[:5] == 'test_':
        decorated_function_name = decorated_function_name[5:]
    return "{}/{}:{}.{}.json".format(
        STRIPE_FIXTURES_DIR, decorated_function_name, mocked_function_name[7:], call_count)

def fixture_files_for_function(decorated_function: CallableT) -> List[str]:  # nocoverage
    decorated_function_name = decorated_function.__name__
    if decorated_function_name[:5] == 'test_':
        decorated_function_name = decorated_function_name[5:]
    return sorted(['{}/{}'.format(STRIPE_FIXTURES_DIR, f) for f in os.listdir(STRIPE_FIXTURES_DIR)
                   if f.startswith(decorated_function_name + ':')])

def generate_and_save_stripe_fixture(decorated_function_name: str, mocked_function_name: str,
                                     mocked_function: CallableT) -> Callable[[Any, Any], Any]:  # nocoverage
    def _generate_and_save_stripe_fixture(*args: Any, **kwargs: Any) -> Any:
        # Note that mock is not the same as mocked_function, even though their
        # definitions look the same
        mock = operator.attrgetter(mocked_function_name)(sys.modules[__name__])
        fixture_path = stripe_fixture_path(decorated_function_name, mocked_function_name, mock.call_count)
        try:
            # Talk to Stripe
            stripe_object = mocked_function(*args, **kwargs)
        except stripe.error.StripeError as e:
            with open(fixture_path, 'w') as f:
                error_dict = e.__dict__
                error_dict["headers"] = dict(error_dict["headers"])
                f.write(json.dumps(error_dict, indent=2, separators=(',', ': '), sort_keys=True) + "\n")
            raise e
        with open(fixture_path, 'w') as f:
            if stripe_object is not None:
                f.write(str(stripe_object) + "\n")
            else:
                f.write("{}\n")
        return stripe_object
    return _generate_and_save_stripe_fixture

def read_stripe_fixture(decorated_function_name: str,
                        mocked_function_name: str) -> Callable[[Any, Any], Any]:
    def _read_stripe_fixture(*args: Any, **kwargs: Any) -> Any:
        mock = operator.attrgetter(mocked_function_name)(sys.modules[__name__])
        fixture_path = stripe_fixture_path(decorated_function_name, mocked_function_name, mock.call_count)
        fixture = ujson.load(open(fixture_path, 'r'))
        # Check for StripeError fixtures
        if "json_body" in fixture:
            requestor = stripe.api_requestor.APIRequestor()
            # This function will raise the relevant StripeError according to the fixture
            requestor.interpret_response(fixture["http_body"], fixture["http_status"], fixture["headers"])
        return stripe.util.convert_to_stripe_object(fixture)
    return _read_stripe_fixture

def delete_fixture_data(decorated_function: CallableT) -> None:  # nocoverage
    for fixture_file in fixture_files_for_function(decorated_function):
        os.remove(fixture_file)

def normalize_fixture_data(decorated_function: CallableT, keep: List[str]=[]) -> None:  # nocoverage
    # stripe ids are all of the form cus_D7OT2jf5YAtZQ2
    id_lengths = [
        ('cus', 14), ('sub', 14), ('si', 14), ('sli', 14), ('req', 14), ('tok', 24), ('card', 24),
        ('txn', 24), ('ch', 24), ('in', 24), ('ii', 24), ('test', 12), ('src_client_secret', 24),
        ('src', 24)]
    # We'll replace cus_D7OT2jf5YAtZQ2 with something like cus_NORMALIZED0001
    pattern_translations = {
        "%s_[A-Za-z0-9]{%d}" % (prefix, length): "%s_NORMALIZED%%0%dd" % (prefix, length - 10)
        for prefix, length in id_lengths
    }
    # We'll replace "invoice_prefix": "A35BC4Q" with something like "invoice_prefix": "NORMA01"
    pattern_translations.update({
        '"invoice_prefix": "([A-Za-z0-9]{7})"': 'NORMA%02d',
        '"fingerprint": "([A-Za-z0-9]{16})"': 'NORMALIZED%06d',
        '"number": "([A-Za-z0-9]{7}-[A-Za-z0-9]{4})"': 'NORMALI-%04d',
        '"address": "([A-Za-z0-9]{9}-test_[A-Za-z0-9]{12})"': '000000000-test_NORMALIZED%02d',
        # Don't use (..) notation, since the matched strings may be small integers that will also match
        # elsewhere in the file
        '"realm_id": "[0-9]+"': '"realm_id": "%d"',
        # Does not preserve relative ordering of the timestamps, nor any
        # coordination with the timestamps in setUp mocks (e.g. Plan.created).
        ': (1[5-9][0-9]{8})(?![0-9-])': '1%09d',
    })

    normalized_values = {pattern: {}
                         for pattern in pattern_translations.keys()}  # type: Dict[str, Dict[str, str]]
    for fixture_file in fixture_files_for_function(decorated_function):
        with open(fixture_file, "r") as f:
            file_content = f.read()
        for pattern, translation in pattern_translations.items():
            for match in re.findall(pattern, file_content):
                if match not in normalized_values[pattern]:
                    normalized_values[pattern][match] = translation % (len(normalized_values[pattern]) + 1,)
                file_content = file_content.replace(match, normalized_values[pattern][match])
        file_content = re.sub(r'(?<="risk_score": )(\d+)', '00', file_content)
        file_content = re.sub(r'(?<="times_redeemed": )(\d+)', '00', file_content)
        # Dates
        file_content = re.sub(r'(?<="Date": )"(.* GMT)"', '"NORMALIZED DATETIME"', file_content)
        file_content = re.sub(r'[0-3]\d [A-Z][a-z]{2} 20[1-2]\d', 'NORMALIZED DATE', file_content)
        # IP addresses
        file_content = re.sub(r'"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"', '"0.0.0.0"', file_content)
        # Even normalized timestamps vary a lot run to run, so suppress
        # timestamp differences entirely unless we explicitly ask to keep them
        if "timestamps" not in keep:
            file_content = re.sub(r': 10000000\d{2}(?=[,$])', ': 1000000000', file_content)

        with open(fixture_file, "w") as f:
            f.write(file_content)

MOCKED_STRIPE_FUNCTION_NAMES = ["stripe.{}".format(name) for name in [
    "Charge.list",
    "Coupon.create",
    "Customer.create", "Customer.retrieve", "Customer.save",
    "Invoice.list", "Invoice.upcoming",
    "InvoiceItem.create",
    "Plan.create",
    "Product.create",
    "Subscription.create", "Subscription.delete", "Subscription.retrieve", "Subscription.save",
    "Token.create",
]]

def mock_stripe(keep: List[str]=[], dont_mock: List[str]=[],
                generate: Optional[bool]=None) -> Callable[[CallableT], CallableT]:
    def _mock_stripe(decorated_function: CallableT) -> CallableT:
        generate_fixture = generate
        if generate_fixture is None:
            generate_fixture = GENERATE_STRIPE_FIXTURES
        for mocked_function_name in MOCKED_STRIPE_FUNCTION_NAMES:
            if mocked_function_name in dont_mock:
                continue
            mocked_function = operator.attrgetter(mocked_function_name)(sys.modules[__name__])
            if generate_fixture:
                side_effect = generate_and_save_stripe_fixture(
                    decorated_function.__name__, mocked_function_name, mocked_function)  # nocoverage
            else:
                side_effect = read_stripe_fixture(decorated_function.__name__, mocked_function_name)
            decorated_function = patch(mocked_function_name, side_effect=side_effect)(decorated_function)

        @wraps(decorated_function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if generate_fixture:  # nocoverage
                delete_fixture_data(decorated_function)
                val = decorated_function(*args, **kwargs)
                normalize_fixture_data(decorated_function, keep)
                return val
            else:
                return decorated_function(*args, **kwargs)
        return cast(CallableT, wrapped)
    return _mock_stripe

# A Kandra is a fictional character that can become anything. Used as a
# wildcard when testing for equality.
class Kandra(object):
    def __eq__(self, other: Any) -> bool:
        return True

def process_all_billing_log_entries() -> None:
    assert not RealmAuditLog.objects.get(pk=1).requires_billing_update
    processor = BillingProcessor.objects.create(
        log_row=RealmAuditLog.objects.get(pk=1), realm=None, state=BillingProcessor.DONE)
    while run_billing_processor_one_step(processor):
        pass

class StripeTest(ZulipTestCase):
    @mock_stripe(generate=False)
    def setUp(self, *mocks: Mock) -> None:
        call_command("setup_stripe")
        # Unfortunately this test suite is likely not robust to users being
        # added in populate_db. A quick hack for now to ensure get_seat_count is 8
        # for these tests (8, since that's what it was when the tests were written).
        realm = get_realm('zulip')
        seat_count = get_seat_count(get_realm('zulip'))
        assert(seat_count >= 8)
        if seat_count > 8:  # nocoverage
            for user in UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False) \
                                           .exclude(email__in=[
                                               self.example_email('hamlet'),
                                               self.example_email('iago')])[6:]:
                user.is_active = False
                user.save(update_fields=['is_active'])
        self.assertEqual(get_seat_count(get_realm('zulip')), 8)
        self.seat_count = 8
        self.signed_seat_count, self.salt = sign_string(str(self.seat_count))

    def get_signed_seat_count_from_response(self, response: HttpResponse) -> Optional[str]:
        match = re.search(r'name=\"signed_seat_count\" value=\"(.+)\"', response.content.decode("utf-8"))
        return match.group(1) if match else None

    def get_salt_from_response(self, response: HttpResponse) -> Optional[str]:
        match = re.search(r'name=\"salt\" value=\"(\w+)\"', response.content.decode("utf-8"))
        return match.group(1) if match else None

    def upgrade(self, invoice: bool=False, talk_to_stripe: bool=True,
                realm: Optional[Realm]=None, **kwargs: Any) -> HttpResponse:
        host_args = {}
        if realm is not None:
            host_args['HTTP_HOST'] = realm.host
        response = self.client_get("/upgrade/", **host_args)
        params = {
            'signed_seat_count': self.get_signed_seat_count_from_response(response),
            'salt': self.get_salt_from_response(response),
            'plan': Plan.CLOUD_ANNUAL}  # type: Dict[str, Any]
        if invoice:  # send_invoice
            params.update({
                'invoiced_seat_count': 123,
                'billing_modality': 'send_invoice'})
        else:  # charge_automatically
            stripe_token = None
            if not talk_to_stripe:
                stripe_token = 'token'
            stripe_token = kwargs.get('stripe_token', stripe_token)
            if stripe_token is None:
                stripe_token = stripe_create_token().id
            params.update({
                'stripe_token': stripe_token,
                'billing_modality': 'charge_automatically',
            })
        params.update(kwargs)
        return self.client_post("/upgrade/", params, **host_args)

    @patch("corporate.lib.stripe.billing_logger.error")
    def test_catch_stripe_errors(self, mock_billing_logger_error: Mock) -> None:
        @catch_stripe_errors
        def raise_invalid_request_error() -> None:
            raise stripe.error.InvalidRequestError(
                "message", "param", "code", json_body={})
        with self.assertRaises(BillingError) as context:
            raise_invalid_request_error()
        self.assertEqual('other stripe error', context.exception.description)
        mock_billing_logger_error.assert_called()

        @catch_stripe_errors
        def raise_card_error() -> None:
            error_message = "The card number is not a valid credit card number."
            json_body = {"error": {"message": error_message}}
            raise stripe.error.CardError(error_message, "number", "invalid_number",
                                         json_body=json_body)
        with self.assertRaises(StripeCardError) as context:
            raise_card_error()
        self.assertIn('not a valid credit card', context.exception.message)
        self.assertEqual('card error', context.exception.description)
        mock_billing_logger_error.assert_called()

    def test_billing_not_enabled(self) -> None:
        with self.settings(BILLING_ENABLED=False):
            self.login(self.example_email("iago"))
            response = self.client_get("/upgrade/")
            self.assert_in_success_response(["Page not found (404)"], response)

    @mock_stripe(keep=["timestamps"])
    def test_initial_upgrade(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        response = self.client_get("/upgrade/")
        self.assert_in_success_response(['Pay annually'], response)
        self.assertFalse(user.realm.has_seat_based_plan)
        self.assertNotEqual(user.realm.plan_type, Realm.STANDARD)
        self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

        # Click "Make payment" in Stripe Checkout
        self.upgrade()

        # Check that we correctly created Customer and Subscription objects in Stripe
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        self.assertEqual(stripe_customer.default_source.id[:5], 'card_')
        self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
        self.assertEqual(stripe_customer.discount, None)
        self.assertEqual(stripe_customer.email, user.email)
        self.assertEqual(dict(stripe_customer.metadata),
                         {'realm_id': str(user.realm.id), 'realm_str': 'zulip'})

        stripe_subscription = extract_current_subscription(stripe_customer)
        self.assertEqual(stripe_subscription.billing, 'charge_automatically')
        self.assertEqual(stripe_subscription.days_until_due, None)
        self.assertEqual(stripe_subscription.plan.id,
                         Plan.objects.get(nickname=Plan.CLOUD_ANNUAL).stripe_plan_id)
        self.assertEqual(stripe_subscription.quantity, self.seat_count)
        self.assertEqual(stripe_subscription.status, 'active')
        self.assertEqual(stripe_subscription.tax_percent, 0)

        # Check that we correctly populated Customer and RealmAuditLog in Zulip
        self.assertEqual(1, Customer.objects.filter(stripe_customer_id=stripe_customer.id,
                                                    realm=user.realm).count())
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', 'event_time').order_by('id'))
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.STRIPE_CUSTOMER_CREATED, timestamp_to_datetime(stripe_customer.created)),
            (RealmAuditLog.STRIPE_CARD_CHANGED, timestamp_to_datetime(stripe_customer.created)),
            # TODO: Add a test where stripe_customer.created != stripe_subscription.created
            (RealmAuditLog.STRIPE_PLAN_CHANGED, timestamp_to_datetime(stripe_subscription.created)),
            (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, Kandra()),
        ])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertTrue(realm.has_seat_based_plan)
        self.assertEqual(realm.plan_type, Realm.STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/billing/', response.url)

        # Check /billing has the correct information
        response = self.client_get("/billing/")
        self.assert_not_in_success_response(['Pay annually'], response)
        for substring in ['Your plan will renew on', '$%s.00' % (80 * self.seat_count,),
                          'Card ending in 4242', 'Update card']:
            self.assert_in_response(substring, response)

    @mock_stripe()
    def test_billing_page_permissions(self, *mocks: Mock) -> None:
        # Check that non-admins can access /upgrade via /billing, when there is no Customer object
        self.login(self.example_email('hamlet'))
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)
        # Check that non-admins can sign up and pay
        self.upgrade()
        # Check that the non-admin hamlet can still access /billing
        response = self.client_get("/billing/")
        self.assert_in_success_response(["for billing history or to make changes"], response)
        # Check admins can access billing, even though they are not a billing admin
        self.login(self.example_email('iago'))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["for billing history or to make changes"], response)
        # Check that a non-admin, non-billing admin user does not have access
        self.login(self.example_email("cordelia"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["You must be an organization administrator"], response)

    @mock_stripe(keep=["timestamps"])
    def test_upgrade_with_outdated_seat_count(self, *mocks: Mock) -> None:
        self.login(self.example_email("hamlet"))
        new_seat_count = 123
        # Change the seat count while the user is going through the upgrade flow
        with patch('corporate.lib.stripe.get_seat_count', return_value=new_seat_count):
            self.upgrade()
        # Check that the subscription call used the old quantity, not new_seat_count
        stripe_customer = stripe_get_customer(
            Customer.objects.get(realm=get_realm('zulip')).stripe_customer_id)
        stripe_subscription = extract_current_subscription(stripe_customer)
        self.assertEqual(stripe_subscription.quantity, self.seat_count)

        # Check that we have the STRIPE_PLAN_QUANTITY_RESET entry, and that we
        # correctly handled the requires_billing_update field
        audit_log_entries = list(RealmAuditLog.objects.order_by('-id')
                                 .values_list('event_type', 'event_time',
                                              'requires_billing_update')[:5])[::-1]
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.STRIPE_CUSTOMER_CREATED, timestamp_to_datetime(stripe_customer.created), False),
            (RealmAuditLog.STRIPE_CARD_CHANGED, timestamp_to_datetime(stripe_customer.created), False),
            # TODO: Ideally this test would force stripe_customer.created != stripe_subscription.created
            (RealmAuditLog.STRIPE_PLAN_CHANGED, timestamp_to_datetime(stripe_subscription.created), False),
            (RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET, timestamp_to_datetime(stripe_subscription.created), True),
            (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, Kandra(), False),
        ])
        self.assertEqual(ujson.loads(RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET).values_list('extra_data', flat=True).first()),
            {'quantity': new_seat_count})

    @mock_stripe()
    def test_upgrade_where_subscription_save_fails_at_first(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        # From https://stripe.com/docs/testing#cards: Attaching this card to
        # a Customer object succeeds, but attempts to charge the customer fail.
        self.upgrade(stripe_token=stripe_create_token('4000000000000341').id)
        # Check that we created a Customer object with has_billing_relationship False
        customer = Customer.objects.get(realm=get_realm('zulip'))
        self.assertFalse(customer.has_billing_relationship)
        original_stripe_customer_id = customer.stripe_customer_id
        # Check that we created a customer in stripe, with no subscription
        stripe_customer = stripe_get_customer(customer.stripe_customer_id)
        self.assertFalse(extract_current_subscription(stripe_customer))
        # Check that we correctly populated RealmAuditLog
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', flat=True).order_by('id'))
        self.assertEqual(audit_log_entries, [RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                                             RealmAuditLog.STRIPE_CARD_CHANGED])
        # Check that we did not update Realm
        realm = get_realm("zulip")
        self.assertFalse(realm.has_seat_based_plan)
        # Check that we still get redirected to /upgrade
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

        # Try again, with a valid card
        self.upgrade()
        customer = Customer.objects.get(realm=get_realm('zulip'))
        # Impossible to create two Customers, but check that we didn't
        # change stripe_customer_id and that we updated has_billing_relationship
        self.assertEqual(customer.stripe_customer_id, original_stripe_customer_id)
        self.assertTrue(customer.has_billing_relationship)
        # Check that we successfully added a subscription
        stripe_customer = stripe_get_customer(customer.stripe_customer_id)
        self.assertTrue(extract_current_subscription(stripe_customer))
        # Check that we correctly populated RealmAuditLog
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', flat=True).order_by('id'))
        self.assertEqual(audit_log_entries, [RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                                             RealmAuditLog.STRIPE_CARD_CHANGED,
                                             RealmAuditLog.STRIPE_CARD_CHANGED,
                                             RealmAuditLog.STRIPE_PLAN_CHANGED,
                                             RealmAuditLog.REALM_PLAN_TYPE_CHANGED])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertTrue(realm.has_seat_based_plan)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/billing/', response.url)

    def test_upgrade_with_tampered_seat_count(self) -> None:
        self.login(self.example_email("hamlet"))
        response = self.upgrade(talk_to_stripe=False, salt='badsalt')
        self.assert_in_success_response(["Upgrade to Zulip Standard"], response)
        self.assertEqual(response['error_description'], 'tampered seat count')

    def test_upgrade_with_tampered_plan(self) -> None:
        # Test with an unknown plan
        self.login(self.example_email("hamlet"))
        response = self.upgrade(talk_to_stripe=False, plan='badplan')
        self.assert_in_success_response(["Upgrade to Zulip Standard"], response)
        self.assertEqual(response['error_description'], 'tampered plan')
        # Test with a plan that's valid, but not if you're paying by invoice
        response = self.upgrade(invoice=True, talk_to_stripe=False, plan=Plan.CLOUD_MONTHLY)
        self.assert_in_success_response(["Upgrade to Zulip Standard"], response)
        self.assertEqual(response['error_description'], 'tampered plan')

    def test_upgrade_with_insufficient_invoiced_seat_count(self) -> None:
        self.login(self.example_email("hamlet"))
        # Test invoicing for less than MIN_INVOICED_SEAT_COUNT
        response = self.upgrade(invoice=True, talk_to_stripe=False,
                                invoiced_seat_count=MIN_INVOICED_SEAT_COUNT - 1)
        self.assert_in_success_response(["Upgrade to Zulip Standard",
                                         "at least %d users" % (MIN_INVOICED_SEAT_COUNT,)], response)
        self.assertEqual(response['error_description'], 'lowball seat count')
        # Test invoicing for less than your user count
        with patch("corporate.views.MIN_INVOICED_SEAT_COUNT", 3):
            response = self.upgrade(invoice=True, talk_to_stripe=False, invoiced_seat_count=4)
        self.assert_in_success_response(["Upgrade to Zulip Standard",
                                         "at least %d users" % (self.seat_count,)], response)
        self.assertEqual(response['error_description'], 'lowball seat count')
        # Test not setting an invoiced_seat_count
        response = self.upgrade(invoice=True, talk_to_stripe=False, invoiced_seat_count=None)
        self.assert_in_success_response(["Upgrade to Zulip Standard",
                                         "at least %d users" % (MIN_INVOICED_SEAT_COUNT,)], response)
        self.assertEqual(response['error_description'], 'lowball seat count')

    @patch("corporate.lib.stripe.billing_logger.error")
    def test_upgrade_with_uncaught_exception(self, mock_: Mock) -> None:
        self.login(self.example_email("hamlet"))
        with patch("corporate.views.process_initial_upgrade", side_effect=Exception):
            response = self.upgrade(talk_to_stripe=False)
        self.assert_in_success_response(["Upgrade to Zulip Standard",
                                         "Something went wrong. Please contact"], response)
        self.assertEqual(response['error_description'], 'uncaught exception during upgrade')

    @mock_stripe(keep=["timestamps"])
    def test_upgrade_billing_by_invoice(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        self.upgrade(invoice=True)
        process_all_billing_log_entries()

        # Check that we correctly created a Customer in Stripe
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        self.assertEqual(stripe_customer.email, user.email)
        # It can take a second for Stripe to attach the source to the
        # customer, and in particular it may not be attached at the time
        # stripe_get_customer is called above, causing test flakes.
        # So commenting the next line out, but leaving it here so future readers know what
        # is supposed to happen here (e.g. the default_source is not None as it would be if
        # we had not added a Subscription).
        # self.assertEqual(stripe_customer.default_source.type, 'ach_credit_transfer')

        # Check that we correctly created a Subscription in Stripe
        stripe_subscription = extract_current_subscription(stripe_customer)
        self.assertEqual(stripe_subscription.billing, 'send_invoice')
        self.assertEqual(stripe_subscription.days_until_due, DEFAULT_INVOICE_DAYS_UNTIL_DUE)
        self.assertEqual(stripe_subscription.plan.id,
                         Plan.objects.get(nickname=Plan.CLOUD_ANNUAL).stripe_plan_id)
        self.assertEqual(stripe_subscription.quantity, get_seat_count(user.realm))
        self.assertEqual(stripe_subscription.status, 'active')
        # Check that we correctly created an initial Invoice in Stripe
        for stripe_invoice in stripe.Invoice.list(customer=stripe_customer.id, limit=1):
            self.assertTrue(stripe_invoice.auto_advance)
            self.assertEqual(stripe_invoice.billing, 'send_invoice')
            self.assertEqual(stripe_invoice.billing_reason, 'subscription_create')
            # Transitions to 'open' after 1-2 hours
            self.assertEqual(stripe_invoice.status, 'draft')
            # Very important. Check that we're invoicing for 123, and not get_seat_count
            self.assertEqual(stripe_invoice.amount_due, 8000*123)

        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertTrue(realm.has_seat_based_plan)
        self.assertEqual(realm.plan_type, Realm.STANDARD)
        # Check that we created a Customer in Zulip
        self.assertEqual(1, Customer.objects.filter(stripe_customer_id=stripe_customer.id,
                                                    realm=realm).count())
        # Check that RealmAuditLog has STRIPE_PLAN_QUANTITY_RESET, and doesn't have STRIPE_CARD_CHANGED
        audit_log_entries = list(RealmAuditLog.objects.order_by('-id')
                                 .values_list('event_type', 'event_time',
                                              'requires_billing_update')[:4])[::-1]
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.STRIPE_CUSTOMER_CREATED, timestamp_to_datetime(stripe_customer.created), False),
            (RealmAuditLog.STRIPE_PLAN_CHANGED, timestamp_to_datetime(stripe_subscription.created), False),
            (RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET, timestamp_to_datetime(stripe_subscription.created), True),
            (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, Kandra(), False),
        ])
        self.assertEqual(ujson.loads(RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET).values_list('extra_data', flat=True).first()),
            {'quantity': self.seat_count})

        # Check /billing has the correct information
        response = self.client_get("/billing/")
        self.assert_not_in_success_response(['Pay annually', 'Update card'], response)
        for substring in ['Your plan will renew on', 'Billed by invoice']:
            self.assert_in_response(substring, response)

    def test_redirect_for_billing_home(self) -> None:
        user = self.example_user("iago")
        self.login(user.email)
        # No Customer yet; check that we are redirected to /upgrade
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

        # Customer, but no billing relationship; check that we are still redirected to /upgrade
        Customer.objects.create(
            realm=user.realm, stripe_customer_id='cus_123', has_billing_relationship=False)
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

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

    def test_sign_string(self) -> None:
        string = "abc"
        signed_string, salt = sign_string(string)
        self.assertEqual(string, unsign_string(signed_string, salt))

        with self.assertRaises(signing.BadSignature):
            unsign_string(signed_string, "randomsalt")

    # This tests both the payment method string, and also is a very basic
    # test that the various upgrade paths involving non-standard payment
    # histories don't throw errors
    @mock_stripe()
    def test_payment_method_string(self, *mocks: Mock) -> None:
        # If you signup with a card, we should show your card as the payment method
        # Already tested in test_initial_upgrade

        # If you pay by invoice, your payment method should be
        # "Billed by invoice", even if you have a card on file
        user = self.example_user("hamlet")
        do_create_customer(user, stripe_create_token().id)
        self.login(user.email)
        self.upgrade(invoice=True)
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        self.assertEqual('Billed by invoice', payment_method_string(stripe_customer))

        # If you signup with a card and then downgrade, we still have your
        # card on file, and should show it
        realm = do_create_realm('realm1', 'realm1')
        user = do_create_user('name@realm1.com', 'password', realm, 'name', 'name')
        self.login(user.email, password='password', realm=realm)
        self.upgrade(realm=realm)
        with patch('corporate.lib.stripe.preview_invoice_total_for_downgrade', return_value=1):
            process_downgrade(user)
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        self.assertEqual('Card ending in 4242', payment_method_string(stripe_customer))

        # If you signup via invoice, and then downgrade immediately, the
        # default_source is in a weird intermediate state.
        realm = do_create_realm('realm2', 'realm2')
        user = do_create_user('name@realm2.com', 'password', realm, 'name', 'name')
        self.login(user.email, password='password', realm=realm)
        self.upgrade(invoice=True, realm=realm)
        with patch('corporate.lib.stripe.preview_invoice_total_for_downgrade', return_value=1):
            process_downgrade(user)
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        # Could be either one, depending on exact timing with the test
        self.assertTrue('Unknown payment method' in payment_method_string(stripe_customer) or
                        'No payment method' in payment_method_string(stripe_customer))

    @mock_stripe()
    def test_attach_discount_to_realm(self, *mocks: Mock) -> None:
        # Attach discount before Stripe customer exists
        user = self.example_user('hamlet')
        attach_discount_to_realm(user, 85)
        self.login(user.email)
        # Check that the discount appears in page_params
        self.assert_in_success_response(['85'], self.client_get("/upgrade/"))
        self.upgrade()
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        assert(stripe_customer.discount is not None)  # for mypy
        self.assertEqual(stripe_customer.discount.coupon.percent_off, 85.0)
        # Check that the customer was charged the discounted amount
        charges = stripe.Charge.list(customer=stripe_customer.id)
        for charge in charges:
            self.assertEqual(charge.amount, get_seat_count(user.realm) * 80 * 15)
        # Check upcoming invoice reflects the discount
        upcoming_invoice = stripe.Invoice.upcoming(customer=stripe_customer.id)
        self.assertEqual(upcoming_invoice.amount_due, get_seat_count(user.realm) * 80 * 15)

        # Attach discount to existing Stripe customer
        attach_discount_to_realm(user, 25)
        # Check upcoming invoice reflects the new discount
        upcoming_invoice = stripe.Invoice.upcoming(customer=stripe_customer.id)
        self.assertEqual(upcoming_invoice.amount_due, get_seat_count(user.realm) * 80 * 75)

    # Tests upgrade followed by immediate downgrade. Doesn't test the
    # calculations for how much credit they should get if they had the
    # subscription for more than 0 time.
    @mock_stripe(keep=["timestamps"])
    def test_downgrade(self, *mocks: Mock) -> None:
        user = self.example_user('iago')
        self.login(user.email)
        self.upgrade()
        realm = get_realm('zulip')
        self.assertEqual(realm.has_seat_based_plan, True)
        self.assertEqual(realm.plan_type, Realm.STANDARD)
        RealmAuditLog.objects.filter(realm=realm).delete()

        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        self.assertEqual(stripe_customer.account_balance, 0)
        # Change subscription in Stripe, but don't pay for it
        stripe_subscription = extract_current_subscription(stripe_customer)
        stripe_subscription.quantity = 123
        stripe.Subscription.save(stripe_subscription)

        response = self.client_post("/json/billing/downgrade", {})
        self.assert_json_success(response)
        stripe_customer = stripe_get_customer(stripe_customer.id)
        self.assertEqual(stripe_customer.account_balance, self.seat_count * -8000)
        self.assertIsNone(extract_current_subscription(stripe_customer))
        stripe_subscription = stripe.Subscription.retrieve(stripe_subscription.id)
        self.assertEqual(stripe_subscription.status, "canceled")

        realm = get_realm('zulip')
        self.assertEqual(realm.plan_type, Realm.LIMITED)
        self.assertFalse(realm.has_seat_based_plan)

        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', 'event_time',
                                              'requires_billing_update').order_by('id'))
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.STRIPE_PLAN_CHANGED,
             timestamp_to_datetime(stripe_subscription.canceled_at), False),
            (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, Kandra(), False),
        ])
        self.assertEqual(ujson.loads(RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.STRIPE_PLAN_CHANGED).values_list('extra_data', flat=True).first()),
            {'plan': None, 'quantity': 123})

    @mock_stripe()
    def test_downgrade_with_no_subscription(self, *mocks: Mock) -> None:
        user = self.example_user("iago")
        do_create_customer(user)
        self.login(user.email)
        with patch("stripe.Customer.save") as mock_save_customer:
            with patch("corporate.lib.stripe.billing_logger.error"):
                response = self.client_post("/json/billing/downgrade", {})
        mock_save_customer.assert_not_called()
        self.assert_json_error_contains(response, 'Please reload')
        self.assertEqual(ujson.loads(response.content)['error_description'], 'downgrade without subscription')

    @mock_stripe()
    def test_downgrade_with_money_owed(self, *mocks: Mock) -> None:
        user = self.example_user('iago')
        self.login(user.email)
        self.upgrade()
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        self.assertEqual(stripe_customer.account_balance, 0)
        stripe_subscription = extract_current_subscription(stripe_customer)
        # Create a situation where customer net owes us money
        stripe.InvoiceItem.create(
            amount=100000,
            currency='usd',
            customer=stripe_customer,
            subscription=stripe_subscription)

        response = self.client_post("/json/billing/downgrade", {})
        self.assert_json_success(response)
        stripe_customer = stripe_get_customer(stripe_customer.id)
        # Check that positive balance was forgiven
        self.assertEqual(stripe_customer.account_balance, 0)
        self.assertIsNone(extract_current_subscription(stripe_customer))
        stripe_subscription = stripe.Subscription.retrieve(stripe_subscription.id)
        self.assertEqual(stripe_subscription.status, "canceled")

    @mock_stripe()
    def test_replace_payment_source(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        self.upgrade()
        # Try replacing with a valid card
        stripe_token = stripe_create_token(card_number='5555555555554444').id
        response = self.client_post("/json/billing/sources/change",
                                    {'stripe_token': ujson.dumps(stripe_token)})
        self.assert_json_success(response)
        number_of_sources = 0
        for stripe_source in stripe_get_customer(Customer.objects.first().stripe_customer_id).sources:
            self.assertEqual(cast(stripe.Card, stripe_source).last4, '4444')
            number_of_sources += 1
        self.assertEqual(number_of_sources, 1)
        audit_log_entry = RealmAuditLog.objects.order_by('-id') \
                                               .values_list('acting_user', 'event_type').first()
        self.assertEqual(audit_log_entry, (user.id, RealmAuditLog.STRIPE_CARD_CHANGED))
        RealmAuditLog.objects.filter(acting_user=user).delete()

        # Try replacing with an invalid card
        stripe_token = stripe_create_token(card_number='4000000000009987').id
        with patch("corporate.lib.stripe.billing_logger.error") as mock_billing_logger:
            response = self.client_post("/json/billing/sources/change",
                                        {'stripe_token': ujson.dumps(stripe_token)})
        mock_billing_logger.assert_called()
        self.assertEqual(ujson.loads(response.content)['error_description'], 'card error')
        self.assert_json_error_contains(response, 'Your card was declined')
        number_of_sources = 0
        for stripe_source in stripe_get_customer(Customer.objects.first().stripe_customer_id).sources:
            self.assertEqual(cast(stripe.Card, stripe_source).last4, '4444')
            number_of_sources += 1
        self.assertEqual(number_of_sources, 1)
        self.assertFalse(RealmAuditLog.objects.filter(event_type=RealmAuditLog.STRIPE_CARD_CHANGED).exists())

    @mock_stripe(keep=["timestamps"], dont_mock=["stripe.Subscription.save"])
    def test_billing_quantity_changes_end_to_end(self, *mocks: Mock) -> None:
        # A full end to end check would check the InvoiceItems, but this test is partway there
        self.login(self.example_email("hamlet"))
        processor = BillingProcessor.objects.create(
            log_row=RealmAuditLog.objects.order_by('id').first(), state=BillingProcessor.DONE)

        def check_billing_processor_update(event_type: str, quantity: int) -> None:
            def check_subscription_save(subscription: stripe.Subscription, idempotency_key: str) -> None:
                self.assertEqual(subscription.quantity, quantity)
                log_row = RealmAuditLog.objects.filter(
                    event_type=event_type, requires_billing_update=True).order_by('-id').first()
                self.assertEqual(idempotency_key.split('+')[0],
                                 'process_billing_log_entry:%s' % (log_row.id,))
                self.assertEqual(subscription.proration_date, datetime_to_timestamp(log_row.event_time))
            with patch.object(stripe.Subscription, 'save', autospec=True,
                              side_effect=check_subscription_save):
                run_billing_processor_one_step(processor)

        # Test STRIPE_PLAN_QUANTITY_RESET
        new_seat_count = 123
        # change the seat count while the user is going through the upgrade flow
        with patch('corporate.lib.stripe.get_seat_count', return_value=new_seat_count):
            self.upgrade()
        check_billing_processor_update(RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET, new_seat_count)

        # Test USER_CREATED
        user = do_create_user('newuser@zulip.com', 'password', get_realm('zulip'), 'full name', 'short name')
        check_billing_processor_update(RealmAuditLog.USER_CREATED, self.seat_count + 1)

        # Test USER_DEACTIVATED
        do_deactivate_user(user)
        check_billing_processor_update(RealmAuditLog.USER_DEACTIVATED, self.seat_count - 1)

        # Test USER_REACTIVATED
        do_reactivate_user(user)
        check_billing_processor_update(RealmAuditLog.USER_REACTIVATED, self.seat_count + 1)

        # Test USER_ACTIVATED
        # Not a proper use of do_activate_user, but it's fine to call it like this for this test
        do_activate_user(user)
        check_billing_processor_update(RealmAuditLog.USER_ACTIVATED, self.seat_count + 1)

class RequiresBillingUpdateTest(ZulipTestCase):
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

class RequiresBillingAccessTest(ZulipTestCase):
    def setUp(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.is_billing_admin = True
        hamlet.save(update_fields=["is_billing_admin"])

    # mocked_function_name will typically be something imported from
    # stripe.py. In theory we could have endpoints that need to mock
    # multiple functions, but we'll cross that bridge when we get there.
    def _test_endpoint(self, url: str, mocked_function_name: str,
                       request_data: Optional[Dict[str, Any]]={}) -> None:
        # Normal users do not have access
        self.login(self.example_email('cordelia'))
        response = self.client_post(url, request_data)
        self.assert_json_error_contains(response, "Must be a billing administrator or an organization")

        # Billing admins have access
        self.login(self.example_email('hamlet'))
        with patch("corporate.views.{}".format(mocked_function_name)) as mocked1:
            response = self.client_post(url, request_data)
        self.assert_json_success(response)
        mocked1.assert_called()

        # Realm admins have access, even if they are not billing admins
        self.login(self.example_email('iago'))
        with patch("corporate.views.{}".format(mocked_function_name)) as mocked2:
            response = self.client_post(url, request_data)
        self.assert_json_success(response)
        mocked2.assert_called()

    def test_json_endpoints(self) -> None:
        params = [
            ("/json/billing/sources/change", "do_replace_payment_source",
             {'stripe_token': ujson.dumps('token')}),
            ("/json/billing/downgrade", "process_downgrade", {})
        ]  # type: List[Tuple[str, str, Dict[str, Any]]]

        for (url, mocked_function_name, data) in params:
            self._test_endpoint(url, mocked_function_name, data)

        # Make sure that we are testing all the JSON endpoints
        # Quite a hack, but probably fine for now
        string_with_all_endpoints = str(get_resolver('corporate.urls').reverse_dict)
        json_endpoints = set([word.strip("\"'()[],$") for word in string_with_all_endpoints.split()
                              if 'json' in word])
        self.assertEqual(len(json_endpoints), len(params))

class BillingProcessorTest(ZulipTestCase):
    def add_log_entry(self, realm: Realm=get_realm('zulip'),
                      event_type: str=RealmAuditLog.USER_CREATED,
                      requires_billing_update: bool=True) -> RealmAuditLog:
        return RealmAuditLog.objects.create(
            realm=realm, event_time=datetime.datetime(2001, 2, 3, 4, 5, 6).replace(tzinfo=timezone_utc),
            event_type=event_type, requires_billing_update=requires_billing_update)

    def test_get_next_billing_log_entry(self) -> None:
        second_realm = Realm.objects.create(string_id='second', name='second')
        entry1 = self.add_log_entry(realm=second_realm)
        realm_processor = BillingProcessor.objects.create(
            realm=second_realm, log_row=entry1, state=BillingProcessor.DONE)
        entry2 = self.add_log_entry()
        # global processor
        processor = BillingProcessor.objects.create(
            log_row=entry2, state=BillingProcessor.STARTED)

        # Test STARTED, STALLED, and typo'ed state entry
        self.assertEqual(entry2, get_next_billing_log_entry(processor))
        processor.state = BillingProcessor.STALLED
        processor.save()
        with self.assertRaises(AssertionError):
            get_next_billing_log_entry(processor)
        processor.state = 'typo'
        processor.save()
        with self.assertRaisesRegex(BillingError, 'unknown processor state'):
            get_next_billing_log_entry(processor)

        # Test global processor is handled correctly
        processor.state = BillingProcessor.DONE
        processor.save()
        # test it ignores entries with requires_billing_update=False
        entry3 = self.add_log_entry(requires_billing_update=False)
        # test it ignores entries with realm processors
        entry4 = self.add_log_entry(realm=second_realm)
        self.assertIsNone(get_next_billing_log_entry(processor))
        # test it does catch entries it should
        entry5 = self.add_log_entry()
        self.assertEqual(entry5, get_next_billing_log_entry(processor))

        # Test realm processor is handled correctly
        # test it gets the entry with its realm, and ignores the entry with
        # requires_billing_update=False, when global processor is up ahead
        processor.log_row = entry5
        processor.save()
        self.assertEqual(entry4, get_next_billing_log_entry(realm_processor))

        # test it doesn't run past the global processor
        processor.log_row = entry3
        processor.save()
        self.assertIsNone(get_next_billing_log_entry(realm_processor))

    def test_run_billing_processor_logic_when_no_errors(self) -> None:
        second_realm = Realm.objects.create(string_id='second', name='second')
        entry1 = self.add_log_entry(realm=second_realm)
        realm_processor = BillingProcessor.objects.create(
            realm=second_realm, log_row=entry1, state=BillingProcessor.DONE)
        entry2 = self.add_log_entry()
        # global processor
        processor = BillingProcessor.objects.create(
            log_row=entry2, state=BillingProcessor.DONE)

        # Test nothing to process
        # test nothing changes, for global processor
        self.assertFalse(run_billing_processor_one_step(processor))
        self.assertEqual(2, BillingProcessor.objects.count())
        # test realm processor gets deleted
        self.assertFalse(run_billing_processor_one_step(realm_processor))
        self.assertEqual(1, BillingProcessor.objects.count())
        self.assertEqual(1, BillingProcessor.objects.filter(realm=None).count())

        # Test something to process
        processor.state = BillingProcessor.STARTED
        processor.save()
        realm_processor = BillingProcessor.objects.create(
            realm=second_realm, log_row=entry1, state=BillingProcessor.STARTED)
        Customer.objects.create(realm=get_realm('zulip'), stripe_customer_id='cust_1')
        Customer.objects.create(realm=second_realm, stripe_customer_id='cust_2')
        with patch('corporate.lib.stripe.do_adjust_subscription_quantity'):
            # test return values
            self.assertTrue(run_billing_processor_one_step(processor))
            self.assertTrue(run_billing_processor_one_step(realm_processor))
        # test no processors get added or deleted
        self.assertEqual(2, BillingProcessor.objects.count())

    @patch("corporate.lib.stripe.billing_logger.error")
    def test_run_billing_processor_with_card_error(self, mock_billing_logger_error: Mock) -> None:
        second_realm = Realm.objects.create(string_id='second', name='second')
        entry1 = self.add_log_entry(realm=second_realm)
        # global processor
        processor = BillingProcessor.objects.create(
            log_row=entry1, state=BillingProcessor.STARTED)
        Customer.objects.create(realm=second_realm, stripe_customer_id='cust_2')

        # card error on global processor should create a new realm processor
        with patch('corporate.lib.stripe.do_adjust_subscription_quantity',
                   side_effect=stripe.error.CardError('message', 'param', 'code', json_body={})):
            self.assertTrue(run_billing_processor_one_step(processor))
        self.assertEqual(2, BillingProcessor.objects.count())
        self.assertTrue(BillingProcessor.objects.filter(
            realm=None, log_row=entry1, state=BillingProcessor.SKIPPED).exists())
        self.assertTrue(BillingProcessor.objects.filter(
            realm=second_realm, log_row=entry1, state=BillingProcessor.STALLED).exists())
        mock_billing_logger_error.assert_called()

        # card error on realm processor should change state to STALLED
        realm_processor = BillingProcessor.objects.filter(realm=second_realm).first()
        realm_processor.state = BillingProcessor.STARTED
        realm_processor.save()
        with patch('corporate.lib.stripe.do_adjust_subscription_quantity',
                   side_effect=stripe.error.CardError('message', 'param', 'code', json_body={})):
            self.assertTrue(run_billing_processor_one_step(realm_processor))
        self.assertEqual(2, BillingProcessor.objects.count())
        self.assertTrue(BillingProcessor.objects.filter(
            realm=second_realm, log_row=entry1, state=BillingProcessor.STALLED).exists())
        mock_billing_logger_error.assert_called()

    @patch("corporate.lib.stripe.billing_logger.error")
    def test_run_billing_processor_with_uncaught_error(self, mock_billing_logger_error: Mock) -> None:
        # This tests three different things:
        # * That run_billing_processor_one_step passes through exceptions that
        #   are not StripeCardError
        # * That process_billing_log_entry catches StripeErrors and re-raises them as BillingErrors
        # * That processor.state=STARTED for non-StripeCardError exceptions
        entry1 = self.add_log_entry()
        entry2 = self.add_log_entry()
        processor = BillingProcessor.objects.create(
            log_row=entry1, state=BillingProcessor.DONE)
        Customer.objects.create(realm=get_realm('zulip'), stripe_customer_id='cust_1')
        with patch('corporate.lib.stripe.do_adjust_subscription_quantity',
                   side_effect=stripe.error.StripeError('message', json_body={})):
            with self.assertRaises(BillingError):
                run_billing_processor_one_step(processor)
        mock_billing_logger_error.assert_called()
        # check processor.state is STARTED
        self.assertTrue(BillingProcessor.objects.filter(
            log_row=entry2, state=BillingProcessor.STARTED).exists())

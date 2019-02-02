from datetime import datetime, timedelta
from decimal import Decimal
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
from django.core.urlresolvers import get_resolver
from django.http import HttpResponse
from django.utils.timezone import utc as timezone_utc

import stripe

from zerver.lib.actions import do_deactivate_user, do_create_user, \
    do_activate_user, do_reactivate_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zerver.models import Realm, UserProfile, get_realm, RealmAuditLog
from corporate.lib.stripe import catch_stripe_errors, attach_discount_to_realm, \
    get_seat_count, sign_string, unsign_string, \
    BillingError, StripeCardError, stripe_get_customer, \
    MIN_INVOICED_LICENSES, \
    add_months, next_month, \
    compute_plan_parameters, update_or_create_stripe_customer, \
    process_initial_upgrade, add_plan_renewal_to_license_ledger_if_needed, \
    update_license_ledger_if_needed, update_license_ledger_for_automanaged_plan, \
    invoice_plan, invoice_plans_as_needed
from corporate.models import Customer, CustomerPlan, LicenseLedger

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
    return "{}/{}--{}.{}.json".format(
        STRIPE_FIXTURES_DIR, decorated_function_name, mocked_function_name[7:], call_count)

def fixture_files_for_function(decorated_function: CallableT) -> List[str]:  # nocoverage
    decorated_function_name = decorated_function.__name__
    if decorated_function_name[:5] == 'test_':
        decorated_function_name = decorated_function_name[5:]
    return sorted(['{}/{}'.format(STRIPE_FIXTURES_DIR, f) for f in os.listdir(STRIPE_FIXTURES_DIR)
                   if f.startswith(decorated_function_name + '--')])

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

def normalize_fixture_data(decorated_function: CallableT,
                           tested_timestamp_fields: List[str]=[]) -> None:  # nocoverage
    # stripe ids are all of the form cus_D7OT2jf5YAtZQ2
    id_lengths = [
        ('cus', 14), ('sub', 14), ('si', 14), ('sli', 14), ('req', 14), ('tok', 24), ('card', 24),
        ('txn', 24), ('ch', 24), ('in', 24), ('ii', 24), ('test', 12), ('src_client_secret', 24),
        ('src', 24), ('invst', 26), ('acct', 16), ('rcpt', 31)]
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
    })
    # Normalizing across all timestamps still causes a lot of variance run to run, which is
    # why we're doing something a bit more complicated
    for i, timestamp_field in enumerate(tested_timestamp_fields):
        # Don't use (..) notation, since the matched timestamp can easily appear in other fields
        pattern_translations[
            '"%s": 1[5-9][0-9]{8}(?![0-9-])' % (timestamp_field,)
        ] = '"%s": 1%02d%%07d' % (timestamp_field, i+1)

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
        # All timestamps not in tested_timestamp_fields
        file_content = re.sub(r': (1[5-9][0-9]{8})(?![0-9-])', ': 1000000000', file_content)

        with open(fixture_file, "w") as f:
            f.write(file_content)

MOCKED_STRIPE_FUNCTION_NAMES = ["stripe.{}".format(name) for name in [
    "Charge.create", "Charge.list",
    "Coupon.create",
    "Customer.create", "Customer.retrieve", "Customer.save",
    "Invoice.create", "Invoice.finalize_invoice", "Invoice.list", "Invoice.upcoming",
    "InvoiceItem.create", "InvoiceItem.list",
    "Plan.create",
    "Product.create",
    "Subscription.create", "Subscription.delete", "Subscription.retrieve", "Subscription.save",
    "Token.create",
]]

def mock_stripe(tested_timestamp_fields: List[str]=[],
                generate: Optional[bool]=None) -> Callable[[CallableT], CallableT]:
    def _mock_stripe(decorated_function: CallableT) -> CallableT:
        generate_fixture = generate
        if generate_fixture is None:
            generate_fixture = GENERATE_STRIPE_FIXTURES
        for mocked_function_name in MOCKED_STRIPE_FUNCTION_NAMES:
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
                normalize_fixture_data(decorated_function, tested_timestamp_fields)
                return val
            else:
                return decorated_function(*args, **kwargs)
        return cast(CallableT, wrapped)
    return _mock_stripe

# A Kandra is a fictional character that can become anything. Used as a
# wildcard when testing for equality.
class Kandra(object):  # nocoverage: TODO
    def __eq__(self, other: Any) -> bool:
        return True

class StripeTestCase(ZulipTestCase):
    def setUp(self, *mocks: Mock) -> None:
        # This test suite is not robust to users being added in populate_db. The following
        # hack ensures get_seat_count is fixed, even as populate_db changes.
        realm = get_realm('zulip')
        seat_count = get_seat_count(realm)
        assert(seat_count >= 6)
        for user in UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False, is_guest=False) \
                                       .exclude(email__in=[
                                           self.example_email('hamlet'),
                                           self.example_email('iago')])[:seat_count-6]:
            user.is_active = False
            user.save(update_fields=['is_active'])
        self.assertEqual(get_seat_count(realm), 6)
        self.seat_count = 6
        self.signed_seat_count, self.salt = sign_string(str(self.seat_count))
        # Choosing dates with corresponding timestamps below 1500000000 so that they are
        # not caught by our timestamp normalization regex in normalize_fixture_data
        self.now = datetime(2012, 1, 2, 3, 4, 5).replace(tzinfo=timezone_utc)
        self.next_month = datetime(2012, 2, 2, 3, 4, 5).replace(tzinfo=timezone_utc)
        self.next_year = datetime(2013, 1, 2, 3, 4, 5).replace(tzinfo=timezone_utc)

    def get_signed_seat_count_from_response(self, response: HttpResponse) -> Optional[str]:
        match = re.search(r'name=\"signed_seat_count\" value=\"(.+)\"', response.content.decode("utf-8"))
        return match.group(1) if match else None

    def get_salt_from_response(self, response: HttpResponse) -> Optional[str]:
        match = re.search(r'name=\"salt\" value=\"(\w+)\"', response.content.decode("utf-8"))
        return match.group(1) if match else None

    def upgrade(self, invoice: bool=False, talk_to_stripe: bool=True,
                realm: Optional[Realm]=None, del_args: List[str]=[],
                **kwargs: Any) -> HttpResponse:
        host_args = {}
        if realm is not None:  # nocoverage: TODO
            host_args['HTTP_HOST'] = realm.host
        response = self.client_get("/upgrade/", **host_args)
        params = {
            'schedule': 'annual',
            'signed_seat_count': self.get_signed_seat_count_from_response(response),
            'salt': self.get_salt_from_response(response)}  # type: Dict[str, Any]
        if invoice:  # send_invoice
            params.update({
                'billing_modality': 'send_invoice',
                'licenses': 123})
        else:  # charge_automatically
            stripe_token = None
            if not talk_to_stripe:
                stripe_token = 'token'
            stripe_token = kwargs.get('stripe_token', stripe_token)
            if stripe_token is None:
                stripe_token = stripe_create_token().id
            params.update({
                'billing_modality': 'charge_automatically',
                'license_management': 'automatic',
                'stripe_token': stripe_token,
            })

        params.update(kwargs)
        for key in del_args:
            if key in params:
                del params[key]
        for key, value in params.items():
            params[key] = ujson.dumps(value)
        return self.client_post("/json/billing/upgrade", params, **host_args)

    # Upgrade without talking to Stripe
    def local_upgrade(self, *args: Any) -> None:
        class StripeMock(object):
            def __init__(self, depth: int=1):
                self.id = 'id'
                self.created = '1000'
                self.last4 = '4242'
                if depth == 1:
                    self.source = StripeMock(depth=2)

        def upgrade_func(*args: Any) -> Any:
            return process_initial_upgrade(self.example_user('hamlet'), *args[:4])

        for mocked_function_name in MOCKED_STRIPE_FUNCTION_NAMES:
            upgrade_func = patch(mocked_function_name, return_value=StripeMock())(upgrade_func)
        upgrade_func(*args)

class StripeTest(StripeTestCase):
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

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_by_card(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        response = self.client_get("/upgrade/")
        self.assert_in_success_response(['Pay annually'], response)
        self.assertNotEqual(user.realm.plan_type, Realm.STANDARD)
        self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

        # Click "Make payment" in Stripe Checkout
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.upgrade()

        # Check that we correctly created a Customer object in Stripe
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        self.assertEqual(stripe_customer.default_source.id[:5], 'card_')
        self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
        self.assertEqual(stripe_customer.discount, None)
        self.assertEqual(stripe_customer.email, user.email)
        self.assertEqual(dict(stripe_customer.metadata),
                         {'realm_id': str(user.realm.id), 'realm_str': 'zulip'})
        # Check Charges in Stripe
        stripe_charges = [charge for charge in stripe.Charge.list(customer=stripe_customer.id)]
        self.assertEqual(len(stripe_charges), 1)
        self.assertEqual(stripe_charges[0].amount, 8000 * self.seat_count)
        # TODO: fix Decimal
        self.assertEqual(stripe_charges[0].description,
                         "Upgrade to Zulip Standard, $80.0 x {}".format(self.seat_count))
        self.assertEqual(stripe_charges[0].receipt_email, user.email)
        self.assertEqual(stripe_charges[0].statement_descriptor, "Zulip Standard")
        # Check Invoices in Stripe
        stripe_invoices = [invoice for invoice in stripe.Invoice.list(customer=stripe_customer.id)]
        self.assertEqual(len(stripe_invoices), 1)
        self.assertIsNotNone(stripe_invoices[0].finalized_at)
        invoice_params = {
            # auto_advance is False because the invoice has been paid
            'amount_due': 0, 'amount_paid': 0, 'auto_advance': False, 'billing': 'charge_automatically',
            'charge': None, 'status': 'paid', 'total': 0}
        for key, value in invoice_params.items():
            self.assertEqual(stripe_invoices[0].get(key), value)
        # Check Line Items on Stripe Invoice
        stripe_line_items = [item for item in stripe_invoices[0].lines]
        self.assertEqual(len(stripe_line_items), 2)
        line_item_params = {
            'amount': 8000 * self.seat_count, 'description': 'Zulip Standard', 'discountable': False,
            'period': {
                'end': datetime_to_timestamp(self.next_year),
                'start': datetime_to_timestamp(self.now)},
            # There's no unit_amount on Line Items, probably because it doesn't show up on the
            # user-facing invoice. We could pull the Invoice Item instead and test unit_amount there,
            # but testing the amount and quantity seems sufficient.
            'plan': None, 'proration': False, 'quantity': self.seat_count}
        for key, value in line_item_params.items():
            self.assertEqual(stripe_line_items[0].get(key), value)
        line_item_params = {
            'amount': -8000 * self.seat_count, 'description': 'Payment (Card ending in 4242)',
            'discountable': False, 'plan': None, 'proration': False, 'quantity': 1}
        for key, value in line_item_params.items():
            self.assertEqual(stripe_line_items[1].get(key), value)

        # Check that we correctly populated Customer, CustomerPlan, and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer, automanage_licenses=True,
            price_per_license=8000, fixed_price=None, discount=None, billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.ANNUAL, invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month, tier=CustomerPlan.STANDARD,
            status=CustomerPlan.ACTIVE)
        LicenseLedger.objects.get(
            plan=plan, is_renewal=True, event_time=self.now, licenses=self.seat_count,
            licenses_at_next_renewal=self.seat_count)
        # Check RealmAuditLog
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', 'event_time').order_by('id'))
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.STRIPE_CUSTOMER_CREATED, timestamp_to_datetime(stripe_customer.created)),
            (RealmAuditLog.STRIPE_CARD_CHANGED, timestamp_to_datetime(stripe_customer.created)),
            (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
            # TODO: Check for REALM_PLAN_TYPE_CHANGED
            # (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, Kandra()),
        ])
        self.assertEqual(ujson.loads(RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED).values_list(
                'extra_data', flat=True).first())['automanage_licenses'], True)
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/billing/', response.url)

        # Check /billing has the correct information
        with patch('corporate.views.timezone_now', return_value=self.now):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(['Pay annually'], response)
        for substring in [
                'Zulip Standard', str(self.seat_count),
                'You are using', '%s of %s licenses' % (self.seat_count, self.seat_count),
                'Your plan will renew on', 'January 2, 2013', '$%s.00' % (80 * self.seat_count,),
                'Visa ending in 4242',
                'Update card']:
            self.assert_in_response(substring, response)

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_by_invoice(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        # Click "Make payment" in Stripe Checkout
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.upgrade(invoice=True)
        # Check that we correctly created a Customer in Stripe
        stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        # It can take a second for Stripe to attach the source to the customer, and in
        # particular it may not be attached at the time stripe_get_customer is called above,
        # causing test flakes.
        # So commenting the next line out, but leaving it here so future readers know what
        # is supposed to happen here
        # self.assertEqual(stripe_customer.default_source.type, 'ach_credit_transfer')

        # Check Charges in Stripe
        self.assertFalse(stripe.Charge.list(customer=stripe_customer.id))
        # Check Invoices in Stripe
        stripe_invoices = [invoice for invoice in stripe.Invoice.list(customer=stripe_customer.id)]
        self.assertEqual(len(stripe_invoices), 1)
        self.assertIsNotNone(stripe_invoices[0].due_date)
        self.assertIsNotNone(stripe_invoices[0].finalized_at)
        invoice_params = {
            'amount_due': 8000 * 123, 'amount_paid': 0, 'attempt_count': 0,
            'auto_advance': True, 'billing': 'send_invoice', 'statement_descriptor': 'Zulip Standard',
            'status': 'open', 'total': 8000 * 123}
        for key, value in invoice_params.items():
            self.assertEqual(stripe_invoices[0].get(key), value)
        # Check Line Items on Stripe Invoice
        stripe_line_items = [item for item in stripe_invoices[0].lines]
        self.assertEqual(len(stripe_line_items), 1)
        line_item_params = {
            'amount': 8000 * 123, 'description': 'Zulip Standard', 'discountable': False,
            'period': {
                'end': datetime_to_timestamp(self.next_year),
                'start': datetime_to_timestamp(self.now)},
            'plan': None, 'proration': False, 'quantity': 123}
        for key, value in line_item_params.items():
            self.assertEqual(stripe_line_items[0].get(key), value)

        # Check that we correctly populated Customer, CustomerPlan and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer, automanage_licenses=False, charge_automatically=False,
            price_per_license=8000, fixed_price=None, discount=None, billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.ANNUAL, invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_year, tier=CustomerPlan.STANDARD,
            status=CustomerPlan.ACTIVE)
        LicenseLedger.objects.get(
            plan=plan, is_renewal=True, event_time=self.now, licenses=123, licenses_at_next_renewal=123)
        # Check RealmAuditLog
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', 'event_time').order_by('id'))
        self.assertEqual(audit_log_entries, [
            (RealmAuditLog.STRIPE_CUSTOMER_CREATED, timestamp_to_datetime(stripe_customer.created)),
            (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
            # TODO: Check for REALM_PLAN_TYPE_CHANGED
            # (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, Kandra()),
        ])
        self.assertEqual(ujson.loads(RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED).values_list(
                'extra_data', flat=True).first())['automanage_licenses'], False)
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/billing/', response.url)

        # Check /billing has the correct information
        with patch('corporate.views.timezone_now', return_value=self.now):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(['Pay annually', 'Update card'], response)
        for substring in [
                'Zulip Standard', str(123),
                'You are using', '%s of %s licenses' % (self.seat_count, 123),
                'Your plan will renew on', 'January 2, 2013', '$9,840.00',  # 9840 = 80 * 123
                'Billed by invoice']:
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

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_by_card_with_outdated_seat_count(self, *mocks: Mock) -> None:
        self.login(self.example_email("hamlet"))
        new_seat_count = 23
        # Change the seat count while the user is going through the upgrade flow
        with patch('corporate.lib.stripe.get_seat_count', return_value=new_seat_count):
            self.upgrade()
        stripe_customer_id = Customer.objects.first().stripe_customer_id
        # Check that the Charge used the old quantity, not new_seat_count
        self.assertEqual(8000 * self.seat_count,
                         [charge for charge in stripe.Charge.list(customer=stripe_customer_id)][0].amount)
        # Check that the invoice has a credit for the old amount and a charge for the new one
        stripe_invoice = [invoice for invoice in stripe.Invoice.list(customer=stripe_customer_id)][0]
        self.assertEqual([8000 * new_seat_count, -8000 * self.seat_count],
                         [item.amount for item in stripe_invoice.lines])
        # Check LicenseLedger has the new amount
        self.assertEqual(LicenseLedger.objects.first().licenses, new_seat_count)
        self.assertEqual(LicenseLedger.objects.first().licenses_at_next_renewal, new_seat_count)

    @mock_stripe()
    def test_upgrade_where_first_card_fails(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        # From https://stripe.com/docs/testing#cards: Attaching this card to
        # a Customer object succeeds, but attempts to charge the customer fail.
        with patch("corporate.lib.stripe.billing_logger.error") as mock_billing_logger:
            self.upgrade(stripe_token=stripe_create_token('4000000000000341').id)
        mock_billing_logger.assert_called()
        # Check that we created a Customer object but no CustomerPlan
        stripe_customer_id = Customer.objects.get(realm=get_realm('zulip')).stripe_customer_id
        self.assertFalse(CustomerPlan.objects.exists())
        # Check that we created a Customer in stripe, a failed Charge, and no Invoices or Invoice Items
        self.assertTrue(stripe_get_customer(stripe_customer_id))
        stripe_charges = [charge for charge in stripe.Charge.list(customer=stripe_customer_id)]
        self.assertEqual(len(stripe_charges), 1)
        self.assertEqual(stripe_charges[0].failure_code, 'card_declined')
        # TODO: figure out what these actually are
        self.assertFalse(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertFalse(stripe.InvoiceItem.list(customer=stripe_customer_id))
        # Check that we correctly populated RealmAuditLog
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', flat=True).order_by('id'))
        self.assertEqual(audit_log_entries, [RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                                             RealmAuditLog.STRIPE_CARD_CHANGED])
        # Check that we did not update Realm
        realm = get_realm("zulip")
        self.assertNotEqual(realm.plan_type, Realm.STANDARD)
        # Check that we still get redirected to /upgrade
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

        # Try again, with a valid card, after they added a few users
        with patch('corporate.lib.stripe.get_seat_count', return_value=23):
            with patch('corporate.views.get_seat_count', return_value=23):
                self.upgrade()
        customer = Customer.objects.get(realm=get_realm('zulip'))
        # It's impossible to create two Customers, but check that we didn't
        # change stripe_customer_id
        self.assertEqual(customer.stripe_customer_id, stripe_customer_id)
        # Check that we successfully added a CustomerPlan, and have the right number of licenses
        plan = CustomerPlan.objects.get(customer=customer)
        ledger_entry = LicenseLedger.objects.get(plan=plan)
        self.assertEqual(ledger_entry.licenses, 23)
        self.assertEqual(ledger_entry.licenses_at_next_renewal, 23)
        # Check the Charges and Invoices in Stripe
        self.assertEqual(8000 * 23, [charge for charge in
                                     stripe.Charge.list(customer=stripe_customer_id)][0].amount)
        stripe_invoice = [invoice for invoice in stripe.Invoice.list(customer=stripe_customer_id)][0]
        self.assertEqual([8000 * 23, -8000 * 23],
                         [item.amount for item in stripe_invoice.lines])
        # Check that we correctly populated RealmAuditLog
        audit_log_entries = list(RealmAuditLog.objects.filter(acting_user=user)
                                 .values_list('event_type', flat=True).order_by('id'))
        # TODO: Test for REALM_PLAN_TYPE_CHANGED as the last entry
        self.assertEqual(audit_log_entries, [RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                                             RealmAuditLog.STRIPE_CARD_CHANGED,
                                             RealmAuditLog.STRIPE_CARD_CHANGED,
                                             RealmAuditLog.CUSTOMER_PLAN_CREATED])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.STANDARD)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/billing/', response.url)

    def test_upgrade_with_tampered_seat_count(self) -> None:
        self.login(self.example_email("hamlet"))
        response = self.upgrade(talk_to_stripe=False, salt='badsalt')
        self.assert_json_error_contains(response, "Something went wrong. Please contact")
        self.assertEqual(ujson.loads(response.content)['error_description'], 'tampered seat count')

    def test_upgrade_race_condition(self) -> None:
        self.login(self.example_email("hamlet"))
        self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        with patch("corporate.lib.stripe.billing_logger.warning") as mock_billing_logger:
            with self.assertRaises(BillingError) as context:
                self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        self.assertEqual('subscribing with existing subscription', context.exception.description)
        mock_billing_logger.assert_called()

    def test_check_upgrade_parameters(self) -> None:
        # Tests all the error paths except 'not enough licenses'
        def check_error(error_description: str, upgrade_params: Dict[str, Any],
                        del_args: List[str]=[]) -> None:
            response = self.upgrade(talk_to_stripe=False, del_args=del_args, **upgrade_params)
            self.assert_json_error_contains(response, "Something went wrong. Please contact")
            self.assertEqual(ujson.loads(response.content)['error_description'], error_description)

        self.login(self.example_email("hamlet"))
        check_error('unknown billing_modality', {'billing_modality': 'invalid'})
        check_error('unknown schedule', {'schedule': 'invalid'})
        check_error('unknown license_management', {'license_management': 'invalid'})
        check_error('autopay with no card', {}, del_args=['stripe_token'])

    def test_upgrade_license_counts(self) -> None:
        def check_error(invoice: bool, licenses: Optional[int], min_licenses_in_response: int,
                        upgrade_params: Dict[str, Any]={}) -> None:
            if licenses is None:
                del_args = ['licenses']
            else:
                del_args = []
                upgrade_params['licenses'] = licenses
            response = self.upgrade(invoice=invoice, talk_to_stripe=False,
                                    del_args=del_args, **upgrade_params)
            self.assert_json_error_contains(response, "at least {} users".format(min_licenses_in_response))
            self.assertEqual(ujson.loads(response.content)['error_description'], 'not enough licenses')

        def check_success(invoice: bool, licenses: Optional[int], upgrade_params: Dict[str, Any]={}) -> None:
            if licenses is None:
                del_args = ['licenses']
            else:
                del_args = []
                upgrade_params['licenses'] = licenses
            with patch('corporate.views.process_initial_upgrade'):
                response = self.upgrade(invoice=invoice, talk_to_stripe=False,
                                        del_args=del_args, **upgrade_params)
            self.assert_json_success(response)

        self.login(self.example_email("hamlet"))
        # Autopay with licenses < seat count
        check_error(False, self.seat_count - 1, self.seat_count, {'license_management': 'manual'})
        # Autopay with not setting licenses
        check_error(False, None, self.seat_count, {'license_management': 'manual'})
        # Invoice with licenses < MIN_INVOICED_LICENSES
        check_error(True, MIN_INVOICED_LICENSES - 1, MIN_INVOICED_LICENSES)
        # Invoice with licenses < seat count
        with patch("corporate.views.MIN_INVOICED_LICENSES", 3):
            check_error(True, 4, self.seat_count)
        # Invoice with not setting licenses
        check_error(True, None, MIN_INVOICED_LICENSES)

        # Autopay with automatic license_management
        check_success(False, None)
        # Autopay with automatic license_management, should just ignore the licenses entry
        check_success(False, self.seat_count)
        # Autopay
        check_success(False, self.seat_count, {'license_management': 'manual'})
        # Invoice
        check_success(True, self.seat_count + MIN_INVOICED_LICENSES)

    @patch("corporate.lib.stripe.billing_logger.error")
    def test_upgrade_with_uncaught_exception(self, mock_: Mock) -> None:
        self.login(self.example_email("hamlet"))
        with patch("corporate.views.process_initial_upgrade", side_effect=Exception):
            response = self.upgrade(talk_to_stripe=False)
        self.assert_json_error_contains(response, "Something went wrong. Please contact zulip-admin@example.com.")
        self.assertEqual(ujson.loads(response.content)['error_description'], 'uncaught exception during upgrade')

    def test_redirect_for_billing_home(self) -> None:
        user = self.example_user("iago")
        self.login(user.email)
        # No Customer yet; check that we are redirected to /upgrade
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/upgrade/', response.url)

        # Customer, but no CustomerPlan; check that we are still redirected to /upgrade
        Customer.objects.create(realm=user.realm, stripe_customer_id='cus_123')
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

        # Test guests
        # Adding a guest to a realm with a lot of members shouldn't change anything
        UserProfile.objects.create(realm=realm, email='user3@zulip.com', pointer=-1, is_guest=True)
        self.assertEqual(get_seat_count(realm), initial_count)
        # Test 1 member and 5 guests
        realm = Realm.objects.create(string_id='second', name='second')
        UserProfile.objects.create(realm=realm, email='member@second.com', pointer=-1)
        for i in range(5):
            UserProfile.objects.create(realm=realm, email='guest{}@second.com'.format(i),
                                       pointer=-1, is_guest=True)
        self.assertEqual(get_seat_count(realm), 1)
        # Test 1 member and 6 guests
        UserProfile.objects.create(realm=realm, email='guest5@second.com', pointer=-1, is_guest=True)
        self.assertEqual(get_seat_count(realm), 2)

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
        pass
        # If you signup with a card, we should show your card as the payment method
        # Already tested in test_initial_upgrade

        # If you pay by invoice, your payment method should be
        # "Billed by invoice", even if you have a card on file
        # user = self.example_user("hamlet")
        # do_create_stripe_customer(user, stripe_create_token().id)
        # self.login(user.email)
        # self.upgrade(invoice=True)
        # stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
        # self.assertEqual('Billed by invoice', payment_method_string(stripe_customer))

        # If you signup with a card and then downgrade, we still have your
        # card on file, and should show it
        # TODO

    @mock_stripe()
    def test_attach_discount_to_realm(self, *mocks: Mock) -> None:
        # Attach discount before Stripe customer exists
        user = self.example_user('hamlet')
        attach_discount_to_realm(user.realm, Decimal(85))
        self.login(user.email)
        # Check that the discount appears in page_params
        self.assert_in_success_response(['85'], self.client_get("/upgrade/"))
        # Check that the customer was charged the discounted amount
        self.upgrade()
        stripe_customer_id = Customer.objects.values_list('stripe_customer_id', flat=True).first()
        self.assertEqual(1200 * self.seat_count,
                         [charge for charge in stripe.Charge.list(customer=stripe_customer_id)][0].amount)
        stripe_invoice = [invoice for invoice in stripe.Invoice.list(customer=stripe_customer_id)][0]
        self.assertEqual([1200 * self.seat_count, -1200 * self.seat_count],
                         [item.amount for item in stripe_invoice.lines])
        # Check CustomerPlan reflects the discount
        plan = CustomerPlan.objects.get(price_per_license=1200, discount=Decimal(85))

        # Attach discount to existing Stripe customer
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=['status'])
        attach_discount_to_realm(user.realm, Decimal(25))
        process_initial_upgrade(user, self.seat_count, True, CustomerPlan.ANNUAL, stripe_create_token().id)
        self.assertEqual(6000 * self.seat_count,
                         [charge for charge in stripe.Charge.list(customer=stripe_customer_id)][0].amount)
        stripe_invoice = [invoice for invoice in stripe.Invoice.list(customer=stripe_customer_id)][0]
        self.assertEqual([6000 * self.seat_count, -6000 * self.seat_count],
                         [item.amount for item in stripe_invoice.lines])
        plan = CustomerPlan.objects.get(price_per_license=6000, discount=Decimal(25))

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
            # TODO: second argument should be something like "process_downgrade"
            ("/json/billing/downgrade", "process_downgrade", {}),
        ]  # type: List[Tuple[str, str, Dict[str, Any]]]

        for (url, mocked_function_name, data) in params:
            self._test_endpoint(url, mocked_function_name, data)

        # Make sure that we are testing all the JSON endpoints
        # Quite a hack, but probably fine for now
        string_with_all_endpoints = str(get_resolver('corporate.urls').reverse_dict)
        json_endpoints = set([word.strip("\"'()[],$") for word in string_with_all_endpoints.split()
                              if 'json' in word])
        # No need to test upgrade endpoint as it only requires user to be logged in.
        json_endpoints.remove("json/billing/upgrade")

        self.assertEqual(len(json_endpoints), len(params))

class BillingHelpersTest(ZulipTestCase):
    def test_next_month(self) -> None:
        anchor = datetime(2019, 12, 31, 1, 2, 3).replace(tzinfo=timezone_utc)
        period_boundaries = [
            anchor,
            datetime(2020, 1, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            # Test that this is the 28th even during leap years
            datetime(2020, 2, 28, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 3, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 4, 30, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 5, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 6, 30, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 7, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 8, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 9, 30, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 10, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 11, 30, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2020, 12, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2021, 1, 31, 1, 2, 3).replace(tzinfo=timezone_utc),
            datetime(2021, 2, 28, 1, 2, 3).replace(tzinfo=timezone_utc)]
        with self.assertRaises(AssertionError):
            add_months(anchor, -1)
        # Explictly test add_months for each value of MAX_DAY_FOR_MONTH and
        # for crossing a year boundary
        for i, boundary in enumerate(period_boundaries):
            self.assertEqual(add_months(anchor, i), boundary)
        # Test next_month for small values
        for last, next_ in zip(period_boundaries[:-1], period_boundaries[1:]):
            self.assertEqual(next_month(anchor, last), next_)
        # Test next_month for large values
        period_boundaries = [dt.replace(year=dt.year+100) for dt in period_boundaries]
        for last, next_ in zip(period_boundaries[:-1], period_boundaries[1:]):
            self.assertEqual(next_month(anchor, last), next_)

    def test_compute_plan_parameters(self) -> None:
        # TODO: test rounding down microseconds
        anchor = datetime(2019, 12, 31, 1, 2, 3).replace(tzinfo=timezone_utc)
        month_later = datetime(2020, 1, 31, 1, 2, 3).replace(tzinfo=timezone_utc)
        year_later = datetime(2020, 12, 31, 1, 2, 3).replace(tzinfo=timezone_utc)
        test_cases = [
            # TODO test with Decimal(85), not 85
            # TODO fix the mypy error by specifying the exact type
            # test all possibilities, since there aren't that many
            [(True,  CustomerPlan.ANNUAL,  None), (anchor, month_later, year_later, 8000)],  # lint:ignore
            [(True,  CustomerPlan.ANNUAL,  85),   (anchor, month_later, year_later, 1200)],  # lint:ignore
            [(True,  CustomerPlan.MONTHLY, None), (anchor, month_later, month_later, 800)],  # lint:ignore
            [(True,  CustomerPlan.MONTHLY, 85),   (anchor, month_later, month_later, 120)],  # lint:ignore
            [(False, CustomerPlan.ANNUAL,  None), (anchor, year_later,  year_later, 8000)],  # lint:ignore
            [(False, CustomerPlan.ANNUAL,  85),   (anchor, year_later,  year_later, 1200)],  # lint:ignore
            [(False, CustomerPlan.MONTHLY, None), (anchor, month_later, month_later, 800)],  # lint:ignore
            [(False, CustomerPlan.MONTHLY, 85),   (anchor, month_later, month_later, 120)],  # lint:ignore
            # test exact math of Decimals; 800 * (1 - 87.25) = 101.9999999..
            [(False, CustomerPlan.MONTHLY, 87.25), (anchor, month_later, month_later, 102)],
            # test dropping of fractional cents; without the int it's 102.8
            [(False, CustomerPlan.MONTHLY, 87.15), (anchor, month_later, month_later, 102)]]
        with patch('corporate.lib.stripe.timezone_now', return_value=anchor):
            for input_, output in test_cases:
                output_ = compute_plan_parameters(*input_)  # type: ignore # TODO
                self.assertEqual(output_, output)

    def test_update_or_create_stripe_customer_logic(self) -> None:
        user = self.example_user('hamlet')
        # No existing Customer object
        with patch('corporate.lib.stripe.do_create_stripe_customer', return_value='returned') as mocked1:
            returned = update_or_create_stripe_customer(user, stripe_token='token')
        mocked1.assert_called()
        self.assertEqual(returned, 'returned')
        # Customer exists, replace payment source
        Customer.objects.create(realm=get_realm('zulip'), stripe_customer_id='cus_12345')
        with patch('corporate.lib.stripe.do_replace_payment_source') as mocked2:
            customer = update_or_create_stripe_customer(self.example_user('hamlet'), 'token')
        mocked2.assert_called()
        self.assertTrue(isinstance(customer, Customer))
        # Customer exists, do nothing
        with patch('corporate.lib.stripe.do_replace_payment_source') as mocked3:
            customer = update_or_create_stripe_customer(self.example_user('hamlet'), None)
        mocked3.assert_not_called()
        self.assertTrue(isinstance(customer, Customer))

class LicenseLedgerTest(StripeTestCase):
    def test_add_plan_renewal_if_needed(self) -> None:
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        self.assertEqual(LicenseLedger.objects.count(), 1)
        plan = CustomerPlan.objects.get()
        # Plan hasn't renewed yet
        add_plan_renewal_to_license_ledger_if_needed(plan, self.next_year - timedelta(days=1))
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Plan needs to renew
        # TODO: do_deactivate_user for a user, so that licenses_at_next_renewal != licenses
        ledger_entry = add_plan_renewal_to_license_ledger_if_needed(plan, self.next_year)
        self.assertEqual(LicenseLedger.objects.count(), 2)
        ledger_params = {
            'plan': plan, 'is_renewal': True, 'event_time': self.next_year,
            'licenses': self.seat_count, 'licenses_at_next_renewal': self.seat_count}
        for key, value in ledger_params.items():
            self.assertEqual(getattr(ledger_entry, key), value)
        # Plan needs to renew, but we already added the plan_renewal ledger entry
        add_plan_renewal_to_license_ledger_if_needed(plan, self.next_year + timedelta(days=1))
        self.assertEqual(LicenseLedger.objects.count(), 2)

    def test_update_license_ledger_if_needed(self) -> None:
        realm = get_realm('zulip')
        # Test no Customer
        update_license_ledger_if_needed(realm, self.now)
        self.assertFalse(LicenseLedger.objects.exists())
        # Test plan not automanaged
        self.local_upgrade(self.seat_count + 1, False, CustomerPlan.ANNUAL, 'token')
        self.assertEqual(LicenseLedger.objects.count(), 1)
        update_license_ledger_if_needed(realm, self.now)
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Test no active plan
        plan = CustomerPlan.objects.get()
        plan.automanage_licenses = True
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=['automanage_licenses', 'status'])
        update_license_ledger_if_needed(realm, self.now)
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Test update needed
        plan.status = CustomerPlan.ACTIVE
        plan.save(update_fields=['status'])
        update_license_ledger_if_needed(realm, self.now)
        self.assertEqual(LicenseLedger.objects.count(), 2)

    def test_update_license_ledger_for_automanaged_plan(self) -> None:
        realm = get_realm('zulip')
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        plan = CustomerPlan.objects.first()
        # Simple increase
        with patch('corporate.lib.stripe.get_seat_count', return_value=23):
            update_license_ledger_for_automanaged_plan(realm, plan, self.now)
        # Decrease
        with patch('corporate.lib.stripe.get_seat_count', return_value=20):
            update_license_ledger_for_automanaged_plan(realm, plan, self.now)
        # Increase, but not past high watermark
        with patch('corporate.lib.stripe.get_seat_count', return_value=21):
            update_license_ledger_for_automanaged_plan(realm, plan, self.now)
        # Increase, but after renewal date, and below last year's high watermark
        with patch('corporate.lib.stripe.get_seat_count', return_value=22):
            update_license_ledger_for_automanaged_plan(realm, plan, self.next_year + timedelta(seconds=1))

        ledger_entries = list(LicenseLedger.objects.values_list(
            'is_renewal', 'event_time', 'licenses', 'licenses_at_next_renewal').order_by('id'))
        self.assertEqual(ledger_entries,
                         [(True, self.now, self.seat_count, self.seat_count),
                          (False, self.now, 23, 23),
                          (False, self.now, 23, 20),
                          (False, self.now, 23, 21),
                          (True, self.next_year, 21, 21),
                          (False, self.next_year + timedelta(seconds=1), 22, 22)])

    def test_user_changes(self) -> None:
        self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        user = do_create_user('email', 'password', get_realm('zulip'), 'name', 'name')
        do_deactivate_user(user)
        do_reactivate_user(user)
        # Not a proper use of do_activate_user, but fine for this test
        do_activate_user(user)
        ledger_entries = list(LicenseLedger.objects.values_list(
            'is_renewal', 'licenses', 'licenses_at_next_renewal').order_by('id'))
        self.assertEqual(ledger_entries,
                         [(True, self.seat_count, self.seat_count),
                          (False, self.seat_count + 1, self.seat_count + 1),
                          (False, self.seat_count + 1, self.seat_count),
                          (False, self.seat_count + 1, self.seat_count + 1),
                          (False, self.seat_count + 1, self.seat_count + 1)])

class InvoiceTest(StripeTestCase):
    def test_invoicing_status_is_started(self) -> None:
        self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        plan = CustomerPlan.objects.first()
        plan.invoicing_status = CustomerPlan.STARTED
        plan.save(update_fields=['invoicing_status'])
        with self.assertRaises(NotImplementedError):
            invoice_plan(CustomerPlan.objects.first(), self.now)

    @mock_stripe()
    def test_invoice_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login(user.email)
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.upgrade()
        # Increase
        with patch('corporate.lib.stripe.get_seat_count', return_value=self.seat_count + 3):
            update_license_ledger_if_needed(get_realm('zulip'), self.now + timedelta(days=100))
        # Decrease
        with patch('corporate.lib.stripe.get_seat_count', return_value=self.seat_count):
            update_license_ledger_if_needed(get_realm('zulip'), self.now + timedelta(days=200))
        # Increase, but not past high watermark
        with patch('corporate.lib.stripe.get_seat_count', return_value=self.seat_count + 1):
            update_license_ledger_if_needed(get_realm('zulip'), self.now + timedelta(days=300))
        # Increase, but after renewal date, and below last year's high watermark
        with patch('corporate.lib.stripe.get_seat_count', return_value=self.seat_count + 2):
            update_license_ledger_if_needed(get_realm('zulip'), self.now + timedelta(days=400))
        # Increase, but after event_time
        with patch('corporate.lib.stripe.get_seat_count', return_value=self.seat_count + 3):
            update_license_ledger_if_needed(get_realm('zulip'), self.now + timedelta(days=500))
        plan = CustomerPlan.objects.first()
        invoice_plan(plan, self.now + timedelta(days=400))

        stripe_invoices = [invoice for invoice in stripe.Invoice.list(
            customer=plan.customer.stripe_customer_id)]
        self.assertEqual(len(stripe_invoices), 2)
        self.assertIsNotNone(stripe_invoices[0].finalized_at)
        stripe_line_items = [item for item in stripe_invoices[0].lines]
        self.assertEqual(len(stripe_line_items), 3)
        line_item_params = {
            'amount': int(8000 * (1 - ((400-366) / 365)) + .5),
            'description': 'Additional license (Feb 5, 2013 - Jan 2, 2014)',
            'discountable': False,
            'period': {
                'start': datetime_to_timestamp(self.now + timedelta(days=400)),
                'end': datetime_to_timestamp(self.now + timedelta(days=2*365 + 1))},
            'quantity': 1}
        for key, value in line_item_params.items():
            self.assertEqual(stripe_line_items[0].get(key), value)
        line_item_params = {
            'amount': 8000 * (self.seat_count + 1),
            'description': 'Zulip Standard - renewal',
            'discountable': False,
            'period': {
                'start': datetime_to_timestamp(self.now + timedelta(days=366)),
                'end': datetime_to_timestamp(self.now + timedelta(days=2*365 + 1))},
            'quantity': (self.seat_count + 1)}
        for key, value in line_item_params.items():
            self.assertEqual(stripe_line_items[1].get(key), value)
        line_item_params = {
            'amount': 3 * int(8000 * (366-100) / 366 + .5),
            'description': 'Additional license (Apr 11, 2012 - Jan 2, 2013)',
            'discountable': False,
            'period': {
                'start': datetime_to_timestamp(self.now + timedelta(days=100)),
                'end': datetime_to_timestamp(self.now + timedelta(days=366))},
            'quantity': 3}
        for key, value in line_item_params.items():
            self.assertEqual(stripe_line_items[2].get(key), value)

    @mock_stripe()
    def test_fixed_price_plans(self, *mocks: Mock) -> None:
        # Also tests charge_automatically=False
        user = self.example_user("hamlet")
        self.login(user.email)
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.upgrade(invoice=True)
        plan = CustomerPlan.objects.first()
        plan.fixed_price = 100
        plan.price_per_license = 0
        plan.save(update_fields=['fixed_price', 'price_per_license'])
        invoice_plan(plan, self.next_year)
        stripe_invoices = [invoice for invoice in stripe.Invoice.list(
            customer=plan.customer.stripe_customer_id)]
        self.assertEqual(len(stripe_invoices), 2)
        self.assertEqual(stripe_invoices[0].billing, 'send_invoice')
        stripe_line_items = [item for item in stripe_invoices[0].lines]
        self.assertEqual(len(stripe_line_items), 1)
        line_item_params = {
            'amount': 100,
            'description': 'Zulip Standard - renewal',
            'discountable': False,
            'period': {
                'start': datetime_to_timestamp(self.next_year),
                'end': datetime_to_timestamp(self.next_year + timedelta(days=365))},
            'quantity': 1}
        for key, value in line_item_params.items():
            self.assertEqual(stripe_line_items[0].get(key), value)

    def test_no_invoice_needed(self) -> None:
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        plan = CustomerPlan.objects.first()
        self.assertEqual(plan.next_invoice_date, self.next_month)
        # Test this doesn't make any calls to stripe.Invoice or stripe.InvoiceItem
        invoice_plan(plan, self.next_month)
        plan = CustomerPlan.objects.first()
        # Test that we still update next_invoice_date
        self.assertEqual(plan.next_invoice_date, self.next_month + timedelta(days=29))

    def test_invoice_plans_as_needed(self) -> None:
        with patch('corporate.lib.stripe.timezone_now', return_value=self.now):
            self.local_upgrade(self.seat_count, True, CustomerPlan.ANNUAL, 'token')
        plan = CustomerPlan.objects.first()
        self.assertEqual(plan.next_invoice_date, self.next_month)
        # Test nothing needed to be done
        with patch('corporate.lib.stripe.invoice_plan') as mocked:
            invoice_plans_as_needed(self.next_month - timedelta(days=1))
        mocked.assert_not_called()
        # Test something needing to be done
        invoice_plans_as_needed(self.next_month)
        plan = CustomerPlan.objects.first()
        self.assertEqual(plan.next_invoice_date, self.next_month + timedelta(days=29))

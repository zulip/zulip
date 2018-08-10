import datetime
from functools import wraps
import logging
import os
from typing import Any, Callable, Optional, TypeVar, Tuple
import ujson

from django.conf import settings
from django.db import transaction
from django.utils.translation import ugettext as _
from django.core.signing import Signer
import stripe

from zerver.lib.exceptions import JsonableError
from zerver.lib.logging_util import log_to_file
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.utils import generate_random_token
from zerver.models import Realm, UserProfile, RealmAuditLog
from zilencer.models import Customer, Plan
from zproject.settings import get_secret

STRIPE_PUBLISHABLE_KEY = get_secret('stripe_publishable_key')
stripe.api_key = get_secret('stripe_secret_key')

BILLING_LOG_PATH = os.path.join('/var/log/zulip'
                                if not settings.DEVELOPMENT
                                else settings.DEVELOPMENT_LOG_DIRECTORY,
                                'billing.log')
billing_logger = logging.getLogger('zilencer.stripe')
log_to_file(billing_logger, BILLING_LOG_PATH)
log_to_file(logging.getLogger('stripe'), BILLING_LOG_PATH)

# To generate the fixture data in stripe_fixtures.json:
# * Set PRINT_STRIPE_FIXTURE_DATA to True
# * ./manage.py setup_stripe
# * Customer.objects.all().delete()
# * Log in as a user, and go to http://localhost:9991/upgrade/
# * Click Add card. Enter the following billing details:
#       Name: Ada Starr, Street: Under the sea, City: Pacific,
#       Zip: 33333, Country: United States
#       Card number: 4242424242424242, Expiry: 03/33, CVV: 333
# * Click Make payment.
# * Copy out the 4 blobs of json from the dev console into stripe_fixtures.json.
#   The contents of that file are '{\n' + concatenate the 4 json blobs + '\n}'.
#   Then you can run e.g. `M-x mark-whole-buffer` and `M-x indent-region` in emacs
#   to prettify the file (and make 4 space indents).
# * Copy out the customer id, plan id, and quantity values into
#   zilencer.tests.test_stripe.StripeTest.setUp.
# * Set PRINT_STRIPE_FIXTURE_DATA to False
PRINT_STRIPE_FIXTURE_DATA = False

CallableT = TypeVar('CallableT', bound=Callable[..., Any])

def get_seat_count(realm: Realm) -> int:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()

def sign_string(string: str) -> Tuple[str, str]:
    salt = generate_random_token(64)
    signer = Signer(salt=salt)
    return signer.sign(string), salt

def unsign_string(signed_string: str, salt: str) -> str:
    signer = Signer(salt=salt)
    return signer.unsign(signed_string)

class BillingError(Exception):
    # error messages
    CONTACT_SUPPORT = _("Something went wrong. Please contact %s)" % (settings.ZULIP_ADMINISTRATOR,))
    TRY_RELOADING = _("Something went wrong. Please reload the page.")

    # description is used only for tests
    def __init__(self, description: str, message: str) -> None:
        self.description = description
        self.message = message

def catch_stripe_errors(func: CallableT) -> CallableT:
    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if settings.DEVELOPMENT and not settings.TEST_SUITE:  # nocoverage
            if STRIPE_PUBLISHABLE_KEY is None:
                raise BillingError('missing stripe config', "Missing Stripe config. "
                                   "See https://zulip.readthedocs.io/en/latest/subsystems/billing.html.")
            if not Plan.objects.exists():
                raise BillingError('missing plans',
                                   "Plan objects not created. Please run ./manage.py setup_stripe")
        try:
            return func(*args, **kwargs)
        except stripe.error.StripeError as e:
            billing_logger.error("Stripe error: %d %s", e.http_status, e.__class__.__name__)
            if isinstance(e, stripe.error.CardError):
                raise BillingError('card error', e.json_body.get('error', {}).get('message'))
            else:
                raise BillingError('other stripe error', BillingError.CONTACT_SUPPORT)
    return wrapped  # type: ignore # https://github.com/python/mypy/issues/1927

@catch_stripe_errors
def stripe_get_customer(stripe_customer_id: str) -> stripe.Customer:
    stripe_customer = stripe.Customer.retrieve(stripe_customer_id, expand=["default_source"])
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"customer_with_subscription": ', str(stripe_customer), ',']))  # nocoverage
    return stripe_customer

@catch_stripe_errors
def stripe_get_upcoming_invoice(stripe_customer_id: str) -> stripe.Invoice:
    stripe_invoice = stripe.Invoice.upcoming(customer=stripe_customer_id)
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"upcoming_invoice": ', str(stripe_invoice), ',']))  # nocoverage
    return stripe_invoice

# Return type should be Optional[stripe.Subscription], which throws a mypy error.
# Will fix once we add type stubs for the Stripe API.
def extract_current_subscription(stripe_customer: stripe.Customer) -> Any:
    if not stripe_customer.subscriptions:
        return None
    for stripe_subscription in stripe_customer.subscriptions:
        if stripe_subscription.status != "canceled":
            return stripe_subscription
    return None

@catch_stripe_errors
def do_create_customer_with_payment_source(user: UserProfile, stripe_token: str) -> stripe.Customer:
    realm = user.realm
    stripe_customer = stripe.Customer.create(
        description="%s (%s)" % (realm.string_id, realm.name),
        email=user.email,
        metadata={'realm_id': realm.id, 'realm_str': realm.string_id},
        source=stripe_token)
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"create_customer": ', str(stripe_customer), ',']))  # nocoverage
    event_time = timestamp_to_datetime(stripe_customer.created)
    RealmAuditLog.objects.create(
        realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CUSTOMER_CREATED,
        event_time=event_time)
    RealmAuditLog.objects.create(
        realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CARD_ADDED,
        event_time=event_time)
    Customer.objects.create(
        realm=realm,
        stripe_customer_id=stripe_customer.id,
        billing_user=user)
    return stripe_customer

@catch_stripe_errors
def do_subscribe_customer_to_plan(stripe_customer: stripe.Customer, stripe_plan_id: str,
                                  seat_count: int, tax_percent: float) -> None:
    if extract_current_subscription(stripe_customer) is not None:
        # Most likely due to a race condition where two people in the org
        # try to upgrade their plan at the same time
        billing_logger.error("Stripe customer %s trying to subscribe to %s, "
                             "but has an active subscription" % (stripe_customer.id, stripe_plan_id))
        raise BillingError('subscribing with existing subscription', BillingError.TRY_RELOADING)
    stripe_subscription = stripe.Subscription.create(
        customer=stripe_customer.id,
        billing='charge_automatically',
        items=[{
            'plan': stripe_plan_id,
            'quantity': seat_count,
        }],
        prorate=True,
        tax_percent=tax_percent)
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"create_subscription": ', str(stripe_subscription), ',']))  # nocoverage
    customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
    with transaction.atomic():
        customer.realm.has_seat_based_plan = True
        customer.realm.save(update_fields=['has_seat_based_plan'])
        RealmAuditLog.objects.create(
            realm=customer.realm,
            acting_user=customer.billing_user,
            event_type=RealmAuditLog.REALM_PLAN_STARTED,
            event_time=timestamp_to_datetime(stripe_subscription.created),
            extra_data=ujson.dumps({'plan': stripe_plan_id, 'quantity': seat_count}))

        current_seat_count = get_seat_count(customer.realm)
        if seat_count != current_seat_count:
            RealmAuditLog.objects.create(
                realm=customer.realm,
                event_type=RealmAuditLog.REALM_PLAN_QUANTITY_RESET,
                event_time=timestamp_to_datetime(stripe_subscription.created),
                requires_billing_update=True,
                extra_data=ujson.dumps({'quantity': current_seat_count}))

def process_initial_upgrade(user: UserProfile, plan: Plan, seat_count: int, stripe_token: str) -> None:
    stripe_customer = do_create_customer_with_payment_source(user, stripe_token)
    do_subscribe_customer_to_plan(
        stripe_customer=stripe_customer,
        stripe_plan_id=plan.stripe_plan_id,
        seat_count=seat_count,
        # TODO: billing address details are passed to us in the request;
        # use that to calculate taxes.
        tax_percent=0)

import datetime
from decimal import Decimal
from functools import wraps
import logging
import os
from typing import Any, Callable, Dict, Optional, TypeVar, Tuple
import ujson

from django.conf import settings
from django.db import transaction
from django.utils.translation import ugettext as _
from django.utils.timezone import now as timezone_now
from django.core.signing import Signer
import stripe

from zerver.lib.exceptions import JsonableError
from zerver.lib.logging_util import log_to_file
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.utils import generate_random_token
from zerver.lib.actions import do_change_plan_type
from zerver.models import Realm, UserProfile, RealmAuditLog
from corporate.models import Customer, CustomerPlan, Plan, Coupon
from zproject.settings import get_secret

STRIPE_PUBLISHABLE_KEY = get_secret('stripe_publishable_key')
stripe.api_key = get_secret('stripe_secret_key')

BILLING_LOG_PATH = os.path.join('/var/log/zulip'
                                if not settings.DEVELOPMENT
                                else settings.DEVELOPMENT_LOG_DIRECTORY,
                                'billing.log')
billing_logger = logging.getLogger('corporate.stripe')
log_to_file(billing_logger, BILLING_LOG_PATH)
log_to_file(logging.getLogger('stripe'), BILLING_LOG_PATH)

CallableT = TypeVar('CallableT', bound=Callable[..., Any])

MIN_INVOICED_LICENSES = 30
DEFAULT_INVOICE_DAYS_UNTIL_DUE = 30

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
    CONTACT_SUPPORT = _("Something went wrong. Please contact %s." % (settings.ZULIP_ADMINISTRATOR,))
    TRY_RELOADING = _("Something went wrong. Please reload the page.")

    # description is used only for tests
    def __init__(self, description: str, message: str=CONTACT_SUPPORT) -> None:
        self.description = description
        self.message = message

class StripeCardError(BillingError):
    pass

class StripeConnectionError(BillingError):
    pass

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
        # See https://stripe.com/docs/api/python#error_handling, though
        # https://stripe.com/docs/api/ruby#error_handling suggests there are additional fields, and
        # https://stripe.com/docs/error-codes gives a more detailed set of error codes
        except stripe.error.StripeError as e:
            err = e.json_body.get('error', {})
            billing_logger.error("Stripe error: %s %s %s %s" % (
                e.http_status, err.get('type'), err.get('code'), err.get('param')))
            if isinstance(e, stripe.error.CardError):
                # TODO: Look into i18n for this
                raise StripeCardError('card error', err.get('message'))
            if isinstance(e, stripe.error.RateLimitError) or \
               isinstance(e, stripe.error.APIConnectionError):  # nocoverage TODO
                raise StripeConnectionError(
                    'stripe connection error',
                    _("Something went wrong. Please wait a few seconds and try again."))
            raise BillingError('other stripe error', BillingError.CONTACT_SUPPORT)
    return wrapped  # type: ignore # https://github.com/python/mypy/issues/1927

@catch_stripe_errors
def stripe_get_customer(stripe_customer_id: str) -> stripe.Customer:
    return stripe.Customer.retrieve(stripe_customer_id, expand=["default_source"])

@catch_stripe_errors
def stripe_get_upcoming_invoice(stripe_customer_id: str) -> stripe.Invoice:
    return stripe.Invoice.upcoming(customer=stripe_customer_id)

# This allows us to access /billing in tests without having to mock the
# whole invoice object
def upcoming_invoice_total(stripe_customer_id: str) -> int:
    return stripe_get_upcoming_invoice(stripe_customer_id).total

# Return type should be Optional[stripe.Subscription], which throws a mypy error.
# Will fix once we add type stubs for the Stripe API.
def extract_current_subscription(stripe_customer: stripe.Customer) -> Any:
    if not stripe_customer.subscriptions:
        return None
    for stripe_subscription in stripe_customer.subscriptions:
        if stripe_subscription.status != "canceled":
            return stripe_subscription

def estimate_customer_arr(stripe_customer: stripe.Customer) -> int:  # nocoverage
    stripe_subscription = extract_current_subscription(stripe_customer)
    if stripe_subscription is None:
        return 0
    # This is an overestimate for those paying by invoice
    estimated_arr = stripe_subscription.plan.amount * stripe_subscription.quantity / 100.
    if stripe_subscription.plan.interval == 'month':
        estimated_arr *= 12
    discount = Customer.objects.get(stripe_customer_id=stripe_customer.id).default_discount
    if discount is not None:
        estimated_arr *= 1 - discount/100.
    return int(estimated_arr)

@catch_stripe_errors
def do_create_customer(user: UserProfile, stripe_token: Optional[str]=None) -> stripe.Customer:
    realm = user.realm
    # We could do a better job of handling race conditions here, but if two
    # people from a realm try to upgrade at exactly the same time, the main
    # bad thing that will happen is that we will create an extra stripe
    # customer that we can delete or ignore.
    stripe_customer = stripe.Customer.create(
        description="%s (%s)" % (realm.string_id, realm.name),
        email=user.email,
        metadata={'realm_id': realm.id, 'realm_str': realm.string_id},
        source=stripe_token)
    event_time = timestamp_to_datetime(stripe_customer.created)
    with transaction.atomic():
        RealmAuditLog.objects.create(
            realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CUSTOMER_CREATED,
            event_time=event_time)
        if stripe_token is not None:
            RealmAuditLog.objects.create(
                realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CARD_CHANGED,
                event_time=event_time)
        Customer.objects.create(realm=realm, stripe_customer_id=stripe_customer.id)
        user.is_billing_admin = True
        user.save(update_fields=["is_billing_admin"])
    return stripe_customer

@catch_stripe_errors
def do_replace_payment_source(user: UserProfile, stripe_token: str) -> stripe.Customer:
    stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
    stripe_customer.source = stripe_token
    # Deletes existing card: https://stripe.com/docs/api#update_customer-source
    # This can also have other side effects, e.g. it will try to pay certain past-due
    # invoices: https://stripe.com/docs/api#update_customer
    updated_stripe_customer = stripe.Customer.save(stripe_customer)
    RealmAuditLog.objects.create(
        realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CARD_CHANGED,
        event_time=timezone_now())
    return updated_stripe_customer

@catch_stripe_errors
def do_subscribe_customer_to_plan(user: UserProfile, stripe_customer: stripe.Customer, stripe_plan_id: str,
                                  seat_count: int, tax_percent: float, charge_automatically: bool) -> None:
    if extract_current_subscription(stripe_customer) is not None:  # nocoverage
        # Unlikely race condition from two people upgrading (clicking "Make payment")
        # at exactly the same time. Doesn't fully resolve the race condition, but having
        # a check here reduces the likelihood.
        billing_logger.error("Stripe customer %s trying to subscribe to %s, "
                             "but has an active subscription" % (stripe_customer.id, stripe_plan_id))
        raise BillingError('subscribing with existing subscription', BillingError.TRY_RELOADING)
    customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
    if charge_automatically:
        billing_method = 'charge_automatically'
        days_until_due = None
    else:
        billing_method = 'send_invoice'
        days_until_due = DEFAULT_INVOICE_DAYS_UNTIL_DUE
    # Note that there is a race condition here, where if two users upgrade at exactly the
    # same time, they will have two subscriptions, and get charged twice. We could try to
    # reduce the chance of it with a well-designed idempotency_key, but it's not easy since
    # we also need to be careful not to block the customer from retrying if their
    # subscription attempt fails (e.g. due to insufficient funds).

    # Success here implies the stripe_customer was charged: https://stripe.com/docs/billing/lifecycle#active
    # Otherwise we should expect it to throw a stripe.error.
    stripe_subscription = stripe.Subscription.create(
        customer=stripe_customer.id,
        billing=billing_method,
        days_until_due=days_until_due,
        items=[{
            'plan': stripe_plan_id,
            'quantity': seat_count,
        }],
        prorate=True,
        tax_percent=tax_percent)
    with transaction.atomic():
        customer.has_billing_relationship = True
        customer.save(update_fields=['has_billing_relationship'])
        customer.realm.has_seat_based_plan = True
        customer.realm.save(update_fields=['has_seat_based_plan'])
        RealmAuditLog.objects.create(
            realm=customer.realm,
            acting_user=user,
            event_type=RealmAuditLog.STRIPE_PLAN_CHANGED,
            event_time=timestamp_to_datetime(stripe_subscription.created),
            extra_data=ujson.dumps({'plan': stripe_plan_id, 'quantity': seat_count,
                                    'billing_method': billing_method}))

        current_seat_count = get_seat_count(customer.realm)
        if seat_count != current_seat_count:
            RealmAuditLog.objects.create(
                realm=customer.realm,
                event_type=RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET,
                event_time=timestamp_to_datetime(stripe_subscription.created),
                requires_billing_update=True,
                extra_data=ujson.dumps({'quantity': current_seat_count}))

def process_initial_upgrade(user: UserProfile, seat_count: int, schedule: int,
                            stripe_token: Optional[str]) -> None:
    if schedule == CustomerPlan.ANNUAL:
        plan = Plan.objects.get(nickname=Plan.CLOUD_ANNUAL)
    else:  # schedule == CustomerPlan.MONTHLY:
        plan = Plan.objects.get(nickname=Plan.CLOUD_MONTHLY)
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        stripe_customer = do_create_customer(user, stripe_token=stripe_token)
    # elif instead of if since we want to avoid doing two round trips to
    # stripe if we can
    elif stripe_token is not None:
        stripe_customer = do_replace_payment_source(user, stripe_token)
    else:
        stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    do_subscribe_customer_to_plan(
        user=user,
        stripe_customer=stripe_customer,
        stripe_plan_id=plan.stripe_plan_id,
        seat_count=seat_count,
        # TODO: billing address details are passed to us in the request;
        # use that to calculate taxes.
        tax_percent=0,
        charge_automatically=(stripe_token is not None))
    do_change_plan_type(user.realm, Realm.STANDARD)

def attach_discount_to_realm(user: UserProfile, discount: Decimal) -> None:
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        do_create_customer(user)
    customer = Customer.objects.filter(realm=user.realm).first()
    customer.default_discount = discount
    customer.save()

def process_downgrade(user: UserProfile) -> None:  # nocoverage
    pass

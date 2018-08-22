import datetime
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
from zilencer.models import Customer, Plan, Coupon, BillingProcessor
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

## Note: this is no longer accurate, as of when we added coupons
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
    CONTACT_SUPPORT = _("Something went wrong. Please contact %s." % (settings.ZULIP_ADMINISTRATOR,))
    TRY_RELOADING = _("Something went wrong. Please reload the page.")

    # description is used only for tests
    def __init__(self, description: str, message: str) -> None:
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
def do_create_customer(user: UserProfile, stripe_token: Optional[str]=None,
                       coupon: Optional[Coupon]=None) -> stripe.Customer:
    realm = user.realm
    stripe_coupon_id = None
    if coupon is not None:
        stripe_coupon_id = coupon.stripe_coupon_id
    # We could do a better job of handling race conditions here, but if two
    # people from a realm try to upgrade at exactly the same time, the main
    # bad thing that will happen is that we will create an extra stripe
    # customer that we can delete or ignore.
    stripe_customer = stripe.Customer.create(
        description="%s (%s)" % (realm.string_id, realm.name),
        email=user.email,
        metadata={'realm_id': realm.id, 'realm_str': realm.string_id},
        source=stripe_token,
        coupon=stripe_coupon_id)
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"create_customer": ', str(stripe_customer), ',']))  # nocoverage
    event_time = timestamp_to_datetime(stripe_customer.created)
    with transaction.atomic():
        RealmAuditLog.objects.create(
            realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CUSTOMER_CREATED,
            event_time=event_time)
        if stripe_token is not None:
            RealmAuditLog.objects.create(
                realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CARD_ADDED,
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
    updated_stripe_customer = stripe_customer.save()
    RealmAuditLog.objects.create(
        realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_CARD_ADDED,
        event_time=timezone_now())
    return updated_stripe_customer

@catch_stripe_errors
def do_replace_coupon(user: UserProfile, coupon: Coupon) -> stripe.Customer:
    stripe_customer = stripe_get_customer(Customer.objects.get(realm=user.realm).stripe_customer_id)
    stripe_customer.coupon = coupon.stripe_coupon_id
    return stripe_customer.save()

@catch_stripe_errors
def do_subscribe_customer_to_plan(user: UserProfile, stripe_customer: stripe.Customer, stripe_plan_id: str,
                                  seat_count: int, tax_percent: float) -> None:
    if extract_current_subscription(stripe_customer) is not None:
        # Most likely due to two people in the org going to the billing page,
        # and then both upgrading their plan. We don't send clients
        # real-time event updates for the billing pages, so this is more
        # likely than it would be in other parts of the app.
        billing_logger.error("Stripe customer %s trying to subscribe to %s, "
                             "but has an active subscription" % (stripe_customer.id, stripe_plan_id))
        raise BillingError('subscribing with existing subscription', BillingError.TRY_RELOADING)
    customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
    # Note that there is a race condition here, where if two users upgrade at exactly the
    # same time, they will have two subscriptions, and get charged twice. We could try to
    # reduce the chance of it with a well-designed idempotency_key, but it's not easy since
    # we also need to be careful not to block the customer from retrying if their
    # subscription attempt fails (e.g. due to insufficient funds).

    # Success here implies the stripe_customer was charged: https://stripe.com/docs/billing/lifecycle#active
    # Otherwise we should expect it to throw a stripe.error.
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
            extra_data=ujson.dumps({'plan': stripe_plan_id, 'quantity': seat_count}))

        current_seat_count = get_seat_count(customer.realm)
        if seat_count != current_seat_count:
            RealmAuditLog.objects.create(
                realm=customer.realm,
                event_type=RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET,
                event_time=timestamp_to_datetime(stripe_subscription.created),
                requires_billing_update=True,
                extra_data=ujson.dumps({'quantity': current_seat_count}))

def process_initial_upgrade(user: UserProfile, plan: Plan, seat_count: int, stripe_token: str) -> None:
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        stripe_customer = do_create_customer(user, stripe_token=stripe_token)
    else:
        stripe_customer = do_replace_payment_source(user, stripe_token)
    do_subscribe_customer_to_plan(
        user=user,
        stripe_customer=stripe_customer,
        stripe_plan_id=plan.stripe_plan_id,
        seat_count=seat_count,
        # TODO: billing address details are passed to us in the request;
        # use that to calculate taxes.
        tax_percent=0)
    do_change_plan_type(user, Realm.PREMIUM)

def attach_discount_to_realm(user: UserProfile, percent_off: int) -> None:
    coupon = Coupon.objects.get(percent_off=percent_off)
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        do_create_customer(user, coupon=coupon)
    else:
        do_replace_coupon(user, coupon)

## Process RealmAuditLog

def do_set_subscription_quantity(
        customer: Customer, timestamp: int, idempotency_key: str, quantity: int) -> None:
    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    stripe_subscription = extract_current_subscription(stripe_customer)
    stripe_subscription.quantity = quantity
    stripe_subscription.proration_date = timestamp
    stripe_subscription.save(idempotency_key=idempotency_key)

def do_adjust_subscription_quantity(
        customer: Customer, timestamp: int, idempotency_key: str, delta: int) -> None:
    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    stripe_subscription = extract_current_subscription(stripe_customer)
    stripe_subscription.quantity = stripe_subscription.quantity + delta
    stripe_subscription.proration_date = timestamp
    stripe_subscription.save(idempotency_key=idempotency_key)

def increment_subscription_quantity(
        customer: Customer, timestamp: int, idempotency_key: str) -> None:
    return do_adjust_subscription_quantity(customer, timestamp, idempotency_key, 1)

def decrement_subscription_quantity(
        customer: Customer, timestamp: int, idempotency_key: str) -> None:
    return do_adjust_subscription_quantity(customer, timestamp, idempotency_key, -1)

@catch_stripe_errors
def process_billing_log_entry(processor: BillingProcessor, log_row: RealmAuditLog) -> None:
    processor.state = BillingProcessor.STARTED
    processor.log_row = log_row
    processor.save()

    customer = Customer.objects.get(realm=log_row.realm)
    timestamp = datetime_to_timestamp(log_row.event_time)
    idempotency_key = 'process_billing_log_entry:%s' % (log_row.id,)
    extra_args = {}  # type: Dict[str, Any]
    if log_row.extra_data is not None:
        extra_args = ujson.loads(log_row.extra_data)
    processing_functions = {
        RealmAuditLog.STRIPE_PLAN_QUANTITY_RESET: do_set_subscription_quantity,
        RealmAuditLog.USER_CREATED: increment_subscription_quantity,
        RealmAuditLog.USER_ACTIVATED: increment_subscription_quantity,
        RealmAuditLog.USER_DEACTIVATED: decrement_subscription_quantity,
        RealmAuditLog.USER_REACTIVATED: increment_subscription_quantity,
    }  # type: Dict[str, Callable[..., None]]
    processing_functions[log_row.event_type](customer, timestamp, idempotency_key, **extra_args)

    processor.state = BillingProcessor.DONE
    processor.save()

def get_next_billing_log_entry(processor: BillingProcessor) -> Optional[RealmAuditLog]:
    if processor.state == BillingProcessor.STARTED:
        return processor.log_row
    assert processor.state != BillingProcessor.STALLED
    if processor.state not in [BillingProcessor.DONE, BillingProcessor.SKIPPED]:
        raise BillingError(
            'unknown processor state',
            "Check for typos, since this value is sometimes set by hand: %s" % (processor.state,))

    if processor.realm is None:
        realms_with_processors = BillingProcessor.objects.exclude(
            realm=None).values_list('realm', flat=True)
        query = RealmAuditLog.objects.exclude(realm__in=realms_with_processors)
    else:
        global_processor = BillingProcessor.objects.get(realm=None)
        query = RealmAuditLog.objects.filter(
            realm=processor.realm, id__lt=global_processor.log_row.id)
    return query.filter(id__gt=processor.log_row.id,
                        requires_billing_update=True).order_by('id').first()

def run_billing_processor_one_step(processor: BillingProcessor) -> bool:
    # Returns True if a row was processed, or if processing was attempted
    log_row = get_next_billing_log_entry(processor)
    if log_row is None:
        if processor.realm is not None:
            processor.delete()
        return False
    try:
        process_billing_log_entry(processor, log_row)
        return True
    except Exception as e:
        billing_logger.error("Error on log_row.realm=%s, event_type=%s, log_row.id=%s, "
                             "processor.id=%s, processor.realm=%s" % (
                                 processor.log_row.realm.string_id, processor.log_row.event_type,
                                 processor.log_row.id, processor.id, processor.realm))
        if isinstance(e, StripeCardError):
            if processor.realm is None:
                BillingProcessor.objects.create(log_row=processor.log_row,
                                                realm=processor.log_row.realm,
                                                state=BillingProcessor.STALLED)
                processor.state = BillingProcessor.SKIPPED
            else:
                processor.state = BillingProcessor.STALLED
            processor.save()
            return True
        raise

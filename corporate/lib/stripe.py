from datetime import datetime
from decimal import Decimal
from functools import wraps
import logging
import os
from typing import Any, Callable, Dict, Optional, TypeVar, Tuple, cast
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
from corporate.models import Customer, CustomerPlan, Plan, Coupon, \
    get_active_plan
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

# Be extremely careful changing this function. Historical billing periods
# are not stored anywhere, and are just computed on the fly using this
# function. Any change you make here should return the same value (or be
# within a few seconds) for basically any value from when the billing system
# went online to within a year from now.
def add_months(dt: datetime, months: int) -> datetime:
    assert(months >= 0)
    # It's fine that the max day in Feb is 28 for leap years.
    MAX_DAY_FOR_MONTH = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                         7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    year = dt.year
    month = dt.month + months
    while month > 12:
        year += 1
        month -= 12
    day = min(dt.day, MAX_DAY_FOR_MONTH[month])
    # datetimes don't support leap seconds, so don't need to worry about those
    return dt.replace(year=year, month=month, day=day)

def next_month(billing_cycle_anchor: datetime, dt: datetime) -> datetime:
    estimated_months = round((dt - billing_cycle_anchor).days * 12. / 365)
    for months in range(max(estimated_months - 1, 0), estimated_months + 2):
        proposed_next_month = add_months(billing_cycle_anchor, months)
        if 20 < (proposed_next_month - dt).days < 40:
            return proposed_next_month
    raise AssertionError('Something wrong in next_month calculation with '
                         'billing_cycle_anchor: %s, dt: %s' % (billing_cycle_anchor, dt))

# TODO take downgrade into account
def next_renewal_date(plan: CustomerPlan) -> datetime:
    months_per_period = {
        CustomerPlan.ANNUAL: 12,
        CustomerPlan.MONTHLY: 1,
    }[plan.billing_schedule]
    periods = 1
    dt = plan.billing_cycle_anchor
    while dt <= plan.billed_through:
        dt = add_months(plan.billing_cycle_anchor, months_per_period * periods)
        periods += 1
    return dt

def renewal_amount(plan: CustomerPlan) -> int:  # nocoverage: TODO
    if plan.fixed_price is not None:
        basis = plan.fixed_price
    elif plan.automanage_licenses:
        assert(plan.price_per_license is not None)
        basis = plan.price_per_license * get_seat_count(plan.customer.realm)
    else:
        assert(plan.price_per_license is not None)
        basis = plan.price_per_license * plan.licenses
    if plan.discount is None:
        return basis
    # TODO: figure out right thing to do with Decimal
    return int(float(basis * (100 - plan.discount) / 100) + .00001)

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
def do_create_customer(user: UserProfile, stripe_token: Optional[str]=None) -> Customer:
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
        customer = Customer.objects.create(realm=realm, stripe_customer_id=stripe_customer.id)
        user.is_billing_admin = True
        user.save(update_fields=["is_billing_admin"])
    return customer

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

# Returns Customer instead of stripe_customer so that we don't make a Stripe
# API call if there's nothing to update
def update_or_create_stripe_customer(user: UserProfile, stripe_token: Optional[str]=None) -> Customer:
    realm = user.realm
    customer = Customer.objects.filter(realm=realm).first()
    if customer is None:
        return do_create_customer(user, stripe_token=stripe_token)
    if stripe_token is not None:
        do_replace_payment_source(user, stripe_token)
    return customer

def compute_plan_parameters(
        automanage_licenses: bool, billing_schedule: int,
        discount: Optional[Decimal]) -> Tuple[datetime, datetime, datetime, int]:
    # Everything in Stripe is stored as timestamps with 1 second resolution,
    # so standardize on 1 second resolution.
    # TODO talk about leapseconds?
    billing_cycle_anchor = timezone_now().replace(microsecond=0)
    if billing_schedule == CustomerPlan.ANNUAL:
        # TODO use variables to account for Zulip Plus
        price_per_license = 8000
        period_end = add_months(billing_cycle_anchor, 12)
    elif billing_schedule == CustomerPlan.MONTHLY:
        price_per_license = 800
        period_end = add_months(billing_cycle_anchor, 1)
    else:
        raise AssertionError('Unknown billing_schedule: {}'.format(billing_schedule))
    if discount is not None:
        # There are no fractional cents in Stripe, so round down to nearest integer.
        price_per_license = int(float(price_per_license * (1 - discount / 100)) + .00001)
    next_billing_date = period_end
    if automanage_licenses:
        next_billing_date = add_months(billing_cycle_anchor, 1)
    return billing_cycle_anchor, next_billing_date, period_end, price_per_license

# Only used for cloud signups
@catch_stripe_errors
def process_initial_upgrade(user: UserProfile, licenses: int, automanage_licenses: bool,
                            billing_schedule: int, stripe_token: Optional[str]) -> None:
    realm = user.realm
    customer = update_or_create_stripe_customer(user, stripe_token=stripe_token)
    # TODO write a test for this
    if CustomerPlan.objects.filter(customer=customer, status=CustomerPlan.ACTIVE).exists():  # nocoverage
        # Unlikely race condition from two people upgrading (clicking "Make payment")
        # at exactly the same time. Doesn't fully resolve the race condition, but having
        # a check here reduces the likelihood.
        billing_logger.warning(
            "Customer {} trying to upgrade, but has an active subscription".format(customer))
        raise BillingError('subscribing with existing subscription', BillingError.TRY_RELOADING)

    billing_cycle_anchor, next_billing_date, period_end, price_per_license = compute_plan_parameters(
        automanage_licenses, billing_schedule, customer.default_discount)
    # The main design constraint in this function is that if you upgrade with a credit card, and the
    # charge fails, everything should be rolled back as if nothing had happened. This is because we
    # expect frequent card failures on initial signup.
    # Hence, if we're going to charge a card, do it at the beginning, even if we later may have to
    # adjust the number of licenses.
    charge_automatically = stripe_token is not None
    if charge_automatically:
        stripe_charge = stripe.Charge.create(
            amount=price_per_license * licenses,
            currency='usd',
            customer=customer.stripe_customer_id,
            description="Upgrade to Zulip Standard, ${} x {}".format(price_per_license/100, licenses),
            receipt_email=user.email,
            statement_descriptor='Zulip Standard')
        # Not setting a period start and end, but maybe we should? Unclear what will make things
        # most similar to the renewal case from an accounting perspective.
        stripe.InvoiceItem.create(
            amount=price_per_license * licenses * -1,
            currency='usd',
            customer=customer.stripe_customer_id,
            description="Payment (Card ending in {})".format(cast(stripe.Card, stripe_charge.source).last4),
            discountable=False)

    # TODO: The correctness of this relies on user creation, deactivation, etc being
    # in a transaction.atomic() with the relevant RealmAuditLog entries
    with transaction.atomic():
        # billed_licenses can greater than licenses if users are added between the start of
        # this function (process_initial_upgrade) and now
        billed_licenses = max(get_seat_count(realm), licenses)
        plan_params = {
            'licenses': billed_licenses,
            'automanage_licenses': automanage_licenses,
            'charge_automatically': charge_automatically,
            'price_per_license': price_per_license,
            'discount': customer.default_discount,
            'billing_cycle_anchor': billing_cycle_anchor,
            'billing_schedule': billing_schedule,
            'tier': CustomerPlan.STANDARD}
        CustomerPlan.objects.create(
            customer=customer,
            billed_through=billing_cycle_anchor,
            next_billing_date=next_billing_date,
            **plan_params)
        RealmAuditLog.objects.create(
            realm=realm, acting_user=user, event_time=billing_cycle_anchor,
            event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED,
            # TODO: add tests for licenses
            # Only 'licenses' is guaranteed to be useful to automated tools. The other extra_data
            # fields can change in the future and are only meant to assist manual debugging.
            extra_data=ujson.dumps(plan_params))
    description = 'Zulip Standard'
    if customer.default_discount is not None:  # nocoverage: TODO
        description += ' (%s%% off)' % (customer.default_discount,)
    stripe.InvoiceItem.create(
        currency='usd',
        customer=customer.stripe_customer_id,
        description=description,
        discountable=False,
        period = {'start': datetime_to_timestamp(billing_cycle_anchor),
                  'end': datetime_to_timestamp(period_end)},
        quantity=billed_licenses,
        unit_amount=price_per_license)

    if charge_automatically:
        billing_method = 'charge_automatically'
        days_until_due = None
    else:
        billing_method = 'send_invoice'
        days_until_due = DEFAULT_INVOICE_DAYS_UNTIL_DUE
    stripe_invoice = stripe.Invoice.create(
        auto_advance=True,
        billing=billing_method,
        customer=customer.stripe_customer_id,
        days_until_due=days_until_due,
        statement_descriptor='Zulip Standard')
    stripe.Invoice.finalize_invoice(stripe_invoice)

    do_change_plan_type(realm, Realm.STANDARD)

def attach_discount_to_realm(user: UserProfile, discount: Decimal) -> None:
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        customer = do_create_customer(user)
    customer.default_discount = discount
    customer.save()

def process_downgrade(user: UserProfile) -> None:  # nocoverage
    pass

def estimate_annual_recurring_revenue_by_realm() -> Dict[str, int]:  # nocoverage
    annual_revenue = {}
    for plan in CustomerPlan.objects.filter(
            status=CustomerPlan.ACTIVE).select_related('customer__realm'):
        renewal_cents = renewal_amount(plan)
        if plan.billing_schedule == CustomerPlan.MONTHLY:
            renewal_cents *= 12
        # TODO: Decimal stuff
        annual_revenue[plan.customer.realm.string_id] = int(renewal_cents / 100)
    return annual_revenue

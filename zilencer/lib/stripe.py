import datetime
from functools import wraps
import logging
import os
from typing import Any, Callable, Optional, TypeVar
import ujson

from django.conf import settings
from django.db import transaction
from django.utils.translation import ugettext as _
import stripe

from zerver.lib.exceptions import JsonableError
from zerver.lib.logging_util import log_to_file
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
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

class StripeError(JsonableError):
    pass

def catch_stripe_errors(func: CallableT) -> CallableT:
    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if STRIPE_PUBLISHABLE_KEY is None:
            # Dev-only message; no translation needed.
            raise StripeError(
                "Missing Stripe config. See https://zulip.readthedocs.io/en/latest/subsystems/billing.html.")
        try:
            return func(*args, **kwargs)
        except stripe.error.StripeError as e:
            billing_logger.error("Stripe error: %d %s",
                                 e.http_status, e.__class__.__name__)
            if isinstance(e, stripe.error.CardError):
                raise StripeError(e.json_body.get('error', {}).get('message'))
            else:
                raise StripeError(
                    _("Something went wrong. Please try again or email us at %s.")
                    % (settings.ZULIP_ADMINISTRATOR,))
        except Exception:
            billing_logger.exception("Uncaught error in Stripe integration")
            raise
    return wrapped  # type: ignore # https://github.com/python/mypy/issues/1927

@catch_stripe_errors
def get_stripe_customer(stripe_customer_id: int) -> stripe.Customer:
    stripe_customer = stripe.Customer.retrieve(stripe_customer_id)
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"retrieve_customer": ', str(stripe_customer), ',']))  # nocoverage
    return stripe_customer

@catch_stripe_errors
def get_upcoming_invoice(stripe_customer_id: int) -> stripe.Invoice:
    stripe_invoice = stripe.Invoice.upcoming(customer=stripe_customer_id)
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"upcoming_invoice": ', str(stripe_invoice), ',']))  # nocoverage
    return stripe_invoice

@catch_stripe_errors
def payment_source(stripe_customer: stripe.Customer) -> Optional[stripe.Card]:
    if stripe_customer.default_source is None:
        return None  # nocoverage -- no way to get here yet
    for source in stripe_customer.sources.data:
        if source.id == stripe_customer.default_source:
            return source
    raise AssertionError("Default source not in sources.")

@catch_stripe_errors
def do_create_customer_with_payment_source(user: UserProfile, stripe_token: str) -> Customer:
    realm = user.realm
    stripe_customer = stripe.Customer.create(
        description="%s (%s)" % (realm.string_id, realm.name),
        metadata={'realm_id': realm.id, 'realm_str': realm.string_id},
        source=stripe_token)
    if PRINT_STRIPE_FIXTURE_DATA:
        print(''.join(['"create_customer": ', str(stripe_customer), ',']))  # nocoverage
    event_time = timestamp_to_datetime(stripe_customer.created)
    RealmAuditLog.objects.create(
        realm=user.realm, acting_user=user, event_type=RealmAuditLog.STRIPE_START, event_time=event_time)
    RealmAuditLog.objects.create(
        realm=user.realm, acting_user=user, event_type=RealmAuditLog.CARD_ADDED, event_time=event_time)
    return Customer.objects.create(
        realm=realm,
        stripe_customer_id=stripe_customer.id,
        billing_user=user)

@catch_stripe_errors
def do_subscribe_customer_to_plan(customer: Customer, stripe_plan_id: int,
                                  seat_count: int, tax_percent: float) -> None:
    # TODO: check that there are no existing live Stripe subscriptions
    # (canceled subscriptions are ok)
    stripe_subscription = stripe.Subscription.create(
        customer=customer.stripe_customer_id,
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
        customer.realm.has_seat_based_plan = True
        customer.realm.save(update_fields=['has_seat_based_plan'])
        RealmAuditLog.objects.create(
            realm=customer.realm,
            acting_user=customer.billing_user,
            event_type=RealmAuditLog.PLAN_START,
            event_time=timestamp_to_datetime(stripe_subscription.created),
            extra_data=ujson.dumps({'plan': stripe_plan_id, 'quantity': seat_count}))

        current_seat_count = get_seat_count(customer.realm)
        if seat_count != current_seat_count:
            RealmAuditLog.objects.create(
                realm=customer.realm,
                event_type=RealmAuditLog.PLAN_UPDATE_QUANTITY,
                event_time=timestamp_to_datetime(stripe_subscription.created),
                requires_billing_update=True,
                extra_data=ujson.dumps({'quantity': current_seat_count}))

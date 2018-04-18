from functools import wraps
import logging
import os
from typing import Any, Callable, Optional, Text, TypeVar

from django.conf import settings
from django.utils.translation import ugettext as _
import stripe

from zerver.lib.exceptions import JsonableError
from zerver.lib.logging_util import log_to_file
from zerver.models import Realm, UserProfile
from zilencer.models import Customer, Plan
from zproject.settings import get_secret

STRIPE_SECRET_KEY = get_secret('stripe_secret_key')
STRIPE_PUBLISHABLE_KEY = get_secret('stripe_publishable_key')
stripe.api_key = STRIPE_SECRET_KEY

BILLING_LOG_PATH = os.path.join('/var/log/zulip'
                                if not settings.DEVELOPMENT
                                else settings.DEVELOPMENT_LOG_DIRECTORY,
                                'billing.log')
billing_logger = logging.getLogger('zilencer.stripe')
log_to_file(billing_logger, BILLING_LOG_PATH)
log_to_file(logging.getLogger('stripe'), BILLING_LOG_PATH)

CallableT = TypeVar('CallableT', bound=Callable[..., Any])

class StripeError(JsonableError):
    pass

def catch_stripe_errors(func: CallableT) -> CallableT:
    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if STRIPE_PUBLISHABLE_KEY is None:
            # Go to https://dashboard.stripe.com/account/apikeys, and add
            # the publishable key and secret key as stripe_publishable_key
            # and stripe_secret_key to zproject/dev-secrets.conf.
            # Dev-only message; no translation needed.
            raise StripeError(
                "Missing Stripe config. In dev, add stripe credentials to zproject/dev-secrets.conf.")
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
        except Exception as e:
            billing_logger.exception("Uncaught error in Stripe integration")
            raise
    return wrapped  # type: ignore # https://github.com/python/mypy/issues/1927

def payment_source(stripe_customer: Any) -> Any:
    if stripe_customer.default_source is None:
        return None
    for source in stripe_customer.sources.data:
        if source.id == stripe_customer.default_source:
            return source

# TODO: Replace Any with appropriate type, like stripe.api_resources.customer.Customer
def get_stripe_customer(stripe_customer_id: int) -> Any:
    return stripe.Customer.retrieve(stripe_customer_id)

def get_upcoming_invoice(stripe_customer_id: int) -> Any:
    return stripe.Invoice.upcoming(customer=stripe_customer_id)

def do_create_customer_with_payment_source(user: UserProfile, stripe_token: Text) -> int:
    realm = user.realm
    stripe_customer = stripe.Customer.create(
        description="%s (%s)" % (realm.string_id, realm.name),
        metadata={'realm_id': realm.id, 'realm_str': realm.string_id},
        source=stripe_token)
    Customer.objects.create(realm=realm, stripe_customer_id=stripe_customer.id, billing_user=user)
    return stripe_customer.id

def do_subscribe_customer_to_plan(stripe_customer_id: int, stripe_plan_id: int,
                                  num_users: int, tax_percent: float) -> None:
    stripe.Subscription.create(
        customer=stripe_customer_id,
        billing='charge_automatically',
        items=[{
            'plan': stripe_plan_id,
            'quantity': num_users,
        }],
        prorate=True,
        tax_percent=tax_percent,
    )

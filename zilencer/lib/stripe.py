from functools import wraps
import logging
import os
from typing import Any, Callable, TypeVar

from django.conf import settings
from django.utils.translation import ugettext as _
import stripe

from zerver.lib.exceptions import JsonableError
from zerver.lib.logging_util import log_to_file
from zerver.models import Realm, UserProfile
from zilencer.models import Customer
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
            # Dev-only message; no translation needed.
            raise StripeError(
                "Missing Stripe config. In dev, add to zproject/dev-secrets.conf .")
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

@catch_stripe_errors
def count_stripe_cards(realm: Realm) -> int:
    try:
        customer_obj = Customer.objects.get(realm=realm)
        cards = stripe.Customer.retrieve(customer_obj.stripe_customer_id).sources.all(object="card")
        return len(cards["data"])
    except Customer.DoesNotExist:
        return 0

@catch_stripe_errors
def save_stripe_token(user: UserProfile, token: str) -> int:
    """Returns total number of cards."""
    # The card metadata doesn't show up in Dashboard but can be accessed
    # using the API.
    card_metadata = {"added_user_id": user.id, "added_user_email": user.email}
    try:
        customer_obj = Customer.objects.get(realm=user.realm)
        customer = stripe.Customer.retrieve(customer_obj.stripe_customer_id)
        billing_logger.info("Adding card on customer %s: source=%r, metadata=%r",
                            customer_obj.stripe_customer_id, token, card_metadata)
        card = customer.sources.create(source=token, metadata=card_metadata)
        customer.default_source = card.id
        customer.save()
        return len(customer.sources.list(object="card")["data"])
    except Customer.DoesNotExist:
        customer_metadata = {"string_id": user.realm.string_id}
        # Description makes it easier to identify customers in Stripe dashboard
        description = "{} ({})".format(user.realm.name, user.realm.string_id)
        billing_logger.info("Creating customer: source=%r, description=%r, metadata=%r",
                            token, description, customer_metadata)
        customer = stripe.Customer.create(source=token,
                                          description=description,
                                          metadata=customer_metadata)

        card = customer.sources.list(object="card")["data"][0]
        card.metadata = card_metadata
        card.save()
        Customer.objects.create(realm=user.realm, stripe_customer_id=customer.id)
        return 1

import logging
from typing import Any, Dict

import stripe
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from corporate.lib.stripe import RealmBillingSession
from corporate.models import PaymentIntent, Session
from zerver.decorator import require_billing_access, require_organization_member
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

billing_logger = logging.getLogger("corporate.stripe")


@require_billing_access
def start_card_update_stripe_session(request: HttpRequest, user: UserProfile) -> HttpResponse:
    billing_session = RealmBillingSession(user)
    assert billing_session.get_customer() is not None
    metadata = {
        "type": "card_update",
        "user_id": user.id,
    }
    stripe_session = billing_session.create_stripe_checkout_session(
        metadata, Session.CARD_UPDATE_FROM_BILLING_PAGE
    )
    return json_success(
        request,
        data={
            "stripe_session_url": stripe_session.url,
            "stripe_session_id": stripe_session.id,
        },
    )


@require_organization_member
@has_request_variables
def start_retry_payment_intent_session(
    request: HttpRequest, user: UserProfile, stripe_payment_intent_id: str = REQ()
) -> HttpResponse:
    billing_session = RealmBillingSession(user)
    customer = billing_session.get_customer()
    if customer is None:
        raise JsonableError(_("Please create a customer first."))

    try:
        payment_intent = PaymentIntent.objects.get(
            stripe_payment_intent_id=stripe_payment_intent_id, customer=customer
        )
    except PaymentIntent.DoesNotExist:
        raise JsonableError(_("Invalid payment intent id."))

    stripe_payment_intent = stripe.PaymentIntent.retrieve(stripe_payment_intent_id)

    if stripe_payment_intent.status == "succeeded":
        raise JsonableError(_("Payment already succeeded."))

    if (
        stripe_payment_intent.status == "processing"
    ):  # nocoverage: Hard to arrive at this state using card
        raise JsonableError(_("Payment processing."))

    metadata: Dict[str, Any] = {
        "user_id": user.id,
    }
    metadata.update(stripe_payment_intent.metadata)
    stripe_session = billing_session.create_stripe_checkout_session(
        metadata, Session.RETRY_UPGRADE_WITH_ANOTHER_PAYMENT_METHOD, payment_intent
    )
    return json_success(
        request,
        data={
            "stripe_session_id": stripe_session.id,
            "stripe_session_url": stripe_session.url,
        },
    )

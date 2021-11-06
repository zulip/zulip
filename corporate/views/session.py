import logging

import stripe
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from corporate.models import PaymentIntent, Session, get_customer_by_realm
from zerver.decorator import require_billing_access, require_organization_member
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

billing_logger = logging.getLogger("corporate.stripe")


@require_billing_access
@has_request_variables
def start_card_update_stripe_session(request: HttpRequest, user: UserProfile) -> HttpResponse:
    customer = get_customer_by_realm(user.realm)
    assert customer
    stripe_session = stripe.checkout.Session.create(
        cancel_url=f"{user.realm.uri}/billing/",
        customer=customer.stripe_customer_id,
        metadata={
            "type": "card_update",
        },
        mode="setup",
        payment_method_types=["card"],
        success_url=f"{user.realm.uri}/billing/event_status?stripe_session_id={{CHECKOUT_SESSION_ID}}",
    )
    Session.objects.create(
        stripe_session_id=stripe_session.id,
        customer=customer,
        type=Session.CARD_UPDATE_FROM_BILLING_PAGE,
    )
    return json_success(
        data={
            "stripe_session_url": stripe_session.url,
            "stripe_session_id": stripe_session.id,
        }
    )


@require_organization_member
@has_request_variables
def start_retry_payment_intent_session(
    request: HttpRequest, user: UserProfile, stripe_payment_intent_id: str = REQ()
) -> HttpResponse:
    customer = get_customer_by_realm(user.realm)
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

    metadata = stripe_payment_intent.metadata
    stripe_session = stripe.checkout.Session.create(
        cancel_url=f"{user.realm.uri}/upgrade/",
        customer=customer.stripe_customer_id,
        metadata=metadata,
        setup_intent_data={"metadata": metadata},
        mode="setup",
        payment_method_types=["card"],
        success_url=f"{user.realm.uri}/billing/event_status?stripe_session_id={{CHECKOUT_SESSION_ID}}",
    )
    session = Session.objects.create(
        stripe_session_id=stripe_session.id,
        customer=customer,
        type=Session.RETRY_UPGRADE_WITH_ANOTHER_PAYMENT_METHOD,
    )

    session.payment_intent = payment_intent
    session.save(update_fields=["payment_intent"])
    session.save()
    return json_success(
        data={
            "stripe_session_id": stripe_session.id,
            "stripe_session_url": stripe_session.url,
        }
    )

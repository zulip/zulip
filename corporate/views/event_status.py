import logging
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from corporate.models import PaymentIntent, Session, get_customer_by_realm
from zerver.decorator import require_organization_member, zulip_login_required
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

billing_logger = logging.getLogger("corporate.stripe")


@require_organization_member
@has_request_variables
def event_status(
    request: HttpRequest,
    user: UserProfile,
    stripe_session_id: Optional[str] = REQ(default=None),
    stripe_payment_intent_id: Optional[str] = REQ(default=None),
) -> HttpResponse:
    customer = get_customer_by_realm(user.realm)
    if customer is None:
        raise JsonableError(_("No customer for this organization!"))

    if stripe_session_id is not None:
        try:
            session = Session.objects.get(stripe_session_id=stripe_session_id, customer=customer)
        except Session.DoesNotExist:
            raise JsonableError(_("Session not found"))

        if session.type == Session.CARD_UPDATE_FROM_BILLING_PAGE and not user.has_billing_access:
            raise JsonableError(_("Must be a billing administrator or an organization owner"))
        return json_success(data={"session": session.to_dict()})

    if stripe_payment_intent_id is not None:
        payment_intent = PaymentIntent.objects.filter(
            stripe_payment_intent_id=stripe_payment_intent_id,
            customer=customer,
        ).last()

        if payment_intent is None:
            raise JsonableError(_("Payment intent not found"))
        return json_success(data={"payment_intent": payment_intent.to_dict()})
    raise JsonableError(_("Pass stripe_session_id or stripe_payment_intent_id"))


@zulip_login_required
@has_request_variables
def event_status_page(
    request: HttpRequest,
    stripe_session_id: str = REQ(default=""),
    stripe_payment_intent_id: str = REQ(default=""),
) -> HttpResponse:
    context = {
        "stripe_session_id": stripe_session_id,
        "stripe_payment_intent_id": stripe_payment_intent_id,
    }
    return render(request, "corporate/event_status.html", context=context)

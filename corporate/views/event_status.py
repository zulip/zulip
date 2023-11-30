import logging
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from corporate.lib.stripe import EventStatusRequest, RealmBillingSession
from zerver.decorator import require_organization_member, zulip_login_required
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
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
    event_status_request = EventStatusRequest(
        stripe_session_id=stripe_session_id, stripe_payment_intent_id=stripe_payment_intent_id
    )
    billing_session = RealmBillingSession(user)
    data = billing_session.get_event_status(event_status_request)
    return json_success(request, data)


@zulip_login_required
@typed_endpoint
def event_status_page(
    request: HttpRequest,
    *,
    stripe_session_id: str = "",
    stripe_payment_intent_id: str = "",
) -> HttpResponse:
    context = {
        "stripe_session_id": stripe_session_id,
        "stripe_payment_intent_id": stripe_payment_intent_id,
    }
    return render(request, "corporate/event_status.html", context=context)

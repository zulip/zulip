import logging

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from corporate.lib.stripe import RealmBillingSession
from corporate.models import Session
from zerver.decorator import require_billing_access, require_organization_member
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
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
@typed_endpoint
def start_card_update_stripe_session_for_realm_upgrade(
    request: HttpRequest,
    user: UserProfile,
    *,
    manual_license_management: Json[bool] = False,
) -> HttpResponse:
    billing_session = RealmBillingSession(user)
    metadata = {
        "type": "card_update",
        "user_id": user.id,
    }
    stripe_session = billing_session.create_stripe_update_card_for_realm_upgrade_session(
        metadata, Session.CARD_UPDATE_FROM_UPGRADE_PAGE, manual_license_management
    )
    return json_success(
        request,
        data={
            "stripe_session_url": stripe_session.url,
            "stripe_session_id": stripe_session.id,
        },
    )

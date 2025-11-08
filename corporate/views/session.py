import logging
from typing import TYPE_CHECKING

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from corporate.lib.decorator import (
    authenticated_remote_realm_management_endpoint,
    authenticated_remote_server_management_endpoint,
)
from zerver.decorator import require_billing_access, require_organization_member
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

if TYPE_CHECKING:
    from corporate.lib.stripe import RemoteRealmBillingSession, RemoteServerBillingSession

billing_logger = logging.getLogger("corporate.stripe")


@require_billing_access
def start_card_update_stripe_session(request: HttpRequest, user: UserProfile) -> HttpResponse:
    from corporate.lib.stripe import RealmBillingSession

    billing_session = RealmBillingSession(user)
    session_data = billing_session.create_card_update_session()
    return json_success(
        request,
        data=session_data,
    )


@authenticated_remote_realm_management_endpoint
def start_card_update_stripe_session_for_remote_realm(
    request: HttpRequest, billing_session: "RemoteRealmBillingSession"
) -> HttpResponse:  # nocoverage
    session_data = billing_session.create_card_update_session()
    return json_success(
        request,
        data=session_data,
    )


@authenticated_remote_server_management_endpoint
def start_card_update_stripe_session_for_remote_server(
    request: HttpRequest, billing_session: "RemoteServerBillingSession"
) -> HttpResponse:  # nocoverage
    session_data = billing_session.create_card_update_session()
    return json_success(
        request,
        data=session_data,
    )


@require_organization_member
@typed_endpoint
def start_card_update_stripe_session_for_realm_upgrade(
    request: HttpRequest,
    user: UserProfile,
    *,
    manual_license_management: Json[bool] = False,
    tier: Json[int],
) -> HttpResponse:
    from corporate.lib.stripe import RealmBillingSession

    billing_session = RealmBillingSession(user)
    session_data = billing_session.create_card_update_session_for_upgrade(
        manual_license_management, tier
    )
    return json_success(
        request,
        data=session_data,
    )


@typed_endpoint
@authenticated_remote_realm_management_endpoint
def start_card_update_stripe_session_for_remote_realm_upgrade(
    request: HttpRequest,
    billing_session: "RemoteRealmBillingSession",
    *,
    manual_license_management: Json[bool] = False,
    tier: Json[int],
) -> HttpResponse:
    session_data = billing_session.create_card_update_session_for_upgrade(
        manual_license_management, tier
    )
    return json_success(
        request,
        data=session_data,
    )


@typed_endpoint
@authenticated_remote_server_management_endpoint
def start_card_update_stripe_session_for_remote_server_upgrade(
    request: HttpRequest,
    billing_session: "RemoteServerBillingSession",
    *,
    manual_license_management: Json[bool] = False,
    tier: Json[int],
) -> HttpResponse:
    session_data = billing_session.create_card_update_session_for_upgrade(
        manual_license_management, tier
    )
    return json_success(
        request,
        data=session_data,
    )

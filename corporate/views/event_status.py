import logging
from typing import TYPE_CHECKING

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from corporate.lib.decorator import (
    authenticated_remote_realm_management_endpoint,
    authenticated_remote_server_management_endpoint,
    self_hosting_management_endpoint,
)
from zerver.decorator import require_organization_member, zulip_login_required
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

if TYPE_CHECKING:
    from corporate.lib.stripe import RemoteRealmBillingSession, RemoteServerBillingSession

billing_logger = logging.getLogger("corporate.stripe")


@require_organization_member
@typed_endpoint
def event_status(
    request: HttpRequest,
    user: UserProfile,
    *,
    stripe_session_id: str | None = None,
    stripe_invoice_id: str | None = None,
) -> HttpResponse:
    from corporate.lib.stripe import EventStatusRequest, RealmBillingSession

    event_status_request = EventStatusRequest(
        stripe_session_id=stripe_session_id, stripe_invoice_id=stripe_invoice_id
    )
    billing_session = RealmBillingSession(user)
    data = billing_session.get_event_status(event_status_request)
    return json_success(request, data)


@typed_endpoint
@authenticated_remote_realm_management_endpoint
def remote_realm_event_status(
    request: HttpRequest,
    billing_session: "RemoteRealmBillingSession",
    *,
    stripe_session_id: str | None = None,
    stripe_invoice_id: str | None = None,
) -> HttpResponse:
    from corporate.lib.stripe import EventStatusRequest

    event_status_request = EventStatusRequest(
        stripe_session_id=stripe_session_id, stripe_invoice_id=stripe_invoice_id
    )
    data = billing_session.get_event_status(event_status_request)
    return json_success(request, data)


@typed_endpoint
@authenticated_remote_server_management_endpoint
def remote_server_event_status(
    request: HttpRequest,
    billing_session: "RemoteServerBillingSession",
    *,
    stripe_session_id: str | None = None,
    stripe_invoice_id: str | None = None,
) -> HttpResponse:  # nocoverage
    from corporate.lib.stripe import EventStatusRequest

    event_status_request = EventStatusRequest(
        stripe_session_id=stripe_session_id, stripe_invoice_id=stripe_invoice_id
    )
    data = billing_session.get_event_status(event_status_request)
    return json_success(request, data)


@zulip_login_required
@typed_endpoint
def event_status_page(
    request: HttpRequest,
    *,
    stripe_session_id: str = "",
    stripe_invoice_id: str = "",
) -> HttpResponse:
    context = {
        "stripe_session_id": stripe_session_id,
        "stripe_invoice_id": stripe_invoice_id,
        "billing_base_url": "",
    }
    return render(request, "corporate/billing/event_status.html", context=context)


@self_hosting_management_endpoint
@typed_endpoint
def remote_realm_event_status_page(
    request: HttpRequest,
    *,
    realm_uuid: str = "",
    server_uuid: str = "",
    stripe_session_id: str = "",
    stripe_invoice_id: str = "",
) -> HttpResponse:  # nocoverage
    context = {
        "stripe_session_id": stripe_session_id,
        "stripe_invoice_id": stripe_invoice_id,
        "billing_base_url": f"/realm/{realm_uuid}",
    }
    return render(request, "corporate/billing/event_status.html", context=context)


@self_hosting_management_endpoint
@typed_endpoint
def remote_server_event_status_page(
    request: HttpRequest,
    *,
    realm_uuid: str = "",
    server_uuid: str = "",
    stripe_session_id: str = "",
    stripe_invoice_id: str = "",
) -> HttpResponse:  # nocoverage
    context = {
        "stripe_session_id": stripe_session_id,
        "stripe_invoice_id": stripe_invoice_id,
        "billing_base_url": f"/server/{server_uuid}",
    }
    return render(request, "corporate/billing/event_status.html", context=context)

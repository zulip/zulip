import datetime
from typing import Any, Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    get_http_headers_from_filename,
    validate_extract_webhook_http_header,
)
from zerver.models import UserProfile

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GITHUB_EVENT")


def sponsorship_cancelled(payload: Dict[str, Any]) -> str:
    sponsorship = payload["sponsorship"]
    cancelled_date = datetime.datetime.strptime(
        sponsorship["created_at"][:10], "%Y-%m-%d"
    ).strftime("%d %B %Y")
    body = f":warning: Uh Oh! Sponsorship Cancelled! :warning:\nSomebody cancelled their sponsorship on {cancelled_date}!"
    return body


def sponsorship_created(payload: Dict[str, Any]) -> str:
    sponsorship = payload["sponsorship"]
    sponsor = sponsorship["sponsor"]["login"]
    subscription = sponsorship["tier"]["name"]
    subscribed_date = datetime.datetime.strptime(
        sponsorship["created_at"][:10], "%Y-%m-%d"
    ).strftime("%d %B %Y")
    body = f':tada: New Subscription for a Sponsorship! :tada:\n{sponsor} subscribed for a "{subscription}" Sponsorship on {subscribed_date}!'
    return body


def sponsorship_pending_cancellation(payload: Dict[str, Any]) -> str:
    effective_date = datetime.datetime.strptime(
        payload["effective_date"][:10], "%Y-%m-%d"
    ).strftime("%d %B %Y")
    body = f":warning: Uh Oh!Upcoming Sponsorship Cancellation! :warning:\nSomebody cancelled their sponsorship! Effective from {effective_date}."
    return body


def sponsership_pending_tier_change(payload: Dict[str, Any]) -> str:
    sponsorship = payload["sponsorship"]
    sponsor = sponsorship["sponsor"]["login"]
    old_subscription = payload["changes"]["tier"]["from"]["name"]
    new_subscription = sponsorship["tier"]["name"]
    effective_date = datetime.datetime.strptime(
        payload["effective_date"][:10], "%Y-%m-%d"
    ).strftime("%d %B %Y")

    body = f':money: Upcoming Subscription Change for a Sponsorship! :money:\n{sponsor} changed subscription from "{old_subscription}" to "{new_subscription}"! Effective from {effective_date}.'
    return body


def sponsership_tier_change(payload: Dict[str, Any]) -> str:
    sponsorship = payload["sponsorship"]
    sponsor = sponsorship["sponsor"]["login"]
    old_subscription = payload["changes"]["tier"]["from"]["name"]
    new_subscription = sponsorship["tier"]["name"]
    changed_date = datetime.datetime.strptime(sponsorship["created_at"][:10], "%Y-%m-%d").strftime(
        "%d %B %Y"
    )

    body = f':money: Subscription Change for a Sponsorship! :money:\n{sponsor} changed subscription from "{old_subscription}" to "{new_subscription}" on {changed_date}!'
    return body


ACTIVITY_FUNCTION_MAPPER: Dict[str, Callable[[Dict[str, Any]], Optional[str]]] = {
    "cancelled": sponsorship_cancelled,
    "created": sponsorship_created,
    "pending_cancellation": sponsorship_pending_cancellation,
    "pending_tier_change": sponsership_pending_tier_change,
    "tier_changed": sponsership_tier_change,
}


@webhook_view("Github Sponsors")
@has_request_variables
def api_githubsponsors_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    header_event = validate_extract_webhook_http_header(
        request, "X_GITHUB_EVENT", "Github Sponsors"
    )
    if header_event is None:
        raise UnsupportedWebhookEventType("no header provided")
    activity = payload["action"]
    handler = ACTIVITY_FUNCTION_MAPPER.get(activity)
    if handler is not None:
        body = handler(payload)
        topic = "githubsponsors"
        if body is not None:
            check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

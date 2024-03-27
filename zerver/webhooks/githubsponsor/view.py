from typing import Any, Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def get_created_body(payload: Dict[str, Any]) -> str:
    template = "New Subscription for a Sponsorship:"
    template = template + "\n{name} subscribed for a {money} a month Sponsorship on {date}."
    return template.format(
        name=payload["sponsorship"]["sponsor"]["name"],
        money=payload["sponsorship"]["tier"]["monthly_price_in_dollars"],
        date=payload["sponsorship"]["created_at"],
    )


def get_pending_tier_change_body(payload: Dict[str, Any]) -> str:
    template = "Upcoming Subscription Change for a Sponsorship:"
    template = (
        template
        + "\n{name} changed subscription from {from_money} to {to_money}. Effective from {effective_date}."
    )
    return template.format(
        name=payload["sponsorship"]["sponsor"]["name"],
        from_money=payload["changes"]["tier"]["from"]["monthly_price_in_dollars"],
        to_money=payload["sponsorship"]["tier"]["monthly_price_in_dollars"],
        effective_date=payload["effective_date"],
    )


def get_tier_changed_body(payload: Dict[str, Any]) -> str:
    template = "Subscription Change for a Sponsorship:"
    template = (
        template
        + "\n{name} changed subscription from {from_money} a month to {to_money} a month on {date}."
    )
    return template.format(
        name=payload["sponsorship"]["sponsor"]["name"],
        from_money=payload["changes"]["tier"]["from"]["monthly_price_in_dollars"],
        to_money=payload["sponsorship"]["tier"]["monthly_price_in_dollars"],
        date=payload["sponsorship"]["created_at"],
    )


def get_pending_cancellation_body(payload: Dict[str, Any]) -> str:
    template = "Upcoming Sponsorship Cancellation:"
    template = template + "\n{name} cancelled their sponsorship. Effective from {effective_date}."
    return template.format(
        name=payload["sponsorship"]["sponsor"]["name"], effective_date=payload["effective_date"]
    )


def get_cancelled_body(payload: Dict[str, Any]) -> str:
    template = "Sponsorship Cancelled:"
    template = template + "\n{name} cancelled their sponsorship on {date}."
    return template.format(
        name=payload["sponsorship"]["sponsor"]["name"], date=payload["sponsorship"]["created_at"]
    )


EVENTS_FUNCTION_MAPPER: Dict[str, Callable[[Dict[str, Any]], Optional[str]]] = {
    "created": get_created_body,
    "pending_tier_change": get_pending_tier_change_body,
    "tier_changed": get_tier_changed_body,
    "pending_cancellation": get_pending_cancellation_body,
    "cancelled": get_cancelled_body,
}


@webhook_view("githubsponsor")
@has_request_variables
def api_githubsponsor_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    # construct the body of the message
    event = payload["action"]
    assert event is not None
    handler = EVENTS_FUNCTION_MAPPER.get(event)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event)

    body = handler(payload)
    topic = "githubsponsor"

    if body is not None:
        check_send_webhook_message(request, user_profile, topic, str(body))
    return json_success(request)

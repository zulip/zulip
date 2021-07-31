from typing import Any, Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.models import UserProfile


# convert fixture names of type members_create -> member:create
# this is done to match the http header X_PATREON_EVENT we get from the incoming webhook
# check patreon webhook docs for more info on why we implemented this
def get_http_headers_from_filename(http_header_key: str) -> Callable[[str], Dict[str, str]]:
    def fixture_to_headers(filename: str) -> Dict[str, str]:
        event_type = ":".join(filename.split("_"))
        return {http_header_key: event_type}

    return fixture_to_headers


fixture_to_headers = get_http_headers_from_filename("HTTP_X_PATREON_EVENT")

# called when new patron joined
def members_create(payload: Dict[str, Any]) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"]
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"]
    body = f"{user_name} joined! :tada:\nYou now have {patron_count} patrons."

    return body


# called when a patron edited their membership information
# including updates on payment charging events
def members_update(payload: Dict[str, Any]) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"]
    body = (
        f"A patron just updated their membership. :notifications:\nPatrons in total: {patron_count}"
    )

    return body


def members_delete(payload: Dict[str, Any]) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"]
    body = (
        f"A patron just deleted their membership. :exclamation:\nPatrons in total: {patron_count}"
    )

    return body


# called when a new patron joined through custom pledge
def members_pledge_create(payload: Dict[str, Any]) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"]
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"]
    pledge_amount = user_data["pledge_amount_cents"] / 100
    body = f"{user_name} joined and pledged ${pledge_amount}. :tada:\nYou now have {patron_count} patrons."

    return body


def members_pledge_update(payload: Dict[str, Any]) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"]
    body = f"A patron just updated their pledge. :notifications:\nPatrons in total: {patron_count}"

    return body


def members_pledge_delete(payload: Dict[str, Any]) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"]
    body = f"A patron just deleted their pledge. :exclamation:\nPatrons in total: {patron_count}"

    return body


EVENTS_FUNCTION_MAPPER: Dict[str, Callable[[Dict[str, Any]], Optional[str]]] = {
    "members:create": members_create,
    "members:update": members_update,
    "members:delete": members_delete,
    "members:pledge:create": members_pledge_create,
    "members:pledge:update": members_pledge_update,
    "members:pledge:delete": members_pledge_delete,
}


@webhook_view("Patreon")
@has_request_variables
def api_patreon_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:

    event = validate_extract_webhook_http_header(request, "X_PATREON_EVENT", "Patreon")
    assert event is not None

    handler = EVENTS_FUNCTION_MAPPER.get(event)
    if handler is None:
        raise UnsupportedWebhookEventType(event)

    body = handler(payload)
    topic = "patreon"

    if body is not None:
        check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

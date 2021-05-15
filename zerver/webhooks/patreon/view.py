from typing import Callable, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_int, check_string, to_wild_value
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.models import UserProfile


# The events for this integration contain the ":" character, which is not appropriate in a
# filename and requires us to deviate from the common `get_http_headers_from_filename` method
# from zerver.lib.webhooks.common.
def get_custom_http_headers_from_filename(http_header_key: str) -> Callable[[str], Dict[str, str]]:
    def fixture_to_headers(filename: str) -> Dict[str, str]:
        event_type = ":".join(filename.split("_"))
        return {http_header_key: event_type}

    return fixture_to_headers


fixture_to_headers = get_custom_http_headers_from_filename("HTTP_X_PATREON_EVENT")


def handle_members_create_event(payload: WildValue) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"].tame(check_int)
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"].tame(check_string)
    body = f"{user_name} has joined as a member! :tada:\nYou now have {patron_count} patron(s)."

    return body


def handle_members_update_event(payload: WildValue) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"].tame(check_int)
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"].tame(check_string)
    body = (
        f"{user_name} just updated their membership. :gear:\nYou now have {patron_count} patron(s)."
    )

    return body


def handle_members_delete_event(payload: WildValue) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"].tame(check_int)
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"].tame(check_string)
    body = f"{user_name} just deleted their membership. :cross_mark:\nYou now have {patron_count} patron(s)."

    return body


def handle_members_pledge_create_event(payload: WildValue) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"].tame(check_int)
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"].tame(check_string)
    pledge_amount = user_data["pledge_amount_cents"].tame(check_int) / 100
    body = f"{user_name} has created a new member pledge of ${pledge_amount}. :tada:\nYou now have {patron_count} patron(s)."

    return body


def handle_members_pledge_update_event(payload: WildValue) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"].tame(check_int)
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"].tame(check_string)
    body = f"{user_name} just updated their pledge. :gear:\nYou now have {patron_count} patron(s)."

    return body


def handle_members_pledge_delete_event(payload: WildValue) -> str:
    included = payload["included"][0]
    patron_count = included["attributes"]["patron_count"].tame(check_int)
    user_data = payload["data"]["attributes"]
    user_name = user_data["full_name"].tame(check_string)
    body = f"{user_name} just deleted their pledge. :cross_mark:\nYou now have {patron_count} patron(s)."

    return body


EVENTS_FUNCTION_MAPPER: Dict[str, Callable[[WildValue], str]] = {
    "members:create": handle_members_create_event,
    "members:update": handle_members_update_event,
    "members:delete": handle_members_delete_event,
    "members:pledge:create": handle_members_pledge_create_event,
    "members:pledge:update": handle_members_pledge_update_event,
    "members:pledge:delete": handle_members_pledge_delete_event,
}


@webhook_view("Patreon")
@has_request_variables
def api_patreon_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:

    event = validate_extract_webhook_http_header(request, "X_PATREON_EVENT", "Patreon")
    assert event is not None

    handler = EVENTS_FUNCTION_MAPPER.get(event)
    if handler is None:
        raise UnsupportedWebhookEventType(event)

    body = handler(payload)
    topic = "Patreon Notifications"
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)

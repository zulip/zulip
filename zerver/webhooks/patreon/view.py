from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.models import UserProfile


# The events for this integration contain the ":" character, which is not appropriate in a
# filename and requires us to deviate from the common `get_http_headers_from_filename` method
# from zerver.lib.webhooks.common.
def get_custom_http_headers_from_filename(http_header_key: str) -> Callable[[str], dict[str, str]]:
    def fixture_to_headers(filename: str) -> dict[str, str]:
        event_type = filename.replace("_", ":")
        return {http_header_key: event_type}

    return fixture_to_headers


fixture_to_headers = get_custom_http_headers_from_filename("HTTP_X_PATREON_EVENT")


def get_members_create_body(payload: WildValue) -> str | None:
    last_charge_status = get_last_charge_status(payload)
    patron_status = get_patron_status(payload)
    # null values indicate the member has never pledged
    if last_charge_status is None and patron_status is None:
        template = "{user_name} has joined as a member!"
        return template.format(
            user_name=get_user_name(payload),
        ).rstrip()
    return None


def get_members_update_body(payload: WildValue) -> str | None:
    last_charge_status = get_last_charge_status(payload)
    patron_status = get_patron_status(payload)
    if last_charge_status in ("Paid", None) and patron_status in ("active_patron", "former_patron"):
        template = "{user_name}'s membership has been updated to {patron_status}."
        return template.format(
            user_name=get_user_name(payload),
            patron_status=str(patron_status).replace("_", " "),
        ).rstrip()
    return None


def get_members_delete_body(payload: WildValue) -> str | None:
    last_charge_status = get_last_charge_status(payload)
    patron_status = get_patron_status(payload)
    # null value indicates the member has never pledged
    if last_charge_status in ("Paid", None) and patron_status != "declined_patron":
        template = "{user_name}'s membership has ended."
        return template.format(
            user_name=get_user_name(payload),
        ).rstrip()
    return None


def get_members_pledge_create_body(payload: WildValue) -> str | None:
    last_charge_status = get_last_charge_status(payload)
    pledge_amount = get_pledge_amount(payload)
    # The only successful charge status is "Paid". null if not yet charged.
    if last_charge_status in ("Paid", None) and pledge_amount > 0:
        template = "{user_name} has pledged ${pledge_amount:.2f} per {pay_per_name}. :tada:\nTotal number of patrons: {patron_count}"
        return template.format(
            user_name=get_user_name(payload),
            pledge_amount=pledge_amount,
            pay_per_name=get_pay_per_name(payload),
            patron_count=get_patron_count(payload),
        ).rstrip()
    return None


def get_members_pledge_update_body(payload: WildValue) -> str | None:
    last_charge_status = get_last_charge_status(payload)
    pledge_amount = get_pledge_amount(payload)
    # The only successful charge status is "Paid". null if not yet charged.
    if last_charge_status in ("Paid", None) and pledge_amount > 0:
        template = "{user_name} has updated their pledge to ${pledge_amount:.2f} per {pay_per_name}. :gear:"
        return template.format(
            user_name=get_user_name(payload),
            pledge_amount=pledge_amount,
            pay_per_name=get_pay_per_name(payload),
        ).rstrip()
    return None


def get_members_pledge_delete_body(payload: WildValue) -> str | None:
    last_charge_status = get_last_charge_status(payload)
    if last_charge_status in ("Paid", "Deleted", None):
        template = "{user_name}'s pledge has been cancelled. :cross_mark:\nTotal number of patrons: {patron_count}"
        return template.format(
            user_name=get_user_name(payload),
            patron_count=get_patron_count(payload),
        ).rstrip()
    return None


def get_last_charge_status(payload: WildValue) -> str | None:
    return payload["data"]["attributes"]["last_charge_status"].tame(check_none_or(check_string))


def get_patron_status(payload: WildValue) -> str | None:
    return payload["data"]["attributes"]["patron_status"].tame(check_none_or(check_string))


def get_user_name(payload: WildValue) -> str:
    return payload["data"]["attributes"]["full_name"].tame(check_string)


def get_pledge_amount(payload: WildValue) -> float:
    return payload["data"]["attributes"]["currently_entitled_amount_cents"].tame(check_int) / 100


def get_patron_count(payload: WildValue) -> int:
    return payload["included"][0]["attributes"]["patron_count"].tame(check_int)


def get_pay_per_name(payload: WildValue) -> str:
    return payload["included"][0]["attributes"]["pay_per_name"].tame(check_string)


EVENT_FUNCTION_MAPPER: dict[str, Callable[[WildValue], str | None]] = {
    "members:create": get_members_create_body,
    "members:update": get_members_update_body,
    "members:delete": get_members_delete_body,
    "members:pledge:create": get_members_pledge_create_body,
    "members:pledge:update": get_members_pledge_update_body,
    "members:pledge:delete": get_members_pledge_delete_body,
}

# deprecated events
IGNORED_EVENTS = [
    "pledges:create",
    "pledges:update",
    "pledges:delete",
]

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("Patreon", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_patreon_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    header_event = validate_extract_webhook_http_header(request, "X-Patreon-Event", "Patreon")

    event_name = get_zulip_event_name(header_event, payload)
    if event_name is None:
        # See IGNORED_EVENTS.
        return json_success(request)
    topic = "membership notifications"

    body_function = EVENT_FUNCTION_MAPPER[event_name]
    body = body_function(payload)

    if body is None:
        # None for payloads that are valid,
        # but where we intentionally do not send a message.
        return json_success(request)

    check_send_webhook_message(request, user_profile, topic, body, event_name)
    return json_success(request)


def get_zulip_event_name(
    header_event: str,
    payload: WildValue,
) -> str | None:
    """
    Usually, we return an event name that is a key in EVENT_FUNCTION_MAPPER.
    We return None for an event that we know we don't want to handle.
    """
    if header_event in EVENT_FUNCTION_MAPPER:
        return header_event
    elif header_event in IGNORED_EVENTS:
        return None
    raise UnsupportedWebhookEventTypeError(header_event)

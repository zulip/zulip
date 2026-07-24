from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import return_success_on_head_request, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

ADMIN_ROLE_UPDATED_TEMPLATE = "{name} is {phrase} an admin."

ADMIN_AWAY_MODE_UPDATED_TEMPLATE = "{name} is {away_status}{reason}."

ADMIN_LOGIN_LOGOUT_TEMPLATE = "{name} {phrase}."


def get_admin_name(payload: WildValue) -> str:
    return payload["data"]["item"]["name"].tame(check_string)


def get_topic_name(event_category: str, payload: WildValue) -> str:
    match event_category:
        case "ping":
            return "Intercom"
        case "admin":
            if payload["topic"].tame(check_string) == "admin.activity_log_event.created":
                return "Admin"
            return f"Admin: {get_admin_name(payload)}"
        case _:  # nocoverage
            raise UnsupportedWebhookEventTypeError(payload["topic"].tame(check_string))


def get_ping_message(payload: WildValue) -> str:
    return get_setup_webhook_message("Intercom")


def get_admin_activity_log_event_created_message(payload: WildValue) -> str:
    return payload["data"]["item"]["activity_description"].tame(check_string)


def get_admin_role_updated_message(phrase: str, payload: WildValue) -> str:
    return ADMIN_ROLE_UPDATED_TEMPLATE.format(name=get_admin_name(payload), phrase=phrase)


def get_admin_login_logout_message(phrase: str, payload: WildValue) -> str:
    return ADMIN_LOGIN_LOGOUT_TEMPLATE.format(name=get_admin_name(payload), phrase=phrase)


def get_admin_away_mode_updated_message(payload: WildValue) -> str:
    admin_name = get_admin_name(payload)
    away_mode_enabled = payload["data"]["item"]["away_mode_enabled"].tame(check_bool)

    if away_mode_enabled:
        away_status = "away"
        reason_value = payload["data"]["item"]["away_status_reason"].tame(check_string)

        # Strip trailing period if exists,
        # since reason will be wrapped inside parentheses.
        reason_value = reason_value.removesuffix(".")
        reason = f" ({reason_value})" if reason_value else ""
    else:
        away_status = "now available"
        reason = ""

    return ADMIN_AWAY_MODE_UPDATED_TEMPLATE.format(
        name=admin_name, away_status=away_status, reason=reason
    )


IGNORED_EVENTS = [
    # Require purchasing an Intercom number.
    *["call"],
    # Might be restricted for trial accounts.
    # Only content_stat.banners was attempted, and it was restricted.
    *["content_stat"],
    # Can only be invoked by SMS from registered US or Canadian numbers.
    *[
        "contact.lead.signed_up",
        "contact.unsubscribed_from_sms",
    ],
    # Unable to invoke these events, likely restricted for trial accounts.
    *[
        "conversation.rating.added",
        "ticket.rating.provided",
        "data_connector.execution.completed",
        "job.completed",
        "messenger.deployment_completed.event.created",
    ],
]


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue], str]] = {
    "ping": get_ping_message,
    "admin.activity_log_event.created": get_admin_activity_log_event_created_message,
    "admin.away_mode_updated": get_admin_away_mode_updated_message,
    "admin.added_to_workspace": partial(get_admin_role_updated_message, "now"),
    "admin.removed_from_workspace": partial(get_admin_role_updated_message, "no longer"),
    "admin.logged_in": partial(get_admin_login_logout_message, "logged in"),
    "admin.logged_out": partial(get_admin_login_logout_message, "logged out"),
}

ALL_EVENT_TYPES = list(EVENT_TO_FUNCTION_MAPPER.keys())


@webhook_view("Intercom", all_event_types=ALL_EVENT_TYPES)
# Intercom sends a HEAD request to validate the webhook URL. In this case, we just assume success.
@return_success_on_head_request
@typed_endpoint
def api_intercom_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event_type = payload["topic"].tame(check_string)
    # event_type is of the form "{event_category}.{event}".
    event_category = event_type.split(".", 1)[0]
    if event_type in IGNORED_EVENTS or event_category in IGNORED_EVENTS:
        return json_success(request)  # nocoverage

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    body = handler(payload)
    topic_name = get_topic_name(event_category, payload)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

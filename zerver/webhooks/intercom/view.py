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

ADMIN_ROLE_UPDATED = "{name} is {phrase} an admin."

ADMIN_AWAY_MODE_UPDATED = "{name} is {away_mode}.{reason}"

ADMIN_LOGIN_LOGOUT = "{name} {phrase}."


def get_admin_name(payload: WildValue) -> str:
    return payload["data"]["item"]["name"].tame(check_string)


def get_entity_topic_name(entity_type: str, entity_name: str | None = None) -> str:
    if entity_name is None:
        return entity_type
    return f"{entity_type}: {entity_name}"


def get_ping_message(payload: WildValue) -> tuple[str, str]:
    body = get_setup_webhook_message("Intercom")
    topic_name = "Intercom"
    return (topic_name, body)


def get_admin_event_log_event_created_message(payload: WildValue) -> tuple[str, str]:
    body = payload["data"]["item"]["activity_description"].tame(check_string)
    topic_name = get_entity_topic_name("Admin")
    return (topic_name, body)


def get_admin_action_message(phrase: str, template: str, payload: WildValue) -> tuple[str, str]:
    admin_name = get_admin_name(payload)
    body = template.format(name=admin_name, phrase=phrase)
    topic_name = get_entity_topic_name("Admin", admin_name)
    return (topic_name, body)


def get_admin_away_mode_updated_message(payload: WildValue) -> tuple[str, str]:
    admin_name = get_admin_name(payload)
    away_mode_enabled = payload["data"]["item"]["away_mode_enabled"].tame(check_bool)

    if away_mode_enabled:
        away_status = "away"
        reason = ""
        reason_value = payload["data"]["item"]["away_status_reason"].tame(check_string)
        if reason_value:
            reason = f" Reason: {reason_value}"
    else:
        away_status = "available"
        reason = ""

    body = ADMIN_AWAY_MODE_UPDATED.format(name=admin_name, away_mode=away_status, reason=reason)
    topic_name = get_entity_topic_name("Admin", admin_name)
    return (topic_name, body)


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


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue], tuple[str, str]]] = {
    "ping": get_ping_message,
    "admin.activity_log_event.created": get_admin_event_log_event_created_message,
    "admin.added_to_workspace": partial(get_admin_action_message, "now", ADMIN_ROLE_UPDATED),
    "admin.removed_from_workspace": partial(
        get_admin_action_message, "no longer", ADMIN_ROLE_UPDATED
    ),
    "admin.away_mode_updated": get_admin_away_mode_updated_message,
    "admin.logged_in": partial(get_admin_action_message, "logged in", ADMIN_LOGIN_LOGOUT),
    "admin.logged_out": partial(get_admin_action_message, "logged out", ADMIN_LOGIN_LOGOUT),
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
    topic_name, body = handler(payload)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

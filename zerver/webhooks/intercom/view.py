from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import return_success_on_head_request, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

ENTITY_TYPES = ("Admin", "Company", "User", "Contact", "Lead", "Ticket", "Conversation", "Visitor")

ADMIN_WORKSPACE_MESSAGE = "Admin **{name}** {action} workspace.".strip()

ADMIN_AWAY_MODE_UPDATED = "Admin **{name}** updated away mode to {away_mode}.".strip()

ADMIN_LOGIN_LOGOUT = "Admin **{name}** {action}.".strip()


def get_ping_message(payload: WildValue) -> tuple[str, str]:
    body = get_setup_webhook_message("Intercom")
    topic_name = "Intercom"
    return (topic_name, body)


def get_admin_name(payload: WildValue) -> str:
    return payload["data"]["item"]["name"].tame(check_string)


def get_entity_topic_name(entity_type: str, entity_name: str | None = None) -> str:
    if entity_name is None:
        return entity_type.capitalize()
    return f"{entity_type.capitalize()}: {entity_name}"


def get_admin_event_log_event_created_message(payload: WildValue) -> tuple[str, str]:
    body = payload["data"]["item"]["activity_description"].tame(check_string)
    topic_name = get_entity_topic_name(ENTITY_TYPES[0])
    return (topic_name, body)


def get_admin_action_message(action: str, template: str, payload: WildValue) -> tuple[str, str]:
    admin_name = get_admin_name(payload)
    body = template.format(name=admin_name, action=action)
    topic_name = get_entity_topic_name(ENTITY_TYPES[0], admin_name)
    return (topic_name, body)


def get_admin_away_mode_updated_message(payload: WildValue) -> tuple[str, str]:
    admin_name = get_admin_name(payload)
    away_mode_enabled = payload["data"]["item"]["away_mode_enabled"].tame(check_bool)
    away_status = "enabled" if away_mode_enabled else "disabled"
    body = ADMIN_AWAY_MODE_UPDATED.format(name=admin_name, away_mode=away_status)
    topic_name = get_entity_topic_name(ENTITY_TYPES[0], admin_name)
    return (topic_name, body)


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue], tuple[str, str]]] = {
    "admin.activity_log_event.created": get_admin_event_log_event_created_message,
    "admin.added_to_workspace": partial(
        get_admin_action_message, "added to", ADMIN_WORKSPACE_MESSAGE
    ),
    "admin.away_mode_updated": get_admin_away_mode_updated_message,
    "admin.logged_in": partial(get_admin_action_message, "logged in", ADMIN_LOGIN_LOGOUT),
    "admin.logged_out": partial(get_admin_action_message, "logged out", ADMIN_LOGIN_LOGOUT),
    "admin.removed_from_workspace": partial(
        get_admin_action_message, "removed from", ADMIN_WORKSPACE_MESSAGE
    ),
    "ping": get_ping_message,
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
    separate_topics_for_each_entity: Json[bool] = False,
) -> HttpResponse:
    event_type = payload["topic"].tame(check_string)

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name, body = handler(payload)
    if not separate_topics_for_each_entity:
        topic_name = topic_name.split(":")[0]
    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

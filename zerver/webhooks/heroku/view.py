from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ENTITY_TRIGGERED_MESSAGE = "{entity} was triggered by {actor}."
ENTITY_UPDATED_MESSAGE = "The {entity} triggered by {actor} {status}."
URL = "[{name}]({url})"
ENTITY_VERSION = "{entity}(v{version})"

USER_VISIBLE_STATUSES = [
    "pending",
    "succeeded",
    "failed",
]

IGNORED_ENTITIES = [
    "addon-attachment",
    "addon",
    "app",
    "collaborator",
    "domain",
    "dyno",
    "formation",
    "sni-endpoint",
]


def get_common_data(payload: WildValue, entity: str) -> tuple[str, str, str]:
    actor = payload["actor"]["email"].tame(check_string)
    app = payload["data"]["app"]["name"].tame(check_string)
    entity_url = payload["data"]["output_stream_url"].tame(check_none_or(check_string))
    if entity_url:
        display_entity = URL.format(name=entity, url=entity_url)
    else:
        display_entity = entity
    return (actor, app, display_entity)


def get_entity_created_message(payload: WildValue, entity: str) -> tuple[str, str]:
    if entity == "release":
        version = payload["data"]["version"].tame(check_int)
        entity = ENTITY_VERSION.format(entity=entity, version=version)

    actor, app, display_entity = get_common_data(payload, entity)
    body = ENTITY_TRIGGERED_MESSAGE.format(entity=display_entity, actor=actor)
    return (app, body)


def get_entity_update_message(payload: WildValue, entity: str) -> tuple[str, str]:
    if entity == "release":
        version = payload["data"]["version"].tame(check_int)
        entity = ENTITY_VERSION.format(entity=entity, version=version)

    actor, app, display_entity = get_common_data(payload, entity)
    status = payload["data"]["status"].tame(check_string)
    body = ENTITY_UPDATED_MESSAGE.format(entity=display_entity, actor=actor, status=status)
    return (app, body)


def should_ignore_event(entity: str, event_type: str, status: str, payload: WildValue) -> bool:
    if entity in IGNORED_ENTITIES:
        return True  # nocoverage

    if status not in USER_VISIBLE_STATUSES:
        return True  # nocoverage

    if (
        event_type == "release.update"
        and status == "succeeded"
        and not payload["data"]["current"].tame(check_bool)
    ):
        return True  # nocoverage

    return False


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue, str], tuple[str, str]]] = {
    "build.create": get_entity_created_message,
    "build.update": get_entity_update_message,
    "release.create": get_entity_created_message,
    "release.update": get_entity_update_message,
}


ALL_EVENT_TYPES = list(EVENT_TO_FUNCTION_MAPPER.keys())


@webhook_view("Heroku", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_heroku_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    only_failed_events: Json[bool] = False,
) -> HttpResponse:
    entity = payload["resource"].tame(check_string)
    event = payload["action"].tame(check_string)
    event_type = f"{entity}.{event}"
    status = payload["data"]["status"].tame(check_string)

    if only_failed_events and status != "failed":
        return json_success(request)

    if should_ignore_event(entity, event_type, status, payload):
        return json_success(request)  # nocoverage

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name, body = handler(payload, entity)

    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)

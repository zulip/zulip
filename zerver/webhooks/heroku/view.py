from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ENTITY_CREATED_MESSAGE = "{actor} triggered a {entity}."
ENTITY_UPDATED_MESSAGE = "The {entity} triggered by {actor} **{status}**."
ENTITY_VERSION = "{entity}(v{version})"

# The events here are ignored not because they are noisy.
# But we do not have accurate fixtures for them.
# The fixtures documented in https://devcenter.heroku.com/articles/webhook-events
# have been reported to drift from actual payloads.
# Heroku does not provide a free trial account.
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


def get_message(payload: WildValue, entity: str) -> tuple[str, str]:
    data = payload["data"]
    actor = payload["actor"]["email"].tame(check_string)
    app = data["app"]["name"].tame(check_string)

    entity_url = data["output_stream_url"].tame(check_none_or(check_string))
    display_entity = f"[{entity}]({entity_url})" if entity_url else entity

    if entity == "release":
        version = data["version"].tame(check_int)
        display_entity = ENTITY_VERSION.format(entity=display_entity, version=version)
        description = data["description"].tame(check_string)
        display_entity = f"{display_entity}: {description}"

    action = payload["action"].tame(check_string)

    if action == "update":
        status = data["status"].tame(check_string)
        body = ENTITY_UPDATED_MESSAGE.format(entity=display_entity, actor=actor, status=status)
    else:
        body = ENTITY_CREATED_MESSAGE.format(entity=display_entity, actor=actor)

    return (app, body)


def should_ignore_event(entity: str, event_type: str, status: str, payload: WildValue) -> bool:
    if entity in IGNORED_ENTITIES:
        return True  # nocoverage

    # Ignore release phase update events, for now, to avoid duplicate notifications.
    # https://devcenter.heroku.com/articles/release-phase
    # 1. Release started: action="create" data.status="pending" data.current=false
    # 2. Release phase(s) finished: action="update" data.status="succeeded" data.current=false
    # 3. Release live: action="update" data.status="succeeded" data.current=true
    if (
        event_type == "release.update"
        and status in {"succeeded", "failed"}
        and not payload["data"]["current"].tame(check_bool)
    ):
        return True

    return False


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue, str], tuple[str, str]]] = {
    "build.create": get_message,
    "build.update": get_message,
    "release.create": get_message,
    "release.update": get_message,
}


ALL_EVENT_TYPES = list(EVENT_TO_FUNCTION_MAPPER.keys())


@webhook_view("Heroku", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_heroku_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    entity = payload["resource"].tame(check_string)
    event = payload["action"].tame(check_string)
    event_type = f"{entity}.{event}"
    status = payload["data"]["status"].tame(check_string)

    if should_ignore_event(entity, event_type, status, payload):
        return json_success(request)

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name, body = handler(payload, entity)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

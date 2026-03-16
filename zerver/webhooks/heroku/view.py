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


def get_body(payload: WildValue, entity: str) -> str:
    data = payload["data"]
    actor = payload["actor"]["email"].tame(check_string)

    entity_url = data["output_stream_url"].tame(check_none_or(check_string))
    display_entity = f"[{entity}]({entity_url})" if entity_url else entity

    if entity == "release":
        version = data["version"].tame(check_int)
        description = data["description"].tame(check_string)
        display_entity = f"{display_entity}(v{version}): {description}"

    action = payload["action"].tame(check_string)
    status = data["status"].tame(check_string)

    template = ENTITY_UPDATED_MESSAGE if action == "update" else ENTITY_CREATED_MESSAGE
    body = template.format(entity=display_entity, actor=actor, status=status)

    return body


def should_ignore_event(entity: str, event_type: str, payload: WildValue) -> bool:
    if entity in IGNORED_ENTITIES:
        return True

    # Ignore release phase update events, for now, to avoid duplicate notifications.
    # https://devcenter.heroku.com/articles/release-phase
    # 1. Release started: action="create" data.status="pending" data.current=false
    # 2. Release phase(s) finished: action="update" data.status="succeeded" data.current=false
    # 3. Release live: action="update" data.status="succeeded" data.current=true
    status = payload["data"]["status"].tame(check_string)
    if (
        event_type == "release.update"
        and status in {"succeeded", "failed"}
        and not payload["data"]["current"].tame(check_bool)
    ):
        return True

    return False


ALL_EVENT_TYPES = ["build.create", "build.update", "release.create", "release.update"]


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

    if should_ignore_event(entity, event_type, payload):
        return json_success(request)

    if event_type not in ALL_EVENT_TYPES:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name = payload["data"]["app"]["name"].tame(check_string)
    body = get_body(payload, entity)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

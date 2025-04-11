from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def get_build_event_body(payload: WildValue, actor: str, action: str, resource: str) -> str:
    output_stream_url = payload["data"]["output_stream_url"].tame(check_string)
    resource_label = format_resource_label(resource, action, output_stream_url)
    status = payload["data"]["status"].tame(check_string)

    if action == "created":
        return f"{actor} {action} {resource_label}."
    return f"{resource_label} {status}."


def get_release_event_body(payload: WildValue, actor: str, action: str, resource: str) -> str:
    output_stream_url = (
        payload["data"]["output_stream_url"].tame(check_string)
        if payload["data"]["output_stream_url"]
        else ""
    )
    description = payload["data"]["description"].tame(check_string)
    version = payload["data"]["version"].tame(check_int)
    resource_label = format_resource_label(resource + f"(v{version})", action, output_stream_url)
    status = payload["data"]["status"].tame(check_string)

    if action == "created":
        return f"{actor} {action} {resource_label}: {description}."
    return f"{resource_label} {status}."


EVENT_FUNCTION_MAPPER: dict[str, Callable[[WildValue, str, str, str], str]] = {
    "build": get_build_event_body,
    "release": get_release_event_body,
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


def format_resource_label(resource: str, action: str, url: str = "") -> str:
    if url:
        resource = f"[{resource}]({url})"
    if action == "created":
        return f"a new {resource}"
    return f"The {resource}"


@webhook_view("Heroku", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_heroku_webhook(
    request: HttpRequest, user_profile: UserProfile, *, payload: JsonBodyPayload[WildValue]
) -> HttpResponse:
    action: str = payload["action"].tame(check_string)
    resource: str = payload["resource"].tame(check_string)
    actor: str = payload["actor"]["email"].tame(check_string)

    formatted_action: str = action + "d"
    topic: str = payload["data"]["app"]["name"].tame(check_string)  # Heroku App name
    message: str
    message_body_fucntion = EVENT_FUNCTION_MAPPER.get(resource)
    if message_body_fucntion is None:
        raise UnsupportedWebhookEventTypeError(resource)

    message = message_body_fucntion(payload, actor, formatted_action, resource)
    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)

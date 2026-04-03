# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import return_success_on_head_request, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string, check_url
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

from .project_events import SUPPORTED_PROJECT_EVENTS, process_project_action
from .task_events import IGNORED_TASK_EVENTS, SUPPORTED_TASK_EVENTS, process_task_action

ALL_SUPPORTED_EVENTS = SUPPORTED_TASK_EVENTS + SUPPORTED_PROJECT_EVENTS


@webhook_view("Vikunja", all_event_types=ALL_SUPPORTED_EVENTS)
@return_success_on_head_request
@typed_endpoint
def api_vikunja_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    host_url: str,
    only_events: Json[list[str]] | None = None,
) -> HttpResponse:
    host = check_url("host_url", host_url).rstrip("/")

    event_name = payload["event_name"].tame(check_string)

    if only_events is not None and event_name not in only_events:
        return json_success(request)

    message = get_topic_and_body(host, payload, event_name)
    if message is None:
        return json_success(request)
    else:
        topic, body = message

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)


def get_topic_and_body(host: str, payload: WildValue, event_name: str) -> tuple[str, str] | None:
    if event_name in SUPPORTED_TASK_EVENTS:
        return process_task_action(host, payload, event_name)
    if event_name in IGNORED_TASK_EVENTS:
        return None
    if event_name in SUPPORTED_PROJECT_EVENTS:
        return process_project_action(host, payload, event_name)

    raise UnsupportedWebhookEventTypeError(event_name)

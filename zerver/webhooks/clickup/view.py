from collections.abc import Callable
from typing import Any

import requests
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.bot_config import ConfigError, get_bot_config
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_service_api_data
from zerver.models import UserProfile

CLICKUP_WEB_BASE_URL = "https://app.clickup.com"
TASK_TEMPLATE = "{author_name} {action} [{name}]({url})."
DASHBOARD_URLS: dict[str, str] = {
    "task": CLICKUP_WEB_BASE_URL + "/t/{team_id}/{entity_id}",
}


def get_event_name(event_type: str) -> str:
    words = []
    start_index = 0

    for i, char in enumerate(event_type):
        if char.isupper() and i > 0:
            words.append(event_type[start_index:i])
            start_index = i

    words.append(event_type[start_index:])

    return " ".join(words).title()


def get_clickup_api_data(id: str, entity: str, token: str) -> dict[str, Any] | None:
    if not token:
        return None

    url = f"https://api.clickup.com/api/v2/{entity}/{id}"
    headers = {"Authorization": token, "accept": "application/json"}

    try:
        response = get_service_api_data(url, integration_name="ClickUp", headers=headers)
        return response.json()

    except (requests.RequestException, ValueError):
        return None


def get_task_message(action: str, payload: WildValue, token: str) -> tuple[str, str]:
    task_id = payload["task_id"].tame(check_string)
    if action == "deleted":
        return ("Task", "A task was deleted.")

    task_data = get_clickup_api_data(task_id, "task", token)
    task_name = task_data["name"] if task_data else "Task"
    topic_name = f"Task: {task_name}" if task_data else task_name
    team_id = payload["team_id"].tame(check_string)
    body = TASK_TEMPLATE.format(
        name=task_name,
        author_name=payload["history_items"][0]["user"]["username"].tame(check_string),
        url=DASHBOARD_URLS["task"].format(team_id=team_id, entity_id=task_id),
        action=action.lower(),
    )

    return (topic_name, body)


# ClickUp emits granular per-field events (e.g. taskStatusUpdated) in addition
# to the generic taskUpdated event.
IGNORED_EVENTS = [
    "taskStatusUpdated",
    "taskPriorityUpdated",
    "taskAssigneeUpdated",
    "taskDueDateUpdated",
    "taskCommentPosted",
    "taskTimeEstimateUpdated",
    "taskTimeTrackedUpdated",
]


def should_ignore_event(event_type: str, payload: WildValue) -> bool:
    return event_type in IGNORED_EVENTS


ALL_EVENT_MAPPER: dict[str, Callable[[WildValue, str], tuple[str, str]]] = {
    "Task Created": partial(get_task_message, "created"),
    "Task Updated": partial(get_task_message, "updated"),
    "Task Deleted": partial(get_task_message, "deleted"),
}
ALL_EVENT_TYPES = list(ALL_EVENT_MAPPER.keys())


@webhook_view("ClickUp", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_clickup_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event_type = payload["event"].tame(check_string)
    if should_ignore_event(event_type, payload):
        return json_success(request)
    event_name = get_event_name(event_type)
    try:
        config = get_bot_config(user_profile)
        clickup_token = config.get("clickup_token", "")
    except ConfigError:
        clickup_token = ""
    handler = ALL_EVENT_MAPPER.get(event_name)
    if not handler:
        raise UnsupportedWebhookEventTypeError(event_name)
    topic_name, body = handler(payload, clickup_token)
    check_send_webhook_message(request, user_profile, topic_name, body, event_name)
    return json_success(request)

import logging
import re
from collections.abc import Callable
from typing import Any

import requests
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.bot_config import ConfigError, get_bot_config
from zerver.lib.exceptions import AnomalousWebhookPayloadError, UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_service_api_data
from zerver.models import UserProfile

logger = logging.getLogger(__name__)

CLICKUP_WEB_BASE_URL = "https://app.clickup.com"
TASK_TEMPLATE = "{author_name} {action} [{name}]({url})."
COMMON_MESSAGE_TEMPLATE = "[{name}]({url}) was {action}."
DASHBOARD_URLS: dict[str, str] = {
    "task": CLICKUP_WEB_BASE_URL + "/t/{team_id}/{entity_id}",
    "space": CLICKUP_WEB_BASE_URL + "/{team_id}/v/s/{entity_id}",
    "folder": CLICKUP_WEB_BASE_URL + "/{team_id}/v/o/f/{entity_id}",
}


def get_event_name(event_type: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", event_type).title()


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
        return (f"Task: {task_id}", "A task was deleted.")

    task_data = get_clickup_api_data(task_id, "task", token)
    task_name = task_data["name"] if task_data else "Task"
    topic_name = f"Task: {task_name if task_data else task_id}"
    team_id = payload["team_id"].tame(check_string)
    body = TASK_TEMPLATE.format(
        name=task_name,
        author_name=payload["history_items"][0]["user"]["username"].tame(check_string),
        url=DASHBOARD_URLS["task"].format(team_id=team_id, entity_id=task_id),
        action=action,
    )

    return (topic_name, body)


def get_event_message(entity: str, action: str, payload: WildValue, token: str) -> tuple[str, str]:
    entity_id = payload[f"{entity}_id"].tame(check_string)

    if action == "deleted":
        return (f"{entity.title()}: {entity_id}", f"A {entity} was deleted.")

    entity_data = get_clickup_api_data(entity_id, entity, token)
    entity_name = entity_data["name"] if entity_data else entity.title()
    topic_name = f"{entity.title()}: {entity_name if entity_data else entity_id}"
    team_id = payload["team_id"].tame(check_string)

    body = COMMON_MESSAGE_TEMPLATE.format(
        name=entity_name,
        url=DASHBOARD_URLS[entity].format(team_id=team_id, entity_id=entity_id),
        action=action,
    )

    return (topic_name, body)


# ClickUp emits granular per-field events in addition
# to the generic taskUpdated event.
IGNORED_EVENTS = [
    "taskStatusUpdated",
    "taskPriorityUpdated",
    "taskAssigneeUpdated",
    "taskDueDateUpdated",
    "taskCommentPosted",
    "taskCommentUpdated",
    "taskTimeEstimateUpdated",
    "taskTimeTrackedUpdated",
    "taskTagUpdated",
    "taskMoved",
]


def should_ignore_event(event_type: str) -> bool:
    return event_type in IGNORED_EVENTS


ALL_EVENT_MAPPER: dict[str, Callable[[WildValue, str], tuple[str, str]]] = {
    "Task Created": partial(get_task_message, "created"),
    "Task Updated": partial(get_task_message, "updated"),
    "Task Deleted": partial(get_task_message, "deleted"),
    "Space Created": partial(get_event_message, "space", "created"),
    "Space Updated": partial(get_event_message, "space", "updated"),
    "Space Deleted": partial(get_event_message, "space", "deleted"),
    "Folder Created": partial(get_event_message, "folder", "created"),
    "Folder Updated": partial(get_event_message, "folder", "updated"),
    "Folder Deleted": partial(get_event_message, "folder", "deleted"),
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
    event_type = payload.get("event").tame(check_none_or(check_string))
    if event_type is None:
        raise AnomalousWebhookPayloadError
    if should_ignore_event(event_type):
        return json_success(request)
    event_name = get_event_name(event_type)
    try:
        config = get_bot_config(user_profile)
        clickup_token = config.get("clickup_token", "")
    except ConfigError:
        clickup_token = ""
    if not clickup_token:
        logger.warning(
            "ClickUp webhook for bot %s has no configured API token;"
            " entity names can't be fetched.",
            user_profile.full_name,
        )
    handler = ALL_EVENT_MAPPER.get(event_name)
    if not handler:
        raise UnsupportedWebhookEventTypeError(event_name)
    topic_name, body = handler(payload, clickup_token)
    check_send_webhook_message(request, user_profile, topic_name, body, event_name)
    return json_success(request)

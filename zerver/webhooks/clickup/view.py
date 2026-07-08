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
from zerver.lib.timestamp import datetime_to_global_time, timestamp_to_datetime
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_service_api_data
from zerver.models import UserProfile

logger = logging.getLogger(__name__)

CLICKUP_WEB_BASE_URL = "https://app.clickup.com"
TASK_TEMPLATE = "{author_name} {action} [{name}]({url}){extension}"
COMMON_MESSAGE_TEMPLATE = "[{name}]({url}) was {action}."
DASHBOARD_URLS: dict[str, str] = {
    "task": CLICKUP_WEB_BASE_URL + "/t/{team_id}/{entity_id}",
    "space": CLICKUP_WEB_BASE_URL + "/{team_id}/v/s/{entity_id}",
    "folder": CLICKUP_WEB_BASE_URL + "/{team_id}/v/o/f/{entity_id}",
    "goal": CLICKUP_WEB_BASE_URL + "/{team_id}/goals/{entity_id}",
    "list": CLICKUP_WEB_BASE_URL + "/{team_id}/v/l/li/{entity_id}",
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


def get_date_and_time(timestamp: str) -> str:
    return datetime_to_global_time(timestamp_to_datetime(int(timestamp) / 1000))


def duration_pretty(duration: int) -> str:
    if duration < 60:
        return f"{duration} {'sec' if duration == 1 else 'secs'}"
    total_minutes = (duration + 30) // 60
    hours, minutes = divmod(total_minutes, 60)
    hour_word = "hr" if hours == 1 else "hrs"
    minute_word = "min" if minutes == 1 else "mins"
    if hours > 0 and minutes > 0:
        return f"{hours} {hour_word} {minutes} {minute_word}"
    if hours > 0:
        return f"{hours} {hour_word}"
    return f"{minutes} {minute_word}"


def get_task_update_message(payload: WildValue) -> tuple[str, str]:
    # A due date change includes more than 1 history_item.
    history_item = next(
        (
            item
            for item in payload["history_items"]
            if item["field"].tame(check_string) == "due_date"
        ),
        payload["history_items"][0],
    )
    field = history_item["field"].tame(check_string)
    if not (after := history_item["after"]) and field in (
        "priority",
        "due_date",
        "start_date",
        "time_estimate",
    ):
        return (f"cleared the {field.replace('_', ' ')} of", ".")

    match field:
        case "status" | "priority":
            value = after[field].tame(check_string)
            return (f"updated the {field} of", f" to {value}.")
        case "due_date" | "start_date":
            return (
                f"updated the {field.replace('_', ' ')} of",
                f" to {get_date_and_time(after.tame(check_string))}.",
            )
        case "time_estimate":
            estimate = history_item["data"]["time_estimate_string"].tame(check_string).strip()
            return ("updated the time estimate of", f" to {estimate}.")
        case "time_spent":
            total_time_ms = int(history_item["data"]["total_time"].tame(check_string))
            return (f"tracked {duration_pretty(total_time_ms // 1000)} on", ".")
        case "assignee_add":
            assignee = after["username"].tame(check_string)
            return ("assigned", f" to {assignee}.")
        case "assignee_rem":
            unassignee = history_item["before"]["username"].tame(check_string)
            return (f"unassigned {unassignee} from", ".")
        case "custom_field":
            custom_field = history_item["custom_field"]
            name = custom_field["name"].tame(check_string)
            if not after:
                return (f"cleared the {name} of", ".")
            value = after.tame(check_string)
            if custom_field["type"].tame(check_string) == "date":
                value = get_date_and_time(value)
            return (f"updated the {name} of", f" to {value}.")
        case "attachments":
            attachment = history_item["attachments"][0]
            title = attachment["title"].tame(check_string)
            url = attachment["url"].tame(check_string)
            return (f"added [{title}]({url}) to", ".")
        case "checklist_items_added":
            checklist = history_item["checklist"]["name"].tame(check_string)
            item = history_item["checklist_items"][0]["name"].tame(check_string)
            return (f"added {item} to the {checklist} checklist on", ".")
        case "checklist_item_resolved":
            item = history_item["checklist_item"]["name"].tame(check_string)
            checklist = history_item["checklist"]["name"].tame(check_string)
            return (f"checked off {item} in the {checklist} checklist on", ".")
        case "comment":
            action = (
                "replied to a comment on" if history_item.get("parent_comment") else "commented on"
            )

            if not (text := history_item["comment"]["text_content"].tame(check_string).strip()):
                return (action, ".")
            return (action, f":\n``` quote\n{text}\n```")
        case "section_moved":
            source = history_item["before"]["name"].tame(check_string)
            destination = history_item["after"]["name"].tame(check_string)
            return ("moved", f" from {source} to {destination}.")
        case _:
            return ("updated", ".")


def get_task_message(action: str, payload: WildValue, token: str) -> tuple[str, str]:
    task_id = payload["task_id"].tame(check_string)
    if action == "deleted":
        return (f"Task: {task_id}", "A task was deleted.")

    task_data = get_clickup_api_data(task_id, "task", token)
    task_name = task_data["name"] if task_data else "Task"
    topic_name = f"Task: {task_name if task_data else task_id}"
    team_id = payload["team_id"].tame(check_string)

    extension = "."
    if action == "updated":
        action, extension = get_task_update_message(payload)

    body = TASK_TEMPLATE.format(
        name=task_name,
        author_name=payload["history_items"][0]["user"]["username"].tame(check_string),
        url=DASHBOARD_URLS["task"].format(team_id=team_id, entity_id=task_id),
        action=action,
        extension=extension,
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


def get_goal_and_key_result_message(
    entity: str, action: str, payload: WildValue, token: str
) -> tuple[str, str]:
    goal_id = payload["goal_id"].tame(check_string)
    if action == "deleted":
        return (f"Goal: {goal_id}", f"A {entity} was deleted.")

    # Key results have no dedicated endpoint, so we fetch the parent goal for
    # its name and dashboard URL.
    goal_data = get_clickup_api_data(goal_id, "goal", token)
    goal = goal_data["goal"] if goal_data else None
    goal_name = goal["name"] if goal else "Goal"
    topic_name = f"Goal: {goal_name if goal else goal_id}"
    team_id = payload["team_id"].tame(check_string)

    # Goals are linked by their pretty_id, which is only in the API response.
    url = (
        DASHBOARD_URLS["goal"].format(team_id=team_id, entity_id=goal["pretty_id"])
        if goal
        else f"{CLICKUP_WEB_BASE_URL}/{team_id}/goals"
    )
    if entity == "goal":
        name = goal_name
    else:
        # Key result events carry only its id; look up the name in the goal.
        name = "Key result"
        if goal:
            key_result_id = payload["key_result_id"].tame(check_string)
            name = next(
                (kr["name"] for kr in goal["key_results"] if kr["id"] == key_result_id),
                "Key result",
            )
    body = COMMON_MESSAGE_TEMPLATE.format(name=name, url=url, action=action)

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
    "List Created": partial(get_event_message, "list", "created"),
    "List Updated": partial(get_event_message, "list", "updated"),
    "List Deleted": partial(get_event_message, "list", "deleted"),
    "Goal Created": partial(get_goal_and_key_result_message, "goal", "created"),
    "Goal Updated": partial(get_goal_and_key_result_message, "goal", "updated"),
    "Goal Deleted": partial(get_goal_and_key_result_message, "goal", "deleted"),
    "Key Result Created": partial(get_goal_and_key_result_message, "key result", "created"),
    "Key Result Updated": partial(get_goal_and_key_result_message, "key result", "updated"),
    "Key Result Deleted": partial(get_goal_and_key_result_message, "key result", "deleted"),
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

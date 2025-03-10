# Webhooks for external integrations.
from typing import Any
from urllib.parse import urljoin

import requests
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, unix_milliseconds_to_timestamp
from zerver.models import UserProfile

SIMPLE_FIELDS = ["priority", "status"]

SPAMMY_FIELDS = ["tag", "tag_removed", "assignee_rem"]

MESSAGE_WRAPPER = "\n~~~ quote\n {icon} {content}\n~~~\n"

EVENT_NAME_TEMPLATE: str = "**[{event_item_type}: {event_item_name}]({item_url})**"


def split_camel_case_string(string: str) -> list[str]:
    words = []
    start_index = 0

    for i, char in enumerate(string):
        if char.isupper() and i > 0:
            words.append(string[start_index:i])
            start_index = i

    words.append(string[start_index:])

    return words


def parse_event_code(event_code: str) -> tuple[str, str]:
    """
    Turns string like "taskUpdated" into ("task", "Updated")
    """
    data_list = split_camel_case_string(event_code)
    if len(data_list) != 2:
        raise UnsupportedWebhookEventTypeError(event_code)
    return data_list[0], data_list[1]


def generate_created_event_message(item_data: dict[str, Any], event_item_type: str) -> str:
    body = "\n:new: " + EVENT_NAME_TEMPLATE + " has been created in your ClickUp space!"
    creator_data = item_data.get("creator")
    if isinstance(creator_data, dict) and "username" in creator_data:
        # Some payload only doesn't provide users data.
        creator_name = creator_data["username"]
        body += f"\n - Created by: **{creator_name}**"
    return body.format(
        event_item_type=event_item_type.title(),
        event_item_name=item_data["name"],
        item_url=item_data["url"],
    )


def body_message_for_simple_fields(
    history_dict: WildValue, event_item_type: str, updated_field: str
) -> str:
    # The value of "before"/"after" for these payloads maybe a dict or a bool
    old_value = (
        history_dict.get("before").get(updated_field).tame(check_string)
        if history_dict.get("before")
        else None
    )
    new_value = (
        history_dict.get("after").get(updated_field).tame(check_string)
        if history_dict.get("after")
        else None
    )
    return MESSAGE_WRAPPER.format(
        icon=":note:",
        content=f"Updated {event_item_type} {updated_field} from **{old_value}** to **{new_value}**",
    )


def body_message_for_special_fields(history_dict: WildValue, updated_field: str) -> str:
    event_details = history_dict.get("data", {})
    icon: str
    content: str
    if updated_field == "name":
        old_value = history_dict["before"].tame(check_none_or(check_string))
        new_value = history_dict["after"].tame(check_none_or(check_string))
        icon = ":pencil:"
        content = f"Renamed from **{old_value}** to **{new_value}**"
    elif updated_field == "assignee_add":
        new_value = history_dict["after"]["username"].tame(check_string)
        icon = ":silhouette:"
        content = f"Now assigned to **{new_value}**"
    elif updated_field == "comment":
        event_user = history_dict["user"]["username"].tame(check_string)
        icon = ":speaking_head:"
        content = f"Commented by **{event_user}**"
    elif updated_field == "due_date":
        raw_old_due_date = history_dict.get("before").tame(check_none_or(check_string))
        old_due_date = (
            unix_milliseconds_to_timestamp(float(raw_old_due_date), "ClickUp").strftime("%Y-%m-%d")
            if raw_old_due_date
            else None
        )
        raw_new_due_date = history_dict.get("after").tame(check_none_or(check_string))
        new_due_date = (
            unix_milliseconds_to_timestamp(float(raw_new_due_date), "ClickUp").strftime("%Y-%m-%d")
            if raw_new_due_date
            else None
        )
        icon = ":spiral_calendar:"
        content = f"Due date updated from <time: {old_due_date}> to <time: {new_due_date}>"
    elif updated_field == "section_moved":
        old_value = history_dict["before"]["name"].tame(check_none_or(check_string))
        new_value = history_dict["after"]["name"].tame(check_none_or(check_string))
        icon = ":folder:"
        content = f"Moved from **{old_value}** to **{new_value}**"
    elif updated_field == "time_spent":
        raw_time_spent = event_details.get("total_time").tame(check_none_or(check_string))
        new_time_spent = (
            unix_milliseconds_to_timestamp(float(raw_time_spent), "ClickUp").strftime("%H:%M:%S")
            if raw_time_spent
            else None
        )
        icon = ":stopwatch:"
        content = f"Time spent changed to **{new_time_spent}**"
    elif updated_field == "time_estimate":
        old_value = event_details["old_time_estimate_string"].tame(check_none_or(check_string))
        new_value = event_details["time_estimate_string"].tame(check_none_or(check_string))
        event_user = history_dict["user"]["username"].tame(check_string)
        icon = ":ruler:"
        content = (
            f"Time estimate changed from **{old_value}** to **{new_value}** by **{event_user}**"
        )
    else:
        raise UnsupportedWebhookEventTypeError(updated_field)
    return MESSAGE_WRAPPER.format(icon=icon, content=content)


def generate_updated_event_message(
    item_data: dict[str, Any],
    event_item_type: str,
    payload: WildValue,
) -> str:
    body = "\n" + EVENT_NAME_TEMPLATE + " has been updated!"
    history_items = payload.get("history_items", [])

    for history_dict in history_items:
        updated_field = history_dict["field"].tame(check_string)
        if updated_field in SPAMMY_FIELDS:
            continue
        elif updated_field in SIMPLE_FIELDS:
            body += body_message_for_simple_fields(history_dict, event_item_type, updated_field)
        else:
            body += body_message_for_special_fields(history_dict, updated_field)

    return body.format(
        event_item_type=event_item_type.title(),
        event_item_name=item_data["name"],
        item_url=item_data["url"],
    )


def get_clickup_api_data(clickup_api_path: str, **kwargs: Any) -> dict[str, Any]:
    if not kwargs.get("token"):
        raise AssertionError("ClickUp API 'token' missing in kwargs")
    token = kwargs.pop("token")

    base_url = "https://api.clickup.com/api/v2/"
    api_endpoint = urljoin(base_url, clickup_api_path)
    response = requests.get(
        api_endpoint,
        headers={
            "Content-Type": "application/json",
            "Authorization": token,
        },
        params=kwargs,
    )
    if response.status_code != requests.codes.ok:
        raise Exception(f"HTTP error accessing the ClickUp API. Error: {response.status_code}")
    return response.json()


def get_item_data(
    event_item_type: str, api_key: str, payload: WildValue, team_id: str
) -> dict[str, Any]:
    item_data: dict[str, Any] = {}

    if event_item_type not in ["task", "list", "folder", "space", "goal"]:
        raise UnsupportedWebhookEventTypeError(event_item_type)

    item_id_key = f"{event_item_type}_id"
    clickup_api_path = f"{event_item_type}/{payload[item_id_key].tame(check_string)}"
    item_data = get_clickup_api_data(clickup_api_path, token=api_key)

    if event_item_type == "goal":
        # The data for "goal" is nested one level deeper.
        item_data = item_data["goal"]

    item_data["url"] = item_data.get("pretty_url", f"https://app.clickup.com/{team_id}/home")

    return item_data


@webhook_view("ClickUp")
@typed_endpoint
def api_clickup_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    clickup_api_key: str,
    team_id: str,
) -> HttpResponse:
    event_code = payload["event"].tame(check_string)
    event_item_type, event_action = parse_event_code(event_code=event_code)
    topic = "ClickUp Notification"

    if event_action == "Deleted":
        body = (
            f"\n:trash_can: A {event_item_type.title()} has been deleted from your ClickUp space!"
        )
        check_send_webhook_message(request, user_profile, topic, body)
        return json_success(request)

    item_data = get_item_data(
        event_item_type,
        clickup_api_key,
        payload,
        team_id,
    )

    if event_action == "Created":
        body = generate_created_event_message(item_data, event_item_type)
    elif event_action == "Updated":
        body = generate_updated_event_message(item_data, event_item_type, payload)
    else:
        raise UnsupportedWebhookEventTypeError(event_code)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)

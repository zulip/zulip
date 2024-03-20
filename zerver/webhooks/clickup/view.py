# Webhooks for external integrations.
import logging
import re
from typing import Any, Dict, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, unix_milliseconds_to_timestamp
from zerver.models import UserProfile
from zerver.webhooks.clickup import (
    EventAcion,
    EventItemType,
    SimpleFields,
    SpammyFields,
    SpecialFields,
)

from .api_endpoints import get_folder, get_goal, get_list, get_space, get_task

logger = logging.getLogger(__name__)

EVENT_NAME_TEMPLATE: str = "**[{event_item_type}: {event_item_name}]({item_url})**"


@webhook_view("ClickUp")
@typed_endpoint
@has_request_variables
def api_clickup_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    clickup_api_key: str = REQ(),
    team_id: str = REQ(),
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    topic, body = topic_and_body(payload, clickup_api_key, team_id)
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)


def topic_and_body(payload: WildValue, clickup_api_key: str, team_id: str) -> Tuple[str, str]:
    event_code = payload["event"].tame(check_string)
    topic = "ClickUp Notification"

    event_item_type, event_action = parse_event_code(event_code=event_code)

    if event_action == EventAcion.DELETED.value:
        body = generate_delete_event_message(event_item_type=event_item_type)
        return topic, body

    item_data = get_item_data(
        event_item_type=event_item_type,
        api_key=clickup_api_key,
        payload=payload,
        team_id=team_id,
    )
    if event_action == EventAcion.CREATED.value:
        body = generate_create_event_message(item_data=item_data, event_item_type=event_item_type)

    elif event_action == EventAcion.UPDATED.value:
        body = generate_updated_event_message(
            item_data=item_data, payload=payload, event_item_type=event_item_type
        )
    else:
        raise UnsupportedWebhookEventTypeError(event_code)

    return topic, body


def parse_event_code(event_code: str) -> Tuple[str, str]:
    item_type_pattern: str = "|".join(EventItemType.as_list())
    action_pattern: str = "|".join(EventAcion.as_list())
    pattern = rf"(?P<item_type>({item_type_pattern}))(?P<event_action>({action_pattern}))"
    match = re.match(pattern, event_code)
    if match is None or match.group("item_type") is None or match.group("event_action") is None:
        raise UnsupportedWebhookEventTypeError(event_code)

    return match.group("item_type"), match.group("event_action")


def generate_create_event_message(item_data: Dict[str, Any], event_item_type: str) -> str:
    created_message = "\n:new: " + EVENT_NAME_TEMPLATE + " has been created in your ClickUp space!"
    if isinstance(item_data.get("creator"), dict) and item_data["creator"].get("username"):
        # some payload only provide creator id, not dict of usable data.
        created_message += "\n - Created by: **{event_user}**".format(
            event_user=item_data["creator"]["username"]
        )

    return created_message.format(
        event_item_type=event_item_type.title(),
        event_item_name=item_data["name"],
        item_url=item_data["url"],
    )


def generate_delete_event_message(event_item_type: str) -> str:
    return f"\n:trash_can: A {event_item_type.title()} has been deleted from your ClickUp space!"


def generate_updated_event_message(
    item_data: Dict[str, Any], payload: WildValue, event_item_type: str
) -> str:
    """
    Appends all the details of the updated fields to the message body.
    """
    body = "\n" + EVENT_NAME_TEMPLATE + " has been updated!"
    history_items = payload.get("history_items")

    if history_items:
        for history_data in history_items:
            updated_field = history_data["field"].tame(check_string)
            if updated_field in SpammyFields.as_list():
                # Updating these fields may trigger multiple identical notifications at a time.
                continue  # nocoverage
            elif updated_field in SimpleFields.as_list():
                body += body_message_for_simple_field(
                    history_data=history_data, event_item_type=event_item_type
                )
            elif updated_field in SpecialFields.as_list():
                body += body_message_for_special_field(history_data=history_data)
            else:
                raise UnsupportedWebhookEventTypeError(updated_field)

    return body.format(
        event_item_type=event_item_type.title(),
        event_item_name=item_data["name"],
        item_url=item_data["url"],
    )


def body_message_for_simple_field(history_data: WildValue, event_item_type: str) -> str:
    updated_field = history_data["field"].tame(check_string)
    old_value = (
        history_data.get("before").get(updated_field).tame(check_string)
        if history_data.get("before")
        else None
    )
    new_value = (
        history_data.get("after").get(updated_field).tame(check_string)
        if history_data.get("after")
        else None
    )
    return f"\n~~~ quote\n :note: Updated {event_item_type} {updated_field} from **{old_value}** to **{new_value}**\n~~~\n"


def body_message_for_special_field(history_data: WildValue) -> str:
    updated_field = history_data["field"].tame(check_string)
    if updated_field == SpecialFields.NAME.value:
        return (
            "\n~~~ quote\n :pencil: Renamed from **{old_value}** to **{new_value}**\n~~~\n"
        ).format(
            old_value=history_data["before"].tame(check_string),
            new_value=history_data["after"].tame(check_string),
        )

    elif updated_field == SpecialFields.ASSIGNEE.value:
        return ("\n~~~ quote\n :silhouette: Now assigned to **{new_value}**\n~~~\n").format(
            new_value=history_data["after"]["username"].tame(check_string)
        )

    elif updated_field == SpecialFields.COMMENT.value:
        return ("\n~~~ quote\n :speaking_head: Commented by **{event_user}**\n~~~\n").format(
            event_user=history_data["user"]["username"].tame(check_string)
        )

    elif updated_field == SpecialFields.DUE_DATE.value:
        old_value = (
            history_data.get("before").tame(check_string) if history_data.get("before") else None
        )
        old_due_date = (
            unix_milliseconds_to_timestamp(
                milliseconds=float(old_value), webhook="ClickUp"
            ).strftime("%Y-%m-%d")
            if old_value
            else None
        )
        new_value = (
            history_data.get("after").tame(check_string) if history_data.get("after") else None
        )
        new_due_date = (
            unix_milliseconds_to_timestamp(
                milliseconds=float(new_value), webhook="ClickUp"
            ).strftime("%Y-%m-%d")
            if new_value
            else None
        )
        return f"\n~~~ quote\n :spiral_calendar: Due date updated from **{old_due_date}** to **{new_due_date}**\n~~~\n"

    elif updated_field == SpecialFields.MOVED.value:
        raw_old_value = history_data.get("before", {}).get("name")
        old_value = raw_old_value.tame(check_string) if raw_old_value else None
        raw_new_value = history_data.get("after", {}).get("name")
        new_value = raw_new_value.tame(check_string) if raw_new_value else None
        return f"\n~~~ quote\n :folder: Moved from **{old_value}** to **{new_value}**\n~~~\n"

    elif updated_field == SpecialFields.TIME_SPENT.value:
        raw_time_spent = history_data.get("data", {}).get("total_time").tame(check_string)
        new_time_spent = (
            unix_milliseconds_to_timestamp(
                milliseconds=float(raw_time_spent), webhook="ClickUp"
            ).strftime("%H:%M:%S")
            if raw_time_spent
            else None
        )
        return f"\n~~~ quote\n :stopwatch: Time spent changed to **{new_time_spent}**\n~~~\n"
    elif updated_field == SpecialFields.TIME_ESTIMATE.value:
        raw_old_value = history_data.get("data", {}).get("old_time_estimate_string")
        old_value = raw_old_value.tame(check_string) if raw_old_value else None
        raw_new_value = history_data.get("data", {}).get("time_estimate_string")
        new_value = raw_new_value.tame(check_string) if raw_new_value else None
        raw_event_user = history_data.get("user", {}).get("username").tame(check_string)
        event_user = raw_event_user if raw_event_user else None
        return f"\n~~~ quote\n :ruler: Time estimate changed from **{old_value}** to **{new_value}** by **{event_user}**\n~~~\n"
    else:
        raise UnsupportedWebhookEventTypeError(updated_field)


def get_item_data(
    event_item_type: str, api_key: str, payload: WildValue, team_id: str
) -> Dict[str, Any]:
    item_data: Dict[str, Any] = {}
    if event_item_type == EventItemType.TASK.value:
        item_data = get_task(api_key=str(api_key), task_id=payload["task_id"].tame(check_string))
    elif event_item_type == EventItemType.LIST.value:
        item_data = get_list(api_key=api_key, list_id=payload["list_id"].tame(check_string))
    elif event_item_type == EventItemType.FOLDER.value:
        item_data = get_folder(api_key=api_key, folder_id=payload["folder_id"].tame(check_string))
    elif event_item_type == EventItemType.GOAL.value:
        goal_data: Dict[str, Any] = get_goal(
            api_key=api_key, goal_id=payload["goal_id"].tame(check_string)
        )
        item_data = goal_data.get(
            "goal", {}
        )  # in case of Goal payload, useful data are stored 1 level deeper
    elif event_item_type == EventItemType.SPACE.value:
        item_data = get_space(api_key=api_key, space_id=payload["space_id"].tame(check_string))
    else:
        raise UnsupportedWebhookEventTypeError(event_item_type)

    if item_data.get("pretty_url") and not item_data.get("url"):
        item_data["url"] = item_data["pretty_url"]
    if not item_data.get("url"):
        item_data["url"] = "https://app.clickup.com/" + team_id + "/home"
    return item_data

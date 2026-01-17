"""Taiga integration for Zulip.

Tips for notification output:

*Text formatting*: if there has been a change of a property, the new
value should always be in bold; otherwise the subject of US/task
should be in bold.
"""

from typing import TypedDict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


class EventType(TypedDict):
    type: str
    event: str
    values: dict[str, str | bool | None]


@webhook_view("Taiga")
@typed_endpoint
def api_taiga_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message: JsonBodyPayload[WildValue],
) -> HttpResponse:
    parsed_events = parse_message(message)
    content = "".join(sorted(generate_content(event) + "\n" for event in parsed_events))
    topic_name = "General"
    if message["data"].get("milestone") and "name" in message["data"]["milestone"]:
        topic_name = message["data"]["milestone"]["name"].tame(check_string)
    check_send_webhook_message(request, user_profile, topic_name, content)

    return json_success(request)


TEMPLATES = {
    "epic": {
        "create": "{user} created epic {subject}.",
        "set_assigned_to": "{user} assigned epic {subject} to {new}.",
        "unset_assigned_to": "{user} unassigned epic {subject}.",
        "changed_assigned_to": "{user} reassigned epic {subject} from {old} to {new}.",
        "blocked": "{user} blocked epic {subject}.",
        "unblocked": "{user} unblocked epic {subject}.",
        "changed_status": "{user} changed status of epic {subject} from {old} to {new}.",
        "renamed": "{user} renamed epic from **{old}** to **{new}**.",
        "description_diff": "{user} updated description of epic {subject}.",
        "commented": "{user} commented on epic {subject}.",
        "delete": "{user} deleted epic {subject}.",
    },
    "relateduserstory": {
        "create": (
            "{user} added a related user story {userstory_subject} to the epic {epic_subject}."
        ),
        "delete": (
            "{user} removed a related user story {userstory_subject} from the epic {epic_subject}."
        ),
    },
    "userstory": {
        "create": "{user} created user story {subject}.",
        "set_assigned_to": "{user} assigned user story {subject} to {new}.",
        "unset_assigned_to": "{user} unassigned user story {subject}.",
        "changed_assigned_to": "{user} reassigned user story {subject} from {old} to {new}.",
        "points": "{user} changed estimation of user story {subject}.",
        "blocked": "{user} blocked user story {subject}.",
        "unblocked": "{user} unblocked user story {subject}.",
        "set_milestone": "{user} added user story {subject} to sprint {new}.",
        "unset_milestone": "{user} removed user story {subject} from sprint {old}.",
        "changed_milestone": "{user} changed sprint of user story {subject} from {old} to {new}.",
        "changed_status": "{user} changed status of user story {subject} from {old} to {new}.",
        "closed": "{user} closed user story {subject}.",
        "reopened": "{user} reopened user story {subject}.",
        "renamed": "{user} renamed user story from {old} to **{new}**.",
        "description_diff": "{user} updated description of user story {subject}.",
        "commented": "{user} commented on user story {subject}.",
        "delete": "{user} deleted user story {subject}.",
        "due_date": "{user} changed due date of user story {subject} from {old} to {new}.",
        "set_due_date": "{user} set due date of user story {subject} to {new}.",
    },
    "milestone": {
        "create": "{user} created sprint {subject}.",
        "renamed": "{user} renamed sprint from {old} to **{new}**.",
        "estimated_start": "{user} changed estimated start of sprint {subject}"
        " from {old} to {new}.",
        "estimated_finish": "{user} changed estimated finish of sprint {subject}"
        " from {old} to {new}.",
        "set_estimated_start": "{user} changed estimated start of sprint {subject} to {new}.",
        "set_estimated_finish": "{user} set estimated finish of sprint {subject} to {new}.",
        "delete": "{user} deleted sprint {subject}.",
    },
    "task": {
        "create": "{user} created task {subject}.",
        "set_assigned_to": "{user} assigned task {subject} to {new}.",
        "unset_assigned_to": "{user} unassigned task {subject}.",
        "changed_assigned_to": "{user} reassigned task {subject} from {old} to {new}.",
        "blocked": "{user} blocked task {subject}.",
        "unblocked": "{user} unblocked task {subject}.",
        "changed_status": "{user} changed status of task {subject} from {old} to {new}.",
        "renamed": "{user} renamed task {old} to **{new}**.",
        "description_diff": "{user} updated description of task {subject}.",
        "set_milestone": "{user} added task {subject} to sprint {new}.",
        "commented": "{user} commented on task {subject}.",
        "delete": "{user} deleted task {subject}.",
        "changed_us": "{user} moved task {subject} from user story {old} to {new}.",
        "due_date": "{user} changed due date of task {subject} from {old} to {new}.",
        "set_due_date": "{user} set due date of task {subject} to {new}.",
    },
    "issue": {
        "create": "{user} created issue {subject}.",
        "set_assigned_to": "{user} assigned issue {subject} to {new}.",
        "unset_assigned_to": "{user} unassigned issue {subject}.",
        "changed_assigned_to": "{user} reassigned issue {subject} from {old} to {new}.",
        "set_milestone": "{user} added issue {subject} to sprint {new}.",
        "unset_milestone": "{user} detached issue {subject} from sprint {old}.",
        "changed_priority": "{user} changed priority of issue {subject} from {old} to {new}.",
        "changed_severity": "{user} changed severity of issue {subject} from {old} to {new}.",
        "changed_status": "{user} changed status of issue {subject} from {old} to {new}.",
        "changed_type": "{user} changed type of issue {subject} from {old} to {new}.",
        "renamed": "{user} renamed issue {old} to **{new}**.",
        "description_diff": "{user} updated description of issue {subject}.",
        "commented": "{user} commented on issue {subject}.",
        "delete": "{user} deleted issue {subject}.",
        "due_date": "{user} changed due date of issue {subject} from {old} to {new}.",
        "set_due_date": "{user} set due date of issue {subject} to {new}.",
        "blocked": "{user} blocked issue {subject}.",
        "unblocked": "{user} unblocked issue {subject}.",
    },
    "webhook_test": {
        "test": "{user} triggered a test of the Taiga integration.",
    },
}


def get_old_and_new_values(change_type: str, message: WildValue) -> tuple[str, str]:
    diff = message["change"]["diff"][change_type]
    old = diff.get("from").tame(check_none_or(check_string))
    new = diff.get("to").tame(check_none_or(check_string))
    return old or "", new or ""


def parse_comment(
    message: WildValue,
) -> EventType:
    return {
        "event": "commented",
        "type": message["type"].tame(check_string),
        "values": {
            "user": get_display_user(message),
            "subject": get_subject(message),
        },
    }


def parse_create_or_delete(
    message: WildValue,
) -> EventType:
    event_type = message["type"].tame(check_string)

    values: dict[str, str | bool | None] = {"user": get_display_user(message)}
    if event_type == "relateduserstory":
        values["epic_subject"] = get_subject(message, "epic")
        values["userstory_subject"] = get_subject(message, "user_story")
    else:
        values["subject"] = get_subject(message)

    return EventType(type=event_type, event=message["action"].tame(check_string), values=values)


def parse_change_event(change_type: str, message: WildValue) -> EventType | None:
    diff_data = message["change"]["diff"]
    values: dict[str, str | bool | None] = {
        "user": get_display_user(message),
        "subject": get_subject(message),
    }
    event_type: str | None

    match change_type:
        case "description_diff" | "points":
            event_type = change_type

        case "milestone" | "assigned_to" | "estimated_finish" | "estimated_start" | "due_date":
            old, new = get_old_and_new_values(change_type, message)
            if not old:
                event_type, values["new"] = f"set_{change_type}", new
            elif not new and change_type in ("milestone", "assigned_to"):
                event_type, values["old"] = f"unset_{change_type}", old
            elif old != new:
                event_type = (
                    change_type
                    if "date" in change_type or "estimated" in change_type
                    else f"changed_{change_type}"
                )
                values.update(old=old, new=new)
            else:
                return None

        case "is_blocked" | "is_closed":
            is_to = diff_data[change_type]["to"].tame(check_bool)
            mapping = {"is_blocked": ("blocked", "unblocked"), "is_closed": ("closed", "reopened")}
            event_type = mapping[change_type][0] if is_to else mapping[change_type][1]

        case "user_story":
            event_type = "changed_us"
            values["old"], values["new"] = get_old_and_new_values(change_type, message)

        case "subject" | "name":
            event_type = "renamed"
            values["old"], values["new"] = get_old_and_new_values(change_type, message)

        case "priority" | "severity" | "type" | "status":
            event_type = f"changed_{change_type}"
            values["old"], values["new"] = get_old_and_new_values(change_type, message)

        case _:
            return None

    return EventType(type=message["type"].tame(check_string), event=event_type, values=values)


def parse_webhook_test(
    message: WildValue,
) -> EventType:
    return {
        "type": "webhook_test",
        "event": "test",
        "values": {
            "user": get_display_user(message),
            "end_type": "test",
        },
    }


def parse_message(
    message: WildValue,
) -> list[EventType]:
    events: list[EventType] = []
    action = message["action"].tame(check_string)

    match action:
        case "create" | "delete":
            events.append(parse_create_or_delete(message))
        case "change":
            if message["change"]["diff"]:
                for value in message["change"]["diff"].keys():  # noqa: SIM118
                    parsed_event = parse_change_event(value, message)
                    if parsed_event:
                        events.append(parsed_event)
            if message["change"]["comment"].tame(check_string):
                events.append(parse_comment(message))
        case "test":
            events.append(parse_webhook_test(message))
        case _:  # nocoverage
            pass

    return events


def generate_content(data: EventType) -> str:
    template = TEMPLATES[data["type"]][data["event"]]
    content = template.format(**data["values"])
    return content


def get_display_user(message: WildValue) -> str:
    owner_name = message["by"]["full_name"].tame(check_string)
    owner_link = message["by"]["permalink"].tame(check_string)
    return f"[{owner_name}]({owner_link})"


def format_subject(subject_text: str, permalink: str | None) -> str:
    return f"[{subject_text}]({permalink})" if permalink else f"**{subject_text}**"


def get_subject(message: WildValue, data_field: str | None = None) -> str:
    data = message["data"][data_field] if data_field is not None else message["data"]
    text = data.get("subject").tame(check_none_or(check_string)) or data["name"].tame(check_string)
    permalink = data.get("permalink").tame(check_none_or(check_string))
    return format_subject(text, permalink)

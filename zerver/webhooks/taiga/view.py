"""Taiga integration for Zulip.

Tips for notification output:

*Text formatting*: if there has been a change of a property, the new
value should always be in bold; otherwise the subject of US/task
should be in bold.
"""

from typing import TypeAlias

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

EventType: TypeAlias = dict[str, str | dict[str, str | bool | None]]
ReturnType: TypeAlias = tuple[WildValue, WildValue]


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


def get_old_and_new_values(change_type: str, message: WildValue) -> ReturnType:
    old = message["change"]["diff"][change_type].get("from")
    new = message["change"]["diff"][change_type].get("to")
    return old, new


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
    if message["type"].tame(check_string) == "relateduserstory":
        return {
            "type": message["type"].tame(check_string),
            "event": message["action"].tame(check_string),
            "values": {
                "user": get_display_user(message),
                "epic_subject": get_epic_subject(message),
                "userstory_subject": get_userstory_subject(message),
            },
        }

    return {
        "type": message["type"].tame(check_string),
        "event": message["action"].tame(check_string),
        "values": {
            "user": get_display_user(message),
            "subject": get_subject(message),
        },
    }


def parse_change_event(change_type: str, message: WildValue) -> EventType | None:
    evt: EventType = {}
    values: dict[str, str | bool | None] = {
        "user": get_display_user(message),
        "subject": get_subject(message),
    }

    if change_type in ["description_diff", "points"]:
        event_type = change_type

    elif change_type in ["milestone", "assigned_to"]:
        old, new = get_old_and_new_values(change_type, message)
        tamed_old = old.tame(check_none_or(check_string))
        tamed_new = new.tame(check_none_or(check_string))
        if not tamed_old:
            event_type = "set_" + change_type
            values["new"] = tamed_new
        elif not tamed_new:
            event_type = "unset_" + change_type
            values["old"] = tamed_old
        else:
            event_type = "changed_" + change_type
            values.update(old=tamed_old, new=tamed_new)

    elif change_type == "is_blocked":
        if message["change"]["diff"]["is_blocked"]["to"].tame(check_bool):
            event_type = "blocked"
        else:
            event_type = "unblocked"

    elif change_type == "is_closed":
        if message["change"]["diff"]["is_closed"]["to"].tame(check_bool):
            event_type = "closed"
        else:
            event_type = "reopened"

    elif change_type == "user_story":
        old, new = get_old_and_new_values(change_type, message)
        event_type = "changed_us"
        tamed_old = old.tame(check_none_or(check_string))
        tamed_new = new.tame(check_none_or(check_string))
        values.update(old=tamed_old, new=tamed_new)

    elif change_type in ["subject", "name"]:
        event_type = "renamed"
        old, new = get_old_and_new_values(change_type, message)
        tamed_old = old.tame(check_none_or(check_string))
        tamed_new = new.tame(check_none_or(check_string))
        values.update(old=tamed_old, new=tamed_new)

    elif change_type in ["estimated_finish", "estimated_start", "due_date"]:
        old, new = get_old_and_new_values(change_type, message)
        tamed_old = old.tame(check_none_or(check_string))
        tamed_new = new.tame(check_none_or(check_string))
        if not tamed_old:
            event_type = "set_" + change_type
            values["new"] = tamed_new
        elif tamed_old != tamed_new:
            event_type = change_type
            values.update(old=tamed_old, new=tamed_new)
        else:
            # date hasn't changed
            return None

    elif change_type in ["priority", "severity", "type", "status"]:
        event_type = "changed_" + change_type
        old, new = get_old_and_new_values(change_type, message)
        tamed_old = old.tame(check_none_or(check_string))
        tamed_new = new.tame(check_none_or(check_string))
        values.update(old=tamed_old, new=tamed_new)

    else:
        # we are not supporting this type of event
        return None

    evt.update(type=message["type"].tame(check_string), event=event_type, values=values)
    return evt


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
    if message["action"].tame(check_string) in ["create", "delete"]:
        events.append(parse_create_or_delete(message))
    elif message["action"].tame(check_string) == "change":
        if message["change"]["diff"]:
            for value in message["change"]["diff"].keys():  # noqa: SIM118
                parsed_event = parse_change_event(value, message)
                if parsed_event:
                    events.append(parsed_event)
        if message["change"]["comment"].tame(check_string):
            events.append(parse_comment(message))
    elif message["action"].tame(check_string) == "test":
        events.append(parse_webhook_test(message))

    return events


def generate_content(data: EventType) -> str:
    assert isinstance(data["type"], str) and isinstance(data["event"], str)
    template = TEMPLATES[data["type"]][data["event"]]

    assert isinstance(data["values"], dict)
    content = template.format(**data["values"])
    return content


def get_display_user(message: WildValue) -> str:
    owner_name = message["by"]["full_name"].tame(check_string)
    owner_link = message["by"]["permalink"].tame(check_string)
    return f"[{owner_name}]({owner_link})"


def get_subject(message: WildValue) -> str:
    data = message["data"]

    subject = data.get("subject").tame(check_none_or(check_string))
    subject_to_use = subject if subject else data["name"].tame(check_string)

    return (
        f"[{subject_to_use}]({data['permalink'].tame(check_string)})"
        if "permalink" in data
        else f"**{subject_to_use}**"
    )


def get_epic_subject(message: WildValue) -> str:
    return (
        f"[{message['data']['epic']['subject'].tame(check_string)}]({message['data']['epic']['permalink'].tame(check_string)})"
        if "permalink" in message["data"]["epic"]
        else f"**{message['data']['epic']['subject'].tame(check_string)}**"
    )


def get_userstory_subject(message: WildValue) -> str:
    us_data = message["data"]["user_story"]
    return (
        f"[{us_data['subject'].tame(check_string)}]({us_data['permalink'].tame(check_string)})"
        if "permalink" in us_data
        else f"**{us_data['subject'].tame(check_string)}**"
    )

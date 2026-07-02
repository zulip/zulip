from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile

CONTENT_MESSAGE_TEMPLATE = "\n~~~ quote\n{message}\n~~~\n"

ISSUE_CREATE_OR_UPDATE_TEMPLATE = "[{type}]({url}) was {action} in team {team_name}"

ISSUE_REMOVE_TEMPLATE = "This issue has been removed from team {team_name}."
COMMENT_CREATE_OR_UPDATE_TEMPLATE = "{user} [{action}]({url}) on issue **{issue_title}**:"
COMMENT_REMOVE_TEMPLATE = "{user} has removed a comment."
PROJECT_CREATE_TEMPLATE = "{actor} created project [{name}]({url})"
PROJECT_UPDATE_TEMPLATE = "{actor} updated project [{name}]({url})"
PROJECT_REMOVE_TEMPLATE = "{actor} removed project **{name}**."
PROJECT_UPDATE_CREATE_OR_EDIT_TEMPLATE = (
    "{user} [{action}]({url}) a status update on **{project_name}** (health: {health}):"
)
PROJECT_UPDATE_REMOVE_TEMPLATE = "{user} removed a status update on **{project_name}**."

PROJECT_HEALTH_LABELS = {
    "onTrack": "On Track",
    "atRisk": "At Risk",
    "offTrack": "Off Track",
}

PROJECT_PRIORITY_LABELS = {
    1: "Urgent",
    2: "High",
    3: "Medium",
    4: "Low",
}


def get_issue_created_or_updated_message(event: str, payload: WildValue, action: str) -> str:
    message = ISSUE_CREATE_OR_UPDATE_TEMPLATE.format(
        type="Issue" if event == "issue" else "Sub-Issue",
        number=payload["data"]["number"].tame(check_int),
        title=payload["data"]["title"].tame(check_string),
        url=payload["url"].tame(check_string),
        action=action,
        team_name=payload["data"]["team"]["name"].tame(check_string),
    )

    has_description = "description" in payload["data"]
    if has_description:
        message += f":{CONTENT_MESSAGE_TEMPLATE.format(message=payload['data']['description'].tame(check_string))}"
    else:
        message += "."

    to_add = []

    priority_label = payload["data"]["priorityLabel"].tame(check_string)
    if priority_label != "No priority":
        to_add.append(f"Priority: {priority_label}")

    has_assignee = "assignee" in payload["data"]
    if has_assignee:
        to_add.append(f"Assignee: {payload['data']['assignee']['name'].tame(check_string)}")

    status = payload["data"]["state"]["name"].tame(check_string)
    to_add.append(f"Status: {status}")

    message += f"\n{', '.join(to_add)}."

    return message


def get_issue_remove_body(payload: WildValue, event: str) -> str:
    return ISSUE_REMOVE_TEMPLATE.format(
        type="Issue" if event == "issue" else "Sub-Issue",
        number=payload["data"]["number"].tame(check_int),
        title=payload["data"]["title"].tame(check_string),
        team_name=payload["data"]["team"]["name"].tame(check_string),
    )


def get_comment_create_or_update_body(payload: WildValue, event: str, action: str) -> str:
    message = COMMENT_CREATE_OR_UPDATE_TEMPLATE.format(
        user=payload["data"]["user"]["name"].tame(check_string),
        action=action,
        url=payload["url"].tame(check_string),
        issue_title=payload["data"]["issue"]["title"].tame(check_string),
    )
    message += CONTENT_MESSAGE_TEMPLATE.format(message=payload["data"]["body"].tame(check_string))
    return message


def get_comment_remove_body(payload: WildValue, event: str) -> str:
    return COMMENT_REMOVE_TEMPLATE.format(user=payload["data"]["user"]["name"].tame(check_string))


def get_issue_or_sub_issue_message(payload: WildValue, event: str) -> str:
    action = payload["action"].tame(check_string)
    if action == "remove":
        return get_issue_remove_body(payload, event)

    return get_issue_created_or_updated_message(
        event, payload, action="created" if action == "create" else "updated"
    )


def get_comment_message(payload: WildValue, event: str) -> str:
    action = payload["action"].tame(check_string)
    if action == "remove":
        return get_comment_remove_body(payload, event)

    return get_comment_create_or_update_body(
        payload, event, "commented" if action == "create" else "updated comment"
    )


def get_actor_name(payload: WildValue) -> str:
    return payload["actor"]["name"].tame(check_string)


def get_project_inline_fields(payload: WildValue) -> list[str]:
    # The project's at-a-glance identity, rendered as a single bold-labeled
    # line below the create message.
    fields = []
    data = payload["data"]

    status = data.get("status")
    if status:
        fields.append(f"**Status:** {status['name'].tame(check_string)}")

    lead = data.get("lead")
    if lead:
        fields.append(f"**Lead:** {lead['name'].tame(check_string)}")

    if "priority" in data:
        priority = data["priority"].tame(check_int)
        if priority in PROJECT_PRIORITY_LABELS:
            fields.append(f"**Priority:** {PROJECT_PRIORITY_LABELS[priority]}")

    return fields


def get_project_date_fields(payload: WildValue) -> list[str]:
    data = payload["data"]
    dates = []
    for date_field, label in (("startDate", "Start date"), ("targetDate", "Target date")):
        if date_field in data:
            value = data[date_field].tame(check_none_or(check_string))
            if value:
                dates.append(f"**{label}:** {value}")
    return dates


def get_project_milestone_fields(payload: WildValue) -> list[str]:
    data = payload["data"]
    if "milestones" in data:
        milestone_names = [m["name"].tame(check_string) for m in data["milestones"]]
        if milestone_names:
            label = "Milestone" if len(milestone_names) == 1 else "Milestones"
            return [f"**{label}:** {', '.join(milestone_names)}"]
    return []


# Linear's API name "content" is what users edit as the project description;
# the separate "description" field is a short summary that rarely changes.
PROJECT_UPDATE_CHANGE_FIELDS = (
    "name",
    "statusId",
    "leadId",
    "priority",
    "startDate",
    "targetDate",
    "content",
)


def get_project_update_changes(payload: WildValue) -> list[str]:
    changes = []
    data = payload["data"]
    updated_from = payload["updatedFrom"]

    for key in PROJECT_UPDATE_CHANGE_FIELDS:
        if key not in updated_from:
            continue

        if key == "name":
            changes.append(f"renamed to {data['name'].tame(check_string)}")
        elif key == "statusId":
            status = data.get("status")
            if status:
                changes.append(f"project status is now {status['name'].tame(check_string)}")
        elif key == "leadId":
            lead = data.get("lead")
            if lead:
                changes.append(f"{lead['name'].tame(check_string)} is now the project lead")
        elif key == "priority":
            new_priority = data["priority"].tame(check_int)
            if new_priority in PROJECT_PRIORITY_LABELS:
                changes.append(f"priority is now set to {PROJECT_PRIORITY_LABELS[new_priority]}")
        elif key in ("startDate", "targetDate"):
            label = "target date" if key == "targetDate" else "start date"
            new_value = data[key].tame(check_none_or(check_string))
            if new_value is not None:
                old_value = updated_from[key].tame(check_none_or(check_string))
                if old_value is None:
                    changes.append(f"{label} is set to {new_value}")
                elif new_value < old_value:
                    changes.append(f"{label} is preponed to {new_value}")
                else:
                    changes.append(f"{label} is postponed to {new_value}")
        elif key == "content":
            changes.append("description is updated")

    return changes


def get_project_create_or_update_body(payload: WildValue, action: str) -> str:
    actor = get_actor_name(payload)
    name = payload["data"]["name"].tame(check_string)
    url = payload["url"].tame(check_string)

    if action != "create":
        # changes is non-empty: content-free updates were filtered in get_event_type.
        message = PROJECT_UPDATE_TEMPLATE.format(actor=actor, name=name, url=url)
        sentence = ", ".join(get_project_update_changes(payload))
        sentence = sentence[0].upper() + sentence[1:]
        return f"{message}.\n{sentence}."

    message = PROJECT_CREATE_TEMPLATE.format(actor=actor, name=name, url=url)
    description = (
        payload["data"]["description"].tame(check_string)
        if "description" in payload["data"]
        else ""
    )
    inline_fields = get_project_inline_fields(payload)
    dates = get_project_date_fields(payload)
    bullets = get_project_milestone_fields(payload)

    # The schedule lives inside the description quote when there is one;
    # otherwise the dates drop down to bullets alongside the milestones.
    if description:
        quote = description
        if dates:
            quote += "\n" + " – ".join(dates)
        message += f":{CONTENT_MESSAGE_TEMPLATE.format(message=quote)}"
    else:
        bullets = dates + bullets

    lines = []
    if inline_fields:
        lines.append(" · ".join(inline_fields))
    lines.extend(f"- {bullet}" for bullet in bullets)

    if not lines:  # nocoverage
        # A project always carries at least a status, so this is defensive.
        if not description:
            message += "."
        return message

    fields = "\n".join(lines)
    if description:
        # The quote template already ends with a newline, so the fields
        # follow the closing fence directly.
        return message + fields
    return f"{message}\n{fields}"


def get_project_remove_body(payload: WildValue) -> str:
    return PROJECT_REMOVE_TEMPLATE.format(
        actor=get_actor_name(payload),
        name=payload["data"]["name"].tame(check_string),
    )


def get_project_message(payload: WildValue, event: str) -> str:
    action = payload["action"].tame(check_string)
    if action == "remove":
        return get_project_remove_body(payload)

    return get_project_create_or_update_body(payload, "create" if action == "create" else "update")


def get_project_update_message(payload: WildValue, event: str) -> str:
    action = payload["action"].tame(check_string)
    user = payload["data"]["user"]["name"].tame(check_string)
    project_name = payload["data"]["project"]["name"].tame(check_string)

    if action == "remove":
        return PROJECT_UPDATE_REMOVE_TEMPLATE.format(user=user, project_name=project_name)

    health = payload["data"]["health"].tame(check_string)
    message = PROJECT_UPDATE_CREATE_OR_EDIT_TEMPLATE.format(
        user=user,
        action="posted" if action == "create" else "edited",
        url=payload["url"].tame(check_string),
        project_name=project_name,
        health=PROJECT_HEALTH_LABELS.get(health, health),
    )
    message += CONTENT_MESSAGE_TEMPLATE.format(message=payload["data"]["body"].tame(check_string))

    if "diffMarkdown" in payload["data"]:
        diff_markdown = payload["data"]["diffMarkdown"].tame(check_none_or(check_string))
        if diff_markdown:
            message += f"\n{diff_markdown}"

    return message


EVENT_FUNCTION_MAPPER: dict[str, Callable[[WildValue, str], str]] = {
    "issue": get_issue_or_sub_issue_message,
    "sub_issue": get_issue_or_sub_issue_message,
    "comment": get_comment_message,
    "project": get_project_message,
    "project_update": get_project_update_message,
}

IGNORED_EVENTS = ["IssueLabel", "Cycle", "Reaction"]

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("Linear", notify_bot_owner_on_invalid_json=True, all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_linear_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    event_type = get_event_type(payload)
    if event_type is None:
        return json_success(request)

    topic_name = get_topic(user_specified_topic, event_type, payload)

    body_function = EVENT_FUNCTION_MAPPER[event_type]
    body = body_function(payload, event_type)

    check_send_webhook_message(request, user_profile, topic_name, body)

    return json_success(request)


def get_topic(user_specified_topic: str | None, event: str, payload: WildValue) -> str:
    if user_specified_topic is not None:
        return user_specified_topic
    elif event == "comment":
        issue_title = payload["data"]["issue"]["title"].tame(check_string)
        return f"Issue: {issue_title}"
    elif event == "sub_issue":
        title = payload["data"]["title"].tame(check_string)
        return f"Sub-Issue: {title}"
    elif event == "issue":
        title = payload["data"]["title"].tame(check_string)
        return f"Issue: {title}"
    elif event == "project":
        name = payload["data"]["name"].tame(check_string)
        return f"Project: {name}"
    elif event == "project_update":
        name = payload["data"]["project"]["name"].tame(check_string)
        return f"Project: {name}"

    raise UnsupportedWebhookEventTypeError(event)


def get_event_type(payload: WildValue) -> str | None:
    event_type = payload["type"].tame(check_string)

    if event_type == "Issue":
        has_parent_id = "parentId" in payload["data"]
        return "issue" if not has_parent_id else "sub_issue"
    elif event_type == "Comment":
        return "comment"
    elif event_type == "Project":
        # Suppress Project.update events that wouldn't produce a renderable
        # message: Linear's auto-fire after a ProjectUpdate post (lastUpdateId
        # in updatedFrom), and any update whose changes are all clears/noise
        # (we only notify on adds/replaces, not removes).
        if "updatedFrom" in payload:
            if "lastUpdateId" in payload["updatedFrom"]:
                return None
            if not get_project_update_changes(payload):
                return None
        return "project"
    elif event_type == "ProjectUpdate":
        return "project_update"
    elif event_type in IGNORED_EVENTS:  # nocoverage
        return None

    # This happens when a new event type is added to Linear and we
    # haven't updated the integration yet.
    complete_event = "{}:{}".format(
        event_type, payload.get("action", "???").tame(check_string)
    )  # nocoverage

    raise UnsupportedWebhookEventTypeError(complete_event)

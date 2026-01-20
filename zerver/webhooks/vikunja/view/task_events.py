from collections.abc import Mapping
from datetime import datetime

from zerver.lib.timestamp import datetime_to_global_time
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_float,
    check_int,
    check_none_or,
    check_string,
    check_union,
)

from .html_conversion import convert_html_body_to_markdown

SUPPORTED_TASK_EVENTS = [
    "task.created",
    "task.updated",
    "task.deleted",
    "task.assignee.created",
    "task.assignee.deleted",
    "task.comment.created",
    "task.comment.edited",
    "task.comment.deleted",
    "task.attachment.created",
    "task.attachment.deleted",
    "task.relation.created",
    "task.relation.deleted",
]

IGNORED_TASK_EVENTS: list[str] = [
    "ignored.task.event.placeholder",  # Placeholder for any task events we want to ignore in the future
]

CREATE = "task.created"
UPDATE = "task.updated"
DELETE = "task.deleted"
ADD_ASSIGNEE = "task.assignee.created"
REMOVE_ASSIGNEE = "task.assignee.deleted"
ADD_COMMENT = "task.comment.created"
EDIT_COMMENT = "task.comment.edited"
REMOVE_COMMENT = "task.comment.deleted"
ADD_ATTACHMENT = "task.attachment.created"
REMOVE_ATTACHMENT = "task.attachment.deleted"
ADD_RELATION = "task.relation.created"
REMOVE_RELATION = "task.relation.deleted"

VIKUNJA_TASK_URL_TEMPLATE = "[{task_name}]({task_url})"
VIKUNJA_PROJECT_URL_TEMPLATE = "[{project_name}]({project_url})"

EVENTS_TO_MESSAGE_MAPPER = {
    CREATE: "created {task_url_template} in {project_url_template}{task_bucket}.",
    UPDATE: "updated {task_color}{task_url_template}{task_status} in {project_url_template}{task_bucket}.{details}",
    DELETE: "deleted {task_url_template} from {project_url_template}{task_bucket}.",
    ADD_ASSIGNEE: "added {assignee_name} to {task_color}{task_url_template} in {project_url_template}{task_bucket}.",
    REMOVE_ASSIGNEE: "removed {assignee_name} from {task_color}{task_url_template} in {project_url_template}{task_bucket}.",
    ADD_COMMENT: "commented on {task_color}{task_url_template} in {project_url_template}{task_bucket}:{comment_formatted_text}",
    EDIT_COMMENT: "edited a comment on {task_color}{task_url_template} in {project_url_template}{task_bucket}:{comment_formatted_text}",
    REMOVE_COMMENT: "removed this comment by {comment_author} from {task_color}{task_url_template} in {project_url_template}{task_bucket}:{comment_formatted_text}",
    ADD_ATTACHMENT: "added the attachment `{attachment_name}` to {task_color}{task_url_template} in {project_url_template}{task_bucket}.",
    REMOVE_ATTACHMENT: "removed the attachment `{attachment_name}` from {task_color}{task_url_template} in {project_url_template}{task_bucket}.",
    ADD_RELATION: "set {linked_task_url_template} {relation_kind_text} {task_color}{task_url_template}.",
    REMOVE_RELATION: "removed the relation of {linked_task_url_template} {relation_kind_text} {task_color}{task_url_template}.",
}

PRIORITY_MAP = {
    1: ["Low", ":grey_exclamation:"],
    2: ["Medium", ":exclamation:"],
    3: ["High", ":exclamation:"],
    4: ["Urgent", ":double_exclamation:"],
    5: ["DO NOW", ":alert:"],
}

RELATION_KIND_TO_MESSAGE_MAPPER = {
    "related": "as a related task of",
    "subtask": "as a subtask of",
    "parenttask": "as a parent task of",
    "duplicates": "as a duplicate task of",
    "blocking": "is blocked by the task",
    "blocked": "is blocking the task",
    "precedes": "as a preceding task of",
    "follows": "as a following task of",
    "copiedfrom": "as the original copy of the task",
    "copiedto": "as a copy of the task",
}


# Low-level utilities
def prettify_date(date_string: str) -> str:
    dt = datetime.fromisoformat(date_string)
    return datetime_to_global_time(dt)


def convert_hex_color_to_closest_emoji(hex_color: str) -> str:
    AVAILABLE_EMOJI = {
        "f54336": ":red_circle:",
        "ff9702": ":orange_circle:",
        "ffcb29": ":yellow_circle:",
        "7ebd39": ":green_circle:",
        "1f7bd0": ":blue_circle:",
        "a945b9": ":purple_circle:",
        "bb6c4c": ":brown_circle:",
        "424140": ":black_circle:",
        "dfdfdf": ":white_circle:",
    }

    def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
        hex_str = hex_str.lstrip("#")
        return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

    target_rgb = hex_to_rgb(hex_color)

    # Find the closest color by Euclidean distance in RGB space
    def color_distance(color_hex: str) -> float:
        color_rgb = hex_to_rgb(color_hex)
        return sum((a - b) ** 2 for a, b in zip(target_rgb, color_rgb, strict=False))

    closest_color_hex = min(AVAILABLE_EMOJI.keys(), key=color_distance)
    return AVAILABLE_EMOJI[closest_color_hex]


# Data extraction helpers
def get_action_data(payload: WildValue) -> WildValue:
    return payload["data"]


def get_project_id(payload: WildValue) -> int:
    return get_action_data(payload)["project"]["id"].tame(check_int)


def get_project_name(payload: WildValue) -> str:
    return get_action_data(payload)["project"]["title"].tame(check_string)


def get_task_name(payload: WildValue) -> str:
    return get_action_data(payload)["task"]["title"].tame(check_string)


def get_task_color(payload: WildValue) -> str | None:
    color = get_action_data(payload)["task"]["hex_color"].tame(check_string)
    return color or None


def get_task_bucket(task: WildValue) -> WildValue | None:
    buckets = task.get("buckets", [])
    if not buckets:
        return None
    return buckets[0]


def get_task_url(host: str, payload: WildValue) -> str:
    id = get_action_data(payload)["task"].get("id").tame(check_int)
    return f"{host}/tasks/{id}"


# Template filling helpers
def get_filled_task_url_template(host: str, payload: WildValue) -> str:
    if payload.get("event_name").tame(check_string) == "task.deleted":
        data = get_action_data(payload)
        task_identifier = data["task"]["identifier"].tame(check_string)
        return f"*{get_task_name(payload)}* `{task_identifier}`"

    return VIKUNJA_TASK_URL_TEMPLATE.format(
        task_name=get_task_name(payload), task_url=get_task_url(host, payload)
    )


def get_filled_project_url_template(host: str, payload: WildValue) -> str:
    project_id = get_project_id(payload)
    return VIKUNJA_PROJECT_URL_TEMPLATE.format(
        project_name=get_project_name(payload),
        project_url=f"{host}/projects/{project_id}",
    )


def fill_appropriate_message_content(
    host: str, payload: WildValue, action_type: str, data: Mapping[str, str] = {}
) -> str:
    data = dict(data)
    if "task_url_template" not in data:
        data["task_url_template"] = get_filled_task_url_template(host, payload)
    if "project_url_template" not in data:
        data["project_url_template"] = get_filled_project_url_template(host, payload)
    if "task_identifier" not in data:
        data["task_identifier"] = get_action_data(payload)["task"]["identifier"].tame(check_string)
    if "task_bucket" not in data:
        task = get_action_data(payload)["task"]
        bucket = get_task_bucket(task)
        data["task_bucket"] = f" > {bucket.get('title').tame(check_string)}" if bucket else ""
    if "task_color" not in data:
        color = get_task_color(payload)
        data["task_color"] = f"{convert_hex_color_to_closest_emoji(color)} " if color else ""

    message_body = get_message_body(action_type)
    return message_body.format(**data)


def get_message_body(event_name: str) -> str:
    return EVENTS_TO_MESSAGE_MAPPER[event_name]


# Markdown formatting helpers
def get_labels_md(labels: WildValue) -> str:
    labels_md_list = []
    for label in labels:
        label_name = label.get("title").tame(check_string)
        label_color = label.get("hex_color").tame(check_string).lstrip("#")
        label_emoji = convert_hex_color_to_closest_emoji(label_color)
        labels_md_list.append(f"{label_emoji} `{label_name}`")
    return ", ".join(labels_md_list)


def get_priority_md(priority: int) -> str:
    return f"{PRIORITY_MAP.get(priority, ['', ''])[1]} Priority: {PRIORITY_MAP.get(priority, ['', ''])[0]}"


def get_dates_md(dates: dict[str, str | None]) -> str:
    icons = {"start_date": ":blue_square:", "end_date": ":red_square:", "due_date": ":alarm_clock:"}
    dates_md_list = []
    for date_field, date_value in dates.items():
        if not date_value:
            continue
        dates_md_list.append(
            f"{icons.get(date_field, '')} {date_field.replace('_', ' ').capitalize()}: {prettify_date(date_value)}"
        )

    dates_joined = "\n".join(dates_md_list)
    return dates_joined


def get_progress_md(progress: float) -> str:
    progress_bar_length = 10
    filled_length = int(progress_bar_length * progress // 100)
    bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
    return f":chart: Progress: {bar} {progress:.0f}%"


def get_description_md(description_html: str) -> str:
    description_md = convert_html_body_to_markdown(description_html)
    return f"~~~ quote\n{description_md}\n~~~" if description_md.strip() else ""


# Event-specific body builders
def get_body_by_action_type_without_data(host: str, payload: WildValue, action_type: str) -> str:
    return fill_appropriate_message_content(host, payload, action_type)


def get_assignee_body(host: str, payload: WildValue, action_type: str) -> str:
    data = {
        "assignee_name": get_action_data(payload)["assignee"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(host, payload, action_type, data)


def get_comment_body(host: str, payload: WildValue, action_type: str) -> str:
    text_html = get_action_data(payload)["comment"]["comment"].tame(check_string)
    text_md = convert_html_body_to_markdown(text_html)
    comment_formatted_text = f"\n~~~ quote\n{text_md}\n~~~" if text_md.strip() else ""

    author = get_action_data(payload)["comment"]["author"]

    data = {
        "comment_formatted_text": comment_formatted_text,
        "comment_author": author.get("name").tame(check_string) if author else "unknown",
    }
    return fill_appropriate_message_content(host, payload, action_type, data)


def get_attachment_body(host: str, payload: WildValue, action_type: str) -> str:
    data = {
        "attachment_name": get_action_data(payload)["attachment"]["file"]["name"].tame(
            check_string
        ),
    }
    return fill_appropriate_message_content(host, payload, action_type, data)


def get_relation_body(host: str, payload: WildValue, action_type: str) -> str:
    source_task = get_action_data(payload)["task"]
    target_task_id = get_action_data(payload)["relation"].get("other_task_id").tame(check_int)
    relation_kind = get_action_data(payload)["relation"].get("relation_kind").tame(check_string)

    related_tasks_of_kind = source_task.get("related_tasks", {}).get(relation_kind, [])
    target_task = next(
        (
            task
            for task in related_tasks_of_kind
            if task.get("id").tame(check_int) == target_task_id
        ),
        None,
    )

    target_task_name = target_task.get("title").tame(check_string) if target_task else "this task"

    data = {
        "linked_task_url_template": VIKUNJA_TASK_URL_TEMPLATE.format(
            task_name=target_task_name,
            task_url=f"{host}/tasks/{target_task_id}",
        ),
        "relation_kind_text": RELATION_KIND_TO_MESSAGE_MAPPER[relation_kind],
    }
    return fill_appropriate_message_content(host, payload, action_type, data)


def get_update_body(host: str, payload: WildValue, action_type: str) -> str:
    action_data = get_action_data(payload)

    labels = action_data["task"].get("labels", [])

    dates: dict[str, str | None] = {"start_date": None, "end_date": None, "due_date": None}

    for date_field in dates:
        date = action_data["task"].get(date_field).tame(check_none_or(check_string))
        if not date or date == "0001-01-01T00:00:00Z":
            continue
        dates[date_field] = date

    priority = action_data["task"].get("priority", 0).tame(check_none_or(check_int))
    if not priority:
        priority = 0

    percent_done = (
        action_data["task"].get("percent_done", 0.0).tame(check_union([check_float, check_int]))
    )
    progress = 0.0
    if percent_done is not None:
        progress = percent_done * 100

    description_html = action_data["task"]["description"].tame(check_string)
    description_md = get_description_md(description_html)

    details = []
    if labels:
        details.append(get_labels_md(labels))
    if any(dates.values()):
        details.append(get_dates_md(dates))
    if priority > 0 and priority <= 5:
        details.append(get_priority_md(priority))
    if progress > 0:
        details.append(get_progress_md(progress))
    if description_md:
        details.append(description_md)

    joined_details = "\n---\n".join(details).strip()

    data = {
        "task_status": " ✔︎" if action_data["task"]["done"].tame(check_bool) else "",
        "details": f"\n```spoiler Show details...\n\n{joined_details}\n```"
        if joined_details
        else "",
    }

    return fill_appropriate_message_content(host, payload, action_type, data)


# Main entry point
def get_body(host: str, payload: WildValue, event_name: str) -> str:
    message_body = EVENTS_TO_FILL_BODY_MAPPER[event_name](host, payload, event_name)
    creator = get_action_data(payload)["doer"]
    creator_name = creator.get("name").tame(check_none_or(check_string)) if creator else "unknown"
    return f"{creator_name} {message_body}"


def process_task_action(host: str, payload: WildValue, event_name: str) -> tuple[str, str] | None:
    return get_project_name(payload), get_body(host, payload, event_name)


EVENTS_TO_FILL_BODY_MAPPER = {
    CREATE: get_body_by_action_type_without_data,
    UPDATE: get_update_body,
    DELETE: get_body_by_action_type_without_data,
    ADD_ASSIGNEE: get_assignee_body,
    REMOVE_ASSIGNEE: get_assignee_body,
    ADD_COMMENT: get_comment_body,
    EDIT_COMMENT: get_comment_body,
    REMOVE_COMMENT: get_comment_body,
    ADD_ATTACHMENT: get_attachment_body,
    REMOVE_ATTACHMENT: get_attachment_body,
    ADD_RELATION: get_relation_body,
    REMOVE_RELATION: get_relation_body,
}

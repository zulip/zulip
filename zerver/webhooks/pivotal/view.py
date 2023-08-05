"""Webhooks for external integrations."""
import re
from typing import Any, Dict, List, Optional, Tuple

import orjson
from defusedxml.ElementTree import fromstring as xml_fromstring
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError, UnsupportedWebhookEventTypeError
from zerver.lib.request import has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def api_pivotal_webhook_v3(request: HttpRequest, user_profile: UserProfile) -> Tuple[str, str, str]:
    payload = xml_fromstring(request.body)

    def get_text(attrs: List[str]) -> str:
        start = payload
        try:
            for attr in attrs:
                start = start.find(attr)
            return start.text
        except AttributeError:
            return ""

    event_type = payload.find("event_type").text
    description = payload.find("description").text
    project_id = payload.find("project_id").text
    story_id = get_text(["stories", "story", "id"])
    # Ugh, the URL in the XML data is not a clickable URL that works for the user
    # so we try to build one that the user can actually click on
    url = f"https://www.pivotaltracker.com/s/projects/{project_id}/stories/{story_id}"

    # Pivotal doesn't tell us the name of the story, but it's usually in the
    # description in quotes as the first quoted string
    name_re = re.compile(r'[^"]+"([^"]+)".*')
    match = name_re.match(description)
    if match and len(match.groups()):
        name = match.group(1)
    else:
        name = "Story changed"  # Failed for an unknown reason, show something
    more_info = f" [(view)]({url})."

    if event_type == "story_update":
        topic = name
        content = description + more_info
    elif event_type == "note_create":
        topic = "Comment added"
        content = description + more_info
    elif event_type == "story_create":
        issue_desc = get_text(["stories", "story", "description"])
        issue_type = get_text(["stories", "story", "story_type"])
        issue_status = get_text(["stories", "story", "current_state"])
        estimate = get_text(["stories", "story", "estimate"])
        if estimate != "":
            estimate = f" worth {estimate} story points"
        topic = name
        content = f"{description} ({issue_status} {issue_type}{estimate}):\n\n~~~ quote\n{issue_desc}\n~~~\n\n{more_info}"
    return topic, content, f"{event_type}_v3"


UNSUPPORTED_EVENT_TYPES = [
    "task_create_activity",
    "comment_delete_activity",
    "task_delete_activity",
    "task_update_activity",
    "story_move_from_project_activity",
    "story_delete_activity",
    "story_move_into_project_activity",
    "epic_update_activity",
    "label_create_activity",
]

ALL_EVENT_TYPES = [
    "story_update_v3",
    "note_create_v3",
    "story_create_v3",
    "story_move_activity_v5",
    "story_create_activity_v5",
    "story_update_activity_v5",
    "comment_create_activity_v5",
]


def api_pivotal_webhook_v5(request: HttpRequest, user_profile: UserProfile) -> Tuple[str, str, str]:
    payload = orjson.loads(request.body)

    event_type = payload["kind"]

    project_name = payload["project"]["name"]
    project_id = payload["project"]["id"]

    primary_resources = payload["primary_resources"][0]
    story_url = primary_resources["url"]
    story_type = primary_resources.get("story_type")
    story_id = primary_resources["id"]
    story_name = primary_resources["name"]

    performed_by = payload.get("performed_by", {}).get("name", "")

    story_info = f"[{project_name}](https://www.pivotaltracker.com/s/projects/{project_id}): [{story_name}]({story_url})"

    changes = payload.get("changes", [])

    content = ""
    topic = f"#{story_id}: {story_name}"

    def extract_comment(change: Dict[str, Any]) -> Optional[str]:
        if change.get("kind") == "comment":
            return change.get("new_values", {}).get("text", None)
        return None

    if event_type == "story_update_activity":
        # Find the changed valued and build a message
        content += f"{performed_by} updated {story_info}:\n"
        for change in changes:
            old_values = change.get("original_values", {})
            new_values = change["new_values"]

            if "current_state" in old_values and "current_state" in new_values:
                content += "* state changed from **{}** to **{}**\n".format(
                    old_values["current_state"], new_values["current_state"]
                )
            if "estimate" in old_values and "estimate" in new_values:
                old_estimate = old_values.get("estimate", None)
                if old_estimate is None:
                    estimate = "is now"
                else:
                    estimate = f"changed from {old_estimate} to"
                new_estimate = new_values["estimate"] if new_values["estimate"] is not None else "0"
                content += f"* estimate {estimate} **{new_estimate} points**\n"
            if "story_type" in old_values and "story_type" in new_values:
                content += "* type changed from **{}** to **{}**\n".format(
                    old_values["story_type"], new_values["story_type"]
                )

            comment = extract_comment(change)
            if comment is not None:
                content += f"* Comment added:\n~~~quote\n{comment}\n~~~\n"

    elif event_type == "comment_create_activity":
        for change in changes:
            comment = extract_comment(change)
            if comment is not None:
                content += (
                    f"{performed_by} added a comment to {story_info}:\n~~~quote\n{comment}\n~~~"
                )
    elif event_type == "story_create_activity":
        content += f"{performed_by} created {story_type}: {story_info}\n"
        for change in changes:
            new_values = change.get("new_values", {})
            if "current_state" in new_values:
                content += "* State is **{}**\n".format(new_values["current_state"])
            if "description" in new_values:
                content += "* Description is\n\n> {}".format(new_values["description"])
    elif event_type == "story_move_activity":
        content = f"{performed_by} moved {story_info}"
        for change in changes:
            old_values = change.get("original_values", {})
            new_values = change["new_values"]
            if "current_state" in old_values and "current_state" in new_values:
                content += " from **{}** to **{}**.".format(
                    old_values["current_state"], new_values["current_state"]
                )
    elif event_type in UNSUPPORTED_EVENT_TYPES:
        # Known but unsupported Pivotal event types
        pass
    else:
        raise UnsupportedWebhookEventTypeError(event_type)

    return topic, content, f"{event_type}_v5"


@webhook_view("Pivotal", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_pivotal_webhook(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    topic = content = None
    try:
        topic, content, event_type = api_pivotal_webhook_v3(request, user_profile)
    except Exception:
        # Attempt to parse v5 JSON payload
        topic, content, event_type = api_pivotal_webhook_v5(request, user_profile)

    if not content:
        raise JsonableError(_("Unable to handle Pivotal payload"))

    check_send_webhook_message(request, user_profile, topic, content, event_type)
    return json_success(request)

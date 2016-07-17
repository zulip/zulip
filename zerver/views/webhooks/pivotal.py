"""Webhooks for external integrations."""
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import api_key_only_webhook_view, REQ, has_request_variables
from zerver.models import UserProfile, Client

from defusedxml.ElementTree import fromstring as xml_fromstring

import logging
import re
import ujson
from six import text_type
from typing import List, Optional, Tuple


def api_pivotal_webhook_v3(request, user_profile, stream):
    # type: (HttpRequest, UserProfile, text_type) -> Tuple[text_type, text_type]
    payload = xml_fromstring(request.body)

    def get_text(attrs):
        # type: (List[str]) -> str
        start = payload
        try:
            for attr in attrs:
                start = start.find(attr)
            return start.text
        except AttributeError:
            return ""

    event_type = payload.find('event_type').text
    description = payload.find('description').text
    project_id = payload.find('project_id').text
    story_id = get_text(['stories', 'story', 'id'])
    # Ugh, the URL in the XML data is not a clickable url that works for the user
    # so we try to build one that the user can actually click on
    url = "https://www.pivotaltracker.com/s/projects/%s/stories/%s" % (project_id, story_id)

    # Pivotal doesn't tell us the name of the story, but it's usually in the
    # description in quotes as the first quoted string
    name_re = re.compile(r'[^"]+"([^"]+)".*')
    match = name_re.match(description)
    if match and len(match.groups()):
        name = match.group(1)
    else:
        name = "Story changed" # Failed for an unknown reason, show something
    more_info = " [(view)](%s)" % (url,)

    if event_type == 'story_update':
        subject = name
        content = description + more_info
    elif event_type == 'note_create':
        subject = "Comment added"
        content = description +  more_info
    elif event_type == 'story_create':
        issue_desc = get_text(['stories', 'story', 'description'])
        issue_type = get_text(['stories', 'story', 'story_type'])
        issue_status = get_text(['stories', 'story', 'current_state'])
        estimate = get_text(['stories', 'story', 'estimate'])
        if estimate != '':
            estimate = " worth %s story points" % (estimate,)
        subject = name
        content = "%s (%s %s%s):\n\n~~~ quote\n%s\n~~~\n\n%s" % (description,
                                                   issue_status,
                                                   issue_type,
                                                   estimate,
                                                   issue_desc,
                                                   more_info)
    return subject, content

def api_pivotal_webhook_v5(request, user_profile, stream):
    # type: (HttpRequest, UserProfile, text_type) -> Tuple[text_type, text_type]
    payload = ujson.loads(request.body)

    event_type = payload["kind"]

    project_name = payload["project"]["name"]
    project_id = payload["project"]["id"]

    primary_resources = payload["primary_resources"][0]
    story_url = primary_resources["url"]
    story_type = primary_resources["story_type"]
    story_id = primary_resources["id"]
    story_name = primary_resources["name"]

    performed_by = payload.get("performed_by", {}).get("name", "")

    story_info = "[%s](https://www.pivotaltracker.com/s/projects/%s): [%s](%s)" % (
        project_name, project_id, story_name, story_url)

    changes = payload.get("changes", [])

    content = ""
    subject = "#%s: %s" % (story_id, story_name)

    def extract_comment(change):
        # type: (Dict[str, Dict]) -> Optional[text_type]
        if change.get("kind") == "comment":
            return change.get("new_values", {}).get("text", None)
        return None

    if event_type == "story_update_activity":
        # Find the changed valued and build a message
        content += "%s updated %s:\n" % (performed_by, story_info)
        for change in changes:
            old_values = change.get("original_values", {})
            new_values = change["new_values"]

            if "current_state" in old_values and "current_state" in new_values:
                content += "* state changed from **%s** to **%s**\n" % (
                    old_values["current_state"], new_values["current_state"])
            if "estimate" in old_values and "estimate" in new_values:
                old_estimate = old_values.get("estimate", None)
                if old_estimate is None:
                    estimate = "is now"
                else:
                    estimate = "changed from %s to" % (old_estimate,)
                new_estimate = new_values["estimate"] if new_values["estimate"] is not None else "0"
                content += "* estimate %s **%s points**\n" % (estimate, new_estimate)
            if "story_type" in old_values and "story_type" in new_values:
                content += "* type changed from **%s** to **%s**\n" % (
                    old_values["story_type"], new_values["story_type"])

            comment = extract_comment(change)
            if comment is not None:
                content += "* Comment added:\n~~~quote\n%s\n~~~\n" % (comment,)

    elif event_type == "comment_create_activity":
        for change in changes:
            comment = extract_comment(change)
            if comment is not None:
                content += "%s added a comment to %s:\n~~~quote\n%s\n~~~" % (performed_by, story_info, comment)
    elif event_type == "story_create_activity":
        content += "%s created %s: %s\n" % (performed_by, story_type, story_info)
        for change in changes:
            new_values = change.get("new_values", {})
            if "current_state" in new_values:
                content += "* State is **%s**\n" % (new_values["current_state"],)
            if "description" in new_values:
                content += "* Description is\n\n> %s" % (new_values["description"],)
    elif event_type == "story_move_activity":
        content = "%s moved %s" % (performed_by, story_info)
        for change in changes:
            old_values = change.get("original_values", {})
            new_values = change["new_values"]
            if "current_state" in old_values and "current_state" in new_values:
                content += " from **%s** to **%s**" % (old_values["current_state"], new_values["current_state"])
    elif event_type in ["task_create_activity", "comment_delete_activity",
                        "task_delete_activity", "task_update_activity",
                        "story_move_from_project_activity", "story_delete_activity",
                        "story_move_into_project_activity"]:
        # Known but unsupported Pivotal event types
        pass
    else:
        logging.warning("Unknown Pivotal event type: %s" % (event_type,))

    return subject, content

@api_key_only_webhook_view("Pivotal")
@has_request_variables
def api_pivotal_webhook(request, user_profile, client, stream=REQ()):
    # type: (HttpRequest, UserProfile, Client, text_type) -> HttpResponse
    subject = content = None
    try:
        subject, content = api_pivotal_webhook_v3(request, user_profile, stream)
    except AttributeError:
        return json_error(_("Failed to extract data from Pivotal XML response"))
    except:
        # Attempt to parse v5 JSON payload
        try:
            subject, content = api_pivotal_webhook_v5(request, user_profile, stream)
        except AttributeError:
            return json_error(_("Failed to extract data from Pivotal V5 JSON response"))

    if subject is None or content is None:
        return json_error(_("Unable to handle Pivotal payload"))

    check_send_message(user_profile, client, "stream",
                       [stream], subject, content)
    return json_success()

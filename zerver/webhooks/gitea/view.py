# vim:fenc=utf-8

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import (
    OptionalUserSpecifiedTopicStr,
    check_send_webhook_message,
    default_fixture_to_headers,
    get_event_header,
)
from zerver.lib.webhooks.git import (
    TOPIC_WITH_BRANCH_TEMPLATE,
    get_pull_request_event_message,
    get_remove_branch_event_message,
)
from zerver.models import UserProfile

# Gitea is a fork of Gogs, and so the webhook implementation is nearly the same.
from zerver.webhooks.gogs.view import ALL_EVENT_TYPES as GOGS_ALL_EVENT_TYPES
from zerver.webhooks.gogs.view import gogs_webhook_main

ALL_EVENT_TYPES = [*GOGS_ALL_EVENT_TYPES, "delete"]

fixture_to_headers = default_fixture_to_headers("HTTP_X_GITEA_EVENT")


def format_delete_event(payload: WildValue) -> str:
    ref = payload["ref"].tame(check_string)
    ref_type = payload["ref_type"].tame(check_string)
    user_name = payload["sender"]["username"].tame(check_string)
    if ref_type == "branch":
        return get_remove_branch_event_message(user_name, ref)
    return f"{user_name} deleted tag {ref}."


def format_pull_request_event(payload: WildValue, include_title: bool = False) -> str:
    assignee = payload["pull_request"]["assignee"]

    if payload["pull_request"]["merged"].tame(check_bool):
        user_name = payload["pull_request"]["merged_by"]["username"].tame(check_string)
        action = "merged"
    else:
        user_name = payload["sender"]["username"].tame(check_string)
        action = payload["action"].tame(check_string)

    url = payload["pull_request"]["html_url"].tame(check_string)
    number = payload["pull_request"]["number"].tame(check_int)
    target_branch = None
    base_branch = None
    if action != "edited":
        if "head" in payload["pull_request"]:
            target_branch = payload["pull_request"]["head"]["ref"].tame(check_string)
        if "base" in payload["pull_request"]:
            base_branch = payload["pull_request"]["base"]["ref"].tame(check_string)
    title = payload["pull_request"]["title"].tame(check_string) if include_title else None
    stringified_assignee = assignee["login"].tame(check_string) if assignee else None

    return get_pull_request_event_message(
        user_name=user_name,
        action=action,
        url=url,
        number=number,
        target_branch=target_branch,
        base_branch=base_branch,
        title=title,
        assignee=stringified_assignee,
        assignee_updated=stringified_assignee if action == "assigned" else None,
    )


@webhook_view("Gitea", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_gitea_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    branches: str | None = None,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    event = get_event_header(request, "X-Gitea-Event", "Gitea")
    if event == "delete":
        repo = payload["repository"]["name"].tame(check_string)
        ref = payload["ref"].tame(check_string)
        body = format_delete_event(payload)
        topic_name = TOPIC_WITH_BRANCH_TEMPLATE.format(repo=repo, branch=ref)
        check_send_webhook_message(request, user_profile, topic_name, body, event)
        return json_success(request)
    return gogs_webhook_main(
        "Gitea",
        "X-Gitea-Event",
        format_pull_request_event,
        request,
        user_profile,
        payload,
        branches,
        user_specified_topic,
    )

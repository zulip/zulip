# vim:fenc=utf-8
from typing import Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.validator import WildValue, check_bool, check_int, check_string, to_wild_value
from zerver.lib.webhooks.common import get_http_headers_from_filename
from zerver.lib.webhooks.git import get_pull_request_event_message
from zerver.models import UserProfile

# Gitea is a fork of Gogs, and so the webhook implementation is nearly the same.
from zerver.webhooks.gogs.view import gogs_webhook_main

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GITEA_EVENT")


def format_pull_request_event(payload: WildValue, include_title: bool = False) -> str:
    assignee = payload["pull_request"]["assignee"]

    if payload["pull_request"]["merged"].tame(check_bool):
        user_name = payload["pull_request"]["merged_by"]["username"].tame(check_string)
        action = "merged"
    else:
        user_name = payload["pull_request"]["user"]["username"].tame(check_string)
        action = payload["action"].tame(check_string)

    url = payload["pull_request"]["html_url"].tame(check_string)
    number = payload["pull_request"]["number"].tame(check_int)
    target_branch = payload["pull_request"]["head"]["ref"].tame(check_string)
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
    )


@webhook_view("Gitea")
@has_request_variables
def api_gitea_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
    branches: Optional[str] = REQ(default=None),
    user_specified_topic: Optional[str] = REQ("topic", default=None),
) -> HttpResponse:
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

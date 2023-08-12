# vim:fenc=utf-8
from typing import Dict, List, Optional, Protocol

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import (
    OptionalUserSpecifiedTopicStr,
    check_send_webhook_message,
    get_http_headers_from_filename,
    validate_extract_webhook_http_header,
)
from zerver.lib.webhooks.git import (
    TOPIC_WITH_BRANCH_TEMPLATE,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    TOPIC_WITH_RELEASE_TEMPLATE,
    get_create_branch_event_message,
    get_issue_event_message,
    get_pull_request_event_message,
    get_push_commits_event_message,
    get_release_event_message,
)
from zerver.models import UserProfile

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GOGS_EVENT")


def get_issue_url(repo_url: str, issue_nr: int) -> str:
    return f"{repo_url}/issues/{issue_nr}"


def format_push_event(payload: WildValue) -> str:
    user_name = payload["sender"]["username"].tame(check_string)
    compare_url = payload["compare_url"].tame(check_string)
    branch_name = payload["ref"].tame(check_string).replace("refs/heads/", "")
    commits_data = _transform_commits_list_to_common_format(payload["commits"])
    return get_push_commits_event_message(
        user_name=user_name,
        compare_url=compare_url,
        branch_name=branch_name,
        commits_data=commits_data,
    )


def _transform_commits_list_to_common_format(commits: WildValue) -> List[Dict[str, str]]:
    return [
        {
            "name": commit["author"]["username"].tame(check_string)
            or commit["author"]["name"].tame(check_string).split()[0],
            "sha": commit["id"].tame(check_string),
            "url": commit["url"].tame(check_string),
            "message": commit["message"].tame(check_string),
        }
        for commit in commits
    ]


def format_new_branch_event(payload: WildValue) -> str:
    branch_name = payload["ref"].tame(check_string)
    url = "{}/src/{}".format(payload["repository"]["html_url"].tame(check_string), branch_name)

    data = {
        "user_name": payload["sender"]["username"].tame(check_string),
        "url": url,
        "branch_name": branch_name,
    }
    return get_create_branch_event_message(**data)


def format_pull_request_event(payload: WildValue, include_title: bool = False) -> str:
    if payload["pull_request"]["merged"].tame(check_bool):
        user_name = payload["pull_request"]["merged_by"]["username"].tame(check_string)
        action = "merged"
    else:
        user_name = payload["pull_request"]["user"]["username"].tame(check_string)
        action = payload["action"].tame(check_string)
    url = payload["pull_request"]["html_url"].tame(check_string)
    number = payload["pull_request"]["number"].tame(check_int)
    target_branch = None
    base_branch = None
    if action != "edited":
        target_branch = payload["pull_request"]["head_branch"].tame(check_string)
        base_branch = payload["pull_request"]["base_branch"].tame(check_string)
    title = payload["pull_request"]["title"].tame(check_string) if include_title else None

    return get_pull_request_event_message(
        user_name=user_name,
        action=action,
        url=url,
        number=number,
        target_branch=target_branch,
        base_branch=base_branch,
        title=title,
    )


def format_issues_event(payload: WildValue, include_title: bool = False) -> str:
    issue_nr = payload["issue"]["number"].tame(check_int)
    assignee = payload["issue"]["assignee"]
    return get_issue_event_message(
        user_name=payload["sender"]["login"].tame(check_string),
        action=payload["action"].tame(check_string),
        url=get_issue_url(payload["repository"]["html_url"].tame(check_string), issue_nr),
        number=issue_nr,
        message=payload["issue"]["body"].tame(check_string),
        assignee=assignee["login"].tame(check_string) if assignee else None,
        title=payload["issue"]["title"].tame(check_string) if include_title else None,
    )


def format_issue_comment_event(payload: WildValue, include_title: bool = False) -> str:
    action = payload["action"].tame(check_string)
    comment = payload["comment"]
    issue = payload["issue"]

    if action == "created":
        action = "[commented]"
    else:
        action = f"{action} a [comment]"
    action += "({}) on".format(comment["html_url"].tame(check_string))

    return get_issue_event_message(
        user_name=payload["sender"]["login"].tame(check_string),
        action=action,
        url=get_issue_url(
            payload["repository"]["html_url"].tame(check_string), issue["number"].tame(check_int)
        ),
        number=issue["number"].tame(check_int),
        message=comment["body"].tame(check_string),
        title=issue["title"].tame(check_string) if include_title else None,
    )


def format_release_event(payload: WildValue, include_title: bool = False) -> str:
    data = {
        "user_name": payload["release"]["author"]["username"].tame(check_string),
        "action": payload["action"].tame(check_string),
        "tagname": payload["release"]["tag_name"].tame(check_string),
        "release_name": payload["release"]["name"].tame(check_string),
        "url": payload["repository"]["html_url"].tame(check_string),
    }

    return get_release_event_message(**data)


ALL_EVENT_TYPES = ["issue_comment", "issues", "create", "pull_request", "push", "release"]


@webhook_view("Gogs", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_gogs_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
    branches: Optional[str] = None,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    return gogs_webhook_main(
        "Gogs",
        "X-Gogs-Event",
        format_pull_request_event,
        request,
        user_profile,
        payload,
        branches,
        user_specified_topic,
    )


class FormatPullRequestEvent(Protocol):
    def __call__(self, payload: WildValue, include_title: bool) -> str:
        ...


def gogs_webhook_main(
    integration_name: str,
    http_header_name: str,
    format_pull_request_event: FormatPullRequestEvent,
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue,
    branches: Optional[str],
    user_specified_topic: Optional[str],
) -> HttpResponse:
    repo = payload["repository"]["name"].tame(check_string)
    event = validate_extract_webhook_http_header(request, http_header_name, integration_name)
    if event == "push":
        branch = payload["ref"].tame(check_string).replace("refs/heads/", "")
        if branches is not None and branch not in branches.split(","):
            return json_success(request)
        body = format_push_event(payload)
        topic = TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=repo,
            branch=branch,
        )
    elif event == "create":
        body = format_new_branch_event(payload)
        topic = TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=repo,
            branch=payload["ref"].tame(check_string),
        )
    elif event == "pull_request":
        body = format_pull_request_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=repo,
            type="PR",
            id=payload["pull_request"]["id"].tame(check_int),
            title=payload["pull_request"]["title"].tame(check_string),
        )
    elif event == "issues":
        body = format_issues_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=repo,
            type="issue",
            id=payload["issue"]["number"].tame(check_int),
            title=payload["issue"]["title"].tame(check_string),
        )
    elif event == "issue_comment":
        body = format_issue_comment_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=repo,
            type="issue",
            id=payload["issue"]["number"].tame(check_int),
            title=payload["issue"]["title"].tame(check_string),
        )
    elif event == "release":
        body = format_release_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_RELEASE_TEMPLATE.format(
            repo=repo,
            tag=payload["release"]["tag_name"].tame(check_string),
            title=payload["release"]["name"].tame(check_string),
        )

    else:
        raise UnsupportedWebhookEventTypeError(event)

    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)

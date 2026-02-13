from collections.abc import Callable
from typing import Protocol

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
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
    CONTENT_MESSAGE_TEMPLATE,
    PULL_REQUEST_COMMENT_TEMPLATE,
    REMOVE_BRANCH_MESSAGE_TEMPLATE,
    REMOVE_BRANCH_TOPIC_TEMPLATE,
    REMOVE_TAG_MESSAGE_TEMPLATE,
    REMOVE_TAG_TOPIC_TEMPLATE,
    TOPIC_WITH_BRANCH_TEMPLATE,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    TOPIC_WITH_RELEASE_TEMPLATE,
    get_create_branch_event_message,
    get_issue_event_message,
    get_pull_request_event_message,
    get_push_commits_event_message,
    get_release_event_message,
    is_branch_name_notifiable,
)
from zerver.models import UserProfile

fixture_to_headers = default_fixture_to_headers("HTTP_X_GOGS_EVENT")


class Helper:
    def __init__(
        self,
        payload: WildValue,
        branches: str | None,
        user_specified_topic: str | None,
        repo: str,
        format_pull_request_event: "FormatPullRequestEvent",
    ) -> None:
        self.payload = payload
        self.branches = branches
        self.user_specified_topic = user_specified_topic
        self.repo = repo
        self.format_pull_request_event = format_pull_request_event


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


def _transform_commits_list_to_common_format(commits: WildValue) -> list[dict[str, str]]:
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
    stringified_assignee = (
        payload["pull_request"]["assignee"]["login"].tame(check_string)
        if payload["action"] and payload["pull_request"]["assignee"]
        else None
    )

    return get_pull_request_event_message(
        user_name=user_name,
        action=action,
        url=url,
        number=number,
        target_branch=target_branch,
        base_branch=base_branch,
        title=title,
        assignee_updated=stringified_assignee,
    )


def format_issues_event(payload: WildValue, include_title: bool = False) -> str:
    issue_nr = payload["issue"]["number"].tame(check_int)
    assignee = payload["issue"]["assignee"]
    stringified_assignee = assignee["login"].tame(check_string) if assignee else None
    action = payload["action"].tame(check_string)
    return get_issue_event_message(
        user_name=payload["sender"]["login"].tame(check_string),
        action=payload["action"].tame(check_string),
        url=get_issue_url(payload["repository"]["html_url"].tame(check_string), issue_nr),
        number=issue_nr,
        message=payload["issue"]["body"].tame(check_string),
        assignee=stringified_assignee,
        title=payload["issue"]["title"].tame(check_string) if include_title else None,
        assignee_updated=stringified_assignee if action == "assigned" else None,
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


def handle_push_event(helper: Helper) -> tuple[str | None, str | None]:
    branch = helper.payload["ref"].tame(check_string).replace("refs/heads/", "")
    if not is_branch_name_notifiable(branch, helper.branches):
        return None, None
    body = format_push_event(helper.payload)
    topic_name = TOPIC_WITH_BRANCH_TEMPLATE.format(
        repo=helper.repo,
        branch=branch,
    )
    return topic_name, body


def handle_create_event(helper: Helper) -> tuple[str | None, str | None]:
    body = format_new_branch_event(helper.payload)
    topic_name = TOPIC_WITH_BRANCH_TEMPLATE.format(
        repo=helper.repo,
        branch=helper.payload["ref"].tame(check_string),
    )
    return topic_name, body


def handle_pull_request_event(helper: Helper) -> tuple[str | None, str | None]:
    body = helper.format_pull_request_event(
        helper.payload,
        include_title=helper.user_specified_topic is not None,
    )
    topic_name = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
        repo=helper.repo,
        type="PR",
        id=helper.payload["pull_request"]["id"].tame(check_int),
        title=helper.payload["pull_request"]["title"].tame(check_string),
    )
    return topic_name, body


def handle_issues_event(helper: Helper) -> tuple[str | None, str | None]:
    body = format_issues_event(
        helper.payload,
        include_title=helper.user_specified_topic is not None,
    )
    topic_name = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
        repo=helper.repo,
        type="issue",
        id=helper.payload["issue"]["number"].tame(check_int),
        title=helper.payload["issue"]["title"].tame(check_string),
    )
    return topic_name, body


def handle_issue_comment_event(helper: Helper) -> tuple[str | None, str | None]:
    # Used for handling comments in PR
    url = helper.payload["comment"]["html_url"].tame(check_string)
    pr_url = helper.payload["comment"]["html_url"].tame(check_string).split("#")[0]
    if url.split("/")[-2] == "pulls":
        topic, body = handle_pr_comment(helper, pr_url)
        return topic, body

    # Used for handling comments in issue
    body = format_issue_comment_event(
        helper.payload,
        include_title=helper.user_specified_topic is not None,
    )
    topic_name = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
        repo=helper.payload["repository"]["name"].tame(check_string),
        type="issue",
        id=helper.payload["issue"]["number"].tame(check_int),
        title=helper.payload["issue"]["title"].tame(check_string),
    )
    return topic_name, body


def handle_release_event(helper: Helper) -> tuple[str | None, str | None]:
    body = format_release_event(
        helper.payload,
        include_title=helper.user_specified_topic is not None,
    )
    topic_name = TOPIC_WITH_RELEASE_TEMPLATE.format(
        repo=helper.repo,
        tag=helper.payload["release"]["tag_name"].tame(check_string),
        title=helper.payload["release"]["name"].tame(check_string),
    )
    return topic_name, body


def handle_pr_comment(helper: Helper, pr_url: str | None = None) -> tuple[str | None, str | None]:
    """
    Handle a comment from a GOGS webhook payload to determine if it's a pull request or issue comment.

    Args:
        helper: Helper object providing access to the JSON payload.
        pr_url: Optional pull request URL to override or validate the comment's context.

    Returns:
        Tuple containing:
        - Comment type ("pull_request" or "issue") or None if undetermined.
        - Relevant URL (pull request or issue URL) or None if not available.
    """
    action = helper.payload["action"].tame(check_string)
    pr_url = pr_url if pr_url else helper.payload["issue"]["html_url"].tame(check_string)
    action = helper.payload["action"].tame(check_string)
    user_name = helper.payload["sender"]["login"].tame(check_string)
    comment_url = helper.payload["comment"]["html_url"].tame(check_string)
    comment_body = helper.payload["comment"]["body"].tame(check_string)
    pr_number = helper.payload["issue"]["number"].tame(check_int)
    pr_title = f'"{helper.payload["issue"]["title"].tame(check_string)}"'
    changes = helper.payload.get("changes", {}).get("body", {}).get("from", None)

    if action == "created":
        action_text = "commented"
        message = comment_body
    elif action == "deleted":
        action_text = "deleted a comment"
        message = comment_body
    elif action == "edited":
        action_text = "edited a comment"
        from_text = changes.tame(check_string).strip() if changes else "unknown"
        message = f'from "{from_text}" to "{comment_body}"'

    # Pass empty assignee since it's not used in the Gitea payload for comments
    body = PULL_REQUEST_COMMENT_TEMPLATE.format(
        user_name=f"{user_name}",
        action=action_text,
        type="PR",
        id=f" #{pr_number}",
        title=pr_title,
        comment_url=comment_url,
        url=pr_url,
    )

    if message:
        body += CONTENT_MESSAGE_TEMPLATE.format(message=message)

    topic_type = "PR comment"
    topic_name = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
        repo=helper.payload["repository"]["name"].tame(check_string),
        type=topic_type,
        id=pr_number,
        title="",  # Omit title from topic for simplicity
    )
    return topic_name, body


def get_remove_branch_event_message(user_name: str, branch_name: str) -> str:
    return REMOVE_BRANCH_MESSAGE_TEMPLATE.format(
        user_name=user_name, branch_name=f"`{branch_name}`"
    )


def get_remove_tag_event_message(user_name: str, tag_name: str) -> str:
    return REMOVE_TAG_MESSAGE_TEMPLATE.format(user_name=user_name, tag_name=f"`{tag_name}`")


def handle_delete_event(helper: Helper) -> tuple[str | None, str | None]:
    user_name = helper.payload["sender"]["login"].tame(check_string)
    ref = helper.payload["ref"].tame(check_string)
    repo_name = helper.repo

    if helper.payload["ref_type"].tame(check_string) == "branch":
        body = get_remove_branch_event_message(
            user_name=user_name,
            branch_name=ref,
        )
        topic_name = REMOVE_BRANCH_TOPIC_TEMPLATE.format(
            repo=repo_name,
            branch_name=ref,
        )
    elif helper.payload["ref_type"].tame(check_string) == "tag":
        body = get_remove_tag_event_message(
            user_name=user_name,
            tag_name=ref,
        )
        topic_name = REMOVE_TAG_TOPIC_TEMPLATE.format(
            repo=repo_name,
            tag_name=ref,
        )
    return topic_name, body


GOGS_EVENT_FUNCTION_MAPPER: dict[str, Callable[[Helper], tuple[str | None, str | None]]] = {
    "push": handle_push_event,
    "create": handle_create_event,
    "pull_request": handle_pull_request_event,
    "issues": handle_issues_event,
    "issue_comment": handle_issue_comment_event,
    "release": handle_release_event,
    "delete": handle_delete_event,
    "pull_request_comment": handle_pr_comment,
}

ALL_EVENT_TYPES = list(GOGS_EVENT_FUNCTION_MAPPER.keys())


@webhook_view("Gogs", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_gogs_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    branches: str | None = None,
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
    def __call__(self, payload: WildValue, include_title: bool) -> str: ...


def gogs_webhook_main(
    integration_name: str,
    http_header_name: str,
    format_pull_request_event: FormatPullRequestEvent,
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue,
    branches: str | None,
    user_specified_topic: str | None,
) -> HttpResponse:
    repo = payload["repository"]["name"].tame(check_string)
    event = get_event_header(request, http_header_name, integration_name)
    helper = Helper(
        payload=payload,
        branches=branches,
        user_specified_topic=user_specified_topic,
        repo=repo,
        format_pull_request_event=format_pull_request_event,
    )

    handler = GOGS_EVENT_FUNCTION_MAPPER.get(event)
    if handler:
        topic_name, body = handler(helper)
        if topic_name and body:
            check_send_webhook_message(request, user_profile, topic_name, body, event)
            return json_success(request)
        elif event == "push":
            # Specific handling for push with ignored branch
            return json_success(request)
        else:
            raise UnsupportedWebhookEventTypeError(event)
    else:
        raise UnsupportedWebhookEventTypeError(event)

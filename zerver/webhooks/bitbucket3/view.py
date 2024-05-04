import string
from typing import Dict, List, Optional, Protocol

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import (
    OptionalUserSpecifiedTopicStr,
    check_send_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.lib.webhooks.git import (
    TOPIC_WITH_BRANCH_TEMPLATE,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    get_commits_comment_action_message,
    get_create_branch_event_message,
    get_pull_request_event_message,
    get_push_tag_event_message,
    get_remove_branch_event_message,
)
from zerver.models import UserProfile
from zerver.webhooks.bitbucket2.view import BITBUCKET_REPO_UPDATED_CHANGED, BITBUCKET_TOPIC_TEMPLATE

BITBUCKET_FORK_BODY = (
    "User {display_name}(login: {username}) forked the repository into [{fork_name}]({fork_url})."
)
BRANCH_UPDATED_MESSAGE_TEMPLATE = "{user_name} pushed to branch {branch_name}. Head is now {head}."
PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE = (
    '{user_name} marked [PR #{number}]({url}) as "needs work".'
)
PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE_WITH_TITLE = """
{user_name} marked [PR #{number} {title}]({url}) as \"needs work\".
""".strip()
PULL_REQUEST_REASSIGNED_TEMPLATE = "{user_name} reassigned [PR #{number}]({url}) to {assignees}."
PULL_REQUEST_REASSIGNED_TEMPLATE_WITH_TITLE = """
{user_name} reassigned [PR #{number} {title}]({url}) to {assignees}.
""".strip()
PULL_REQUEST_REASSIGNED_TO_NONE_TEMPLATE = (
    "{user_name} removed all reviewers from [PR #{number}]({url})."
)
PULL_REQUEST_REASSIGNED_TO_NONE_TEMPLATE_WITH_TITLE = """
{user_name} removed all reviewers from [PR #{number} {title}]({url})
""".strip()
PULL_REQUEST_OPENED_OR_MODIFIED_TEMPLATE_WITH_REVIEWERS = """
{user_name} {action} [PR #{number}]({url}) from `{source}` to \
`{destination}` (assigned to {assignees} for review)
""".strip()
PULL_REQUEST_OPENED_OR_MODIFIED_TEMPLATE_WITH_REVIEWERS_WITH_TITLE = """
{user_name} {action} [PR #{number} {title}]({url}) from `{source}` to \
`{destination}` (assigned to {assignees} for review)
""".strip()


def fixture_to_headers(fixture_name: str) -> Dict[str, str]:
    if fixture_name == "diagnostics_ping":
        return {"HTTP_X_EVENT_KEY": "diagnostics:ping"}
    return {}


def get_user_name(payload: WildValue) -> str:
    user_name = "[{name}]({url})".format(
        name=payload["actor"]["name"].tame(check_string),
        url=payload["actor"]["links"]["self"][0]["href"].tame(check_string),
    )
    return user_name


def ping_handler(
    payload: WildValue,
    branches: Optional[str],
    include_title: Optional[str],
) -> List[Dict[str, str]]:
    if include_title:
        topic_name = include_title
    else:
        topic_name = "Bitbucket Server Ping"
    body = "Congratulations! The Bitbucket Server webhook was configured successfully!"
    return [{"topic": topic_name, "body": body}]


def repo_comment_handler(
    action: str,
    payload: WildValue,
    branches: Optional[str],
    include_title: Optional[str],
) -> List[Dict[str, str]]:
    repo_name = payload["repository"]["name"].tame(check_string)
    topic_name = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    sha = payload["commit"].tame(check_string)
    commit_url = payload["repository"]["links"]["self"][0]["href"].tame(check_string)[
        : -len("browse")
    ]
    commit_url += f"commits/{sha}"
    message = payload["comment"]["text"].tame(check_string)
    if action == "deleted their comment":
        message = f"~~{message}~~"
    body = get_commits_comment_action_message(
        user_name=get_user_name(payload),
        action=action,
        commit_url=commit_url,
        sha=sha,
        message=message,
    )
    return [{"topic": topic_name, "body": body}]


def repo_forked_handler(
    payload: WildValue,
    branches: Optional[str],
    include_title: Optional[str],
) -> List[Dict[str, str]]:
    repo_name = payload["repository"]["origin"]["name"].tame(check_string)
    topic_name = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    body = BITBUCKET_FORK_BODY.format(
        display_name=payload["actor"]["displayName"].tame(check_string),
        username=get_user_name(payload),
        fork_name=payload["repository"]["name"].tame(check_string),
        fork_url=payload["repository"]["links"]["self"][0]["href"].tame(check_string),
    )
    return [{"topic": topic_name, "body": body}]


def repo_modified_handler(
    payload: WildValue,
    branches: Optional[str],
    include_title: Optional[str],
) -> List[Dict[str, str]]:
    topic_name_new = BITBUCKET_TOPIC_TEMPLATE.format(
        repository_name=payload["new"]["name"].tame(check_string)
    )
    new_name = payload["new"]["name"].tame(check_string)
    body = BITBUCKET_REPO_UPDATED_CHANGED.format(
        actor=get_user_name(payload),
        change="name",
        repo_name=payload["old"]["name"].tame(check_string),
        old=payload["old"]["name"].tame(check_string),
        new=new_name,
    )  # As of writing this, the only change we'd be notified about is a name change.
    punctuation = "." if new_name[-1] not in string.punctuation else ""
    body = f"{body}{punctuation}"
    return [{"topic": topic_name_new, "body": body}]


def repo_push_branch_data(payload: WildValue, change: WildValue) -> Dict[str, str]:
    event_type = change["type"].tame(check_string)
    repo_name = payload["repository"]["name"].tame(check_string)
    user_name = get_user_name(payload)
    branch_name = change["ref"]["displayId"].tame(check_string)
    branch_head = change["toHash"].tame(check_string)

    if event_type == "ADD":
        body = get_create_branch_event_message(
            user_name=user_name,
            url=None,
            branch_name=branch_name,
        )
    elif event_type == "UPDATE":
        body = BRANCH_UPDATED_MESSAGE_TEMPLATE.format(
            user_name=user_name,
            branch_name=branch_name,
            head=branch_head,
        )
    elif event_type == "DELETE":
        body = get_remove_branch_event_message(user_name, branch_name)
    else:
        message = "{}.{}".format(payload["eventKey"].tame(check_string), event_type)  # nocoverage
        raise UnsupportedWebhookEventTypeError(message)

    topic_name = TOPIC_WITH_BRANCH_TEMPLATE.format(repo=repo_name, branch=branch_name)
    return {"topic": topic_name, "body": body}


def repo_push_tag_data(payload: WildValue, change: WildValue) -> Dict[str, str]:
    event_type = change["type"].tame(check_string)
    repo_name = payload["repository"]["name"].tame(check_string)
    tag_name = change["ref"]["displayId"].tame(check_string)

    if event_type == "ADD":
        action = "pushed"
    elif event_type == "DELETE":
        action = "removed"
    else:
        message = "{}.{}".format(payload["eventKey"].tame(check_string), event_type)  # nocoverage
        raise UnsupportedWebhookEventTypeError(message)

    topic_name = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    body = get_push_tag_event_message(get_user_name(payload), tag_name, action=action)
    return {"topic": topic_name, "body": body}


def repo_push_handler(
    payload: WildValue,
    branches: Optional[str],
    include_title: Optional[str],
) -> List[Dict[str, str]]:
    data = []
    for change in payload["changes"]:
        event_target_type = change["ref"]["type"].tame(check_string)
        if event_target_type == "BRANCH":
            branch = change["ref"]["displayId"].tame(check_string)
            if branches and branch not in branches:
                continue
            data.append(repo_push_branch_data(payload, change))
        elif event_target_type == "TAG":
            data.append(repo_push_tag_data(payload, change))
        else:
            message = "{}.{}".format(
                payload["eventKey"].tame(check_string), event_target_type
            )  # nocoverage
            raise UnsupportedWebhookEventTypeError(message)
    return data


def get_assignees_string(pr: WildValue) -> Optional[str]:
    reviewers = []
    for reviewer in pr["reviewers"]:
        name = reviewer["user"]["name"].tame(check_string)
        link = reviewer["user"]["links"]["self"][0]["href"].tame(check_string)
        reviewers.append(f"[{name}]({link})")
    if len(reviewers) == 0:
        assignees = None
    elif len(reviewers) == 1:
        assignees = reviewers[0]
    else:
        assignees = ", ".join(reviewers[:-1]) + " and " + reviewers[-1]
    return assignees


def get_pr_topic(repo: str, type: str, id: int, title: str) -> str:
    return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(repo=repo, type=type, id=id, title=title)


def get_simple_pr_body(payload: WildValue, action: str, include_title: Optional[str]) -> str:
    pr = payload["pullRequest"]
    return get_pull_request_event_message(
        user_name=get_user_name(payload),
        action=action,
        url=pr["links"]["self"][0]["href"].tame(check_string),
        number=pr["id"].tame(check_int),
        title=pr["title"].tame(check_string) if include_title else None,
    )


def get_pr_opened_or_modified_body(
    payload: WildValue, action: str, include_title: Optional[str]
) -> str:
    pr = payload["pullRequest"]
    description = pr.get("description").tame(check_none_or(check_string))
    target_branch = None
    base_branch = None
    if action == "opened":
        target_branch = pr["fromRef"]["displayId"].tame(check_string)
        base_branch = pr["toRef"]["displayId"].tame(check_string)
    reviewers_string = get_assignees_string(pr)

    return get_pull_request_event_message(
        user_name=get_user_name(payload),
        action=action,
        url=pr["links"]["self"][0]["href"].tame(check_string),
        number=pr["id"].tame(check_int),
        target_branch=target_branch,
        base_branch=base_branch,
        message=description,
        reviewer=reviewers_string if reviewers_string else None,
        title=pr["title"].tame(check_string) if include_title else None,
    )


def get_pr_merged_body(payload: WildValue, action: str, include_title: Optional[str]) -> str:
    pr = payload["pullRequest"]
    return get_pull_request_event_message(
        user_name=get_user_name(payload),
        action=action,
        url=pr["links"]["self"][0]["href"].tame(check_string),
        number=pr["id"].tame(check_int),
        target_branch=pr["fromRef"]["displayId"].tame(check_string),
        base_branch=pr["toRef"]["displayId"].tame(check_string),
        title=pr["title"].tame(check_string) if include_title else None,
    )


def get_pr_needs_work_body(payload: WildValue, include_title: Optional[str]) -> str:
    pr = payload["pullRequest"]
    if not include_title:
        return PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE.format(
            user_name=get_user_name(payload),
            number=pr["id"].tame(check_int),
            url=pr["links"]["self"][0]["href"].tame(check_string),
        )
    return PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE_WITH_TITLE.format(
        user_name=get_user_name(payload),
        number=pr["id"].tame(check_int),
        url=pr["links"]["self"][0]["href"].tame(check_string),
        title=pr["title"].tame(check_string),
    )


def get_pr_reassigned_body(payload: WildValue, include_title: Optional[str]) -> str:
    pr = payload["pullRequest"]
    assignees_string = get_assignees_string(pr)
    if not assignees_string:
        if not include_title:
            return PULL_REQUEST_REASSIGNED_TO_NONE_TEMPLATE.format(
                user_name=get_user_name(payload),
                number=pr["id"].tame(check_int),
                url=pr["links"]["self"][0]["href"].tame(check_string),
            )
        punctuation = "." if pr["title"].tame(check_string)[-1] not in string.punctuation else ""
        message = PULL_REQUEST_REASSIGNED_TO_NONE_TEMPLATE_WITH_TITLE.format(
            user_name=get_user_name(payload),
            number=pr["id"].tame(check_int),
            url=pr["links"]["self"][0]["href"].tame(check_string),
            title=pr["title"].tame(check_string),
        )
        message = f"{message}{punctuation}"
        return message
    if not include_title:
        return PULL_REQUEST_REASSIGNED_TEMPLATE.format(
            user_name=get_user_name(payload),
            number=pr["id"].tame(check_int),
            url=pr["links"]["self"][0]["href"].tame(check_string),
            assignees=assignees_string,
        )
    return PULL_REQUEST_REASSIGNED_TEMPLATE_WITH_TITLE.format(
        user_name=get_user_name(payload),
        number=pr["id"].tame(check_int),
        url=pr["links"]["self"][0]["href"].tame(check_string),
        assignees=assignees_string,
        title=pr["title"].tame(check_string),
    )


def pr_handler(
    action: str,
    payload: WildValue,
    branches: Optional[str],
    include_title: Optional[str],
) -> List[Dict[str, str]]:
    pr = payload["pullRequest"]
    topic_name = get_pr_topic(
        pr["toRef"]["repository"]["name"].tame(check_string),
        type="PR",
        id=pr["id"].tame(check_int),
        title=pr["title"].tame(check_string),
    )
    if action in ["opened", "modified"]:
        body = get_pr_opened_or_modified_body(payload, action, include_title)
    elif action == "merged":
        body = get_pr_merged_body(payload, action, include_title)
    elif action == "needs_work":
        body = get_pr_needs_work_body(payload, include_title)
    elif action == "reviewers_updated":
        body = get_pr_reassigned_body(payload, include_title)
    else:
        body = get_simple_pr_body(payload, action, include_title)

    return [{"topic": topic_name, "body": body}]


def pr_comment_handler(
    action: str,
    payload: WildValue,
    branches: Optional[str],
    include_title: Optional[str],
) -> List[Dict[str, str]]:
    pr = payload["pullRequest"]
    topic_name = get_pr_topic(
        pr["toRef"]["repository"]["name"].tame(check_string),
        type="PR",
        id=pr["id"].tame(check_int),
        title=pr["title"].tame(check_string),
    )
    message = payload["comment"]["text"].tame(check_string)
    if action == "deleted their comment on":
        message = f"~~{message}~~"
    body = get_pull_request_event_message(
        user_name=get_user_name(payload),
        action=action,
        url=pr["links"]["self"][0]["href"].tame(check_string),
        number=pr["id"].tame(check_int),
        message=message,
        title=pr["title"].tame(check_string) if include_title else None,
    )

    return [{"topic": topic_name, "body": body}]


class EventHandler(Protocol):
    def __call__(
        self, payload: WildValue, branches: Optional[str], include_title: Optional[str]
    ) -> List[Dict[str, str]]: ...


EVENT_HANDLER_MAP: Dict[str, EventHandler] = {
    "diagnostics:ping": ping_handler,
    "repo:comment:added": partial(repo_comment_handler, "commented"),
    "repo:comment:edited": partial(repo_comment_handler, "edited their comment"),
    "repo:comment:deleted": partial(repo_comment_handler, "deleted their comment"),
    "repo:forked": repo_forked_handler,
    "repo:modified": repo_modified_handler,
    "repo:refs_changed": repo_push_handler,
    "pr:comment:added": partial(pr_comment_handler, "commented on"),
    "pr:comment:edited": partial(pr_comment_handler, "edited their comment on"),
    "pr:comment:deleted": partial(pr_comment_handler, "deleted their comment on"),
    "pr:declined": partial(pr_handler, "declined"),
    "pr:deleted": partial(pr_handler, "deleted"),
    "pr:merged": partial(pr_handler, "merged"),
    "pr:modified": partial(pr_handler, "modified"),
    "pr:opened": partial(pr_handler, "opened"),
    "pr:reviewer:approved": partial(pr_handler, "approved"),
    "pr:reviewer:needs_work": partial(pr_handler, "needs_work"),
    "pr:reviewer:updated": partial(pr_handler, "reviewers_updated"),
    "pr:reviewer:unapproved": partial(pr_handler, "unapproved"),
}

ALL_EVENT_TYPES = list(EVENT_HANDLER_MAP.keys())


@webhook_view("Bitbucket3", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_bitbucket3_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    branches: Optional[str] = None,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    eventkey: Optional[str]
    if "eventKey" in payload:
        eventkey = payload["eventKey"].tame(check_string)
    else:
        eventkey = validate_extract_webhook_http_header(request, "X-Event-Key", "BitBucket")
    handler = EVENT_HANDLER_MAP.get(eventkey)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(eventkey)

    data = handler(payload, branches=branches, include_title=user_specified_topic)
    for element in data:
        check_send_webhook_message(
            request,
            user_profile,
            element["topic"],
            element["body"],
            eventkey,
            unquote_url_parameters=True,
        )

    return json_success(request)

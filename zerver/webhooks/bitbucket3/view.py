import string
from functools import partial
from inspect import signature
from typing import Any, Callable, Dict, List, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import (
    CONTENT_MESSAGE_TEMPLATE,
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

BITBUCKET_FORK_BODY = "User {display_name}(login: {username}) forked the repository into [{fork_name}]({fork_url})."
BRANCH_UPDATED_MESSAGE_TEMPLATE = "{user_name} pushed to branch {branch_name}. Head is now {head}."
PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE = "{user_name} marked [PR #{number}]({url}) as \"needs work\"."
PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE_WITH_TITLE = """
{user_name} marked [PR #{number} {title}]({url}) as \"needs work\".
""".strip()
PULL_REQUEST_REASSIGNED_TEMPLATE = "{user_name} reassigned [PR #{number}]({url}) to {assignees}."
PULL_REQUEST_REASSIGNED_TEMPLATE_WITH_TITLE = """
{user_name} reassigned [PR #{number} {title}]({url}) to {assignees}.
""".strip()
PULL_REQUEST_REASSIGNED_TO_NONE_TEMPLATE = "{user_name} removed all reviewers from [PR #{number}]({url})."
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

def get_user_name(payload: Dict[str, Any]) -> str:
    user_name = "[{name}]({url})".format(name=payload["actor"]["name"],
                                         url=payload["actor"]["links"]["self"][0]["href"])
    return user_name

def ping_handler(payload: Dict[str, Any], include_title: Optional[str]=None,
                 ) -> List[Dict[str, str]]:
    if include_title:
        subject = include_title
    else:
        subject = "Bitbucket Server Ping"
    body = "Congratulations! The Bitbucket Server webhook was configured successfully!"
    return [{"subject": subject, "body": body}]

def repo_comment_handler(payload: Dict[str, Any], action: str) -> List[Dict[str, str]]:
    repo_name = payload["repository"]["name"]
    subject = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    sha = payload["commit"]
    commit_url = payload["repository"]["links"]["self"][0]["href"][: -len("browse")]
    commit_url += f"commits/{sha}"
    message = payload["comment"]["text"]
    if action == "deleted their comment":
        message = f"~~{message}~~"
    body = get_commits_comment_action_message(
        user_name=get_user_name(payload),
        action=action,
        commit_url=commit_url,
        sha=sha,
        message=message,
    )
    return [{"subject": subject, "body": body}]

def repo_forked_handler(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    repo_name = payload["repository"]["origin"]["name"]
    subject = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    body = BITBUCKET_FORK_BODY.format(
        display_name=payload["actor"]["displayName"],
        username=get_user_name(payload),
        fork_name=payload["repository"]["name"],
        fork_url=payload["repository"]["links"]["self"][0]["href"],
    )
    return [{"subject": subject, "body": body}]

def repo_modified_handler(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    subject_new = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=payload["new"]["name"])
    new_name = payload['new']['name']
    body = BITBUCKET_REPO_UPDATED_CHANGED.format(
        actor=get_user_name(payload),
        change="name",
        repo_name=payload["old"]["name"],
        old=payload["old"]["name"],
        new=new_name,
    )  # As of writing this, the only change we'd be notified about is a name change.
    punctuation = '.' if new_name[-1] not in string.punctuation else ''
    body = f"{body}{punctuation}"
    return [{"subject": subject_new, "body": body}]

def repo_push_branch_data(payload: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, str]:
    event_type = change["type"]
    repo_name = payload["repository"]["name"]
    user_name = get_user_name(payload)
    branch_name = change["ref"]["displayId"]
    branch_head = change["toHash"]

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
        message = "{}.{}".format(payload["eventKey"], event_type)  # nocoverage
        raise UnsupportedWebhookEventType(message)

    subject = TOPIC_WITH_BRANCH_TEMPLATE.format(repo=repo_name, branch=branch_name)
    return {"subject": subject, "body": body}

def repo_push_tag_data(payload: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, str]:
    event_type = change["type"]
    repo_name = payload["repository"]["name"]
    tag_name = change["ref"]["displayId"]

    if event_type == "ADD":
        action = "pushed"
    elif event_type == "DELETE":
        action = "removed"
    else:
        message = "{}.{}".format(payload["eventKey"], event_type)  # nocoverage
        raise UnsupportedWebhookEventType(message)

    subject = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    body = get_push_tag_event_message(get_user_name(payload), tag_name, action=action)
    return {"subject": subject, "body": body}

def repo_push_handler(payload: Dict[str, Any], branches: Optional[str]=None,
                      ) -> List[Dict[str, str]]:
    data = []
    for change in payload["changes"]:
        event_target_type = change["ref"]["type"]
        if event_target_type == "BRANCH":
            branch = change["ref"]["displayId"]
            if branches:
                if branch not in branches:
                    continue
            data.append(repo_push_branch_data(payload, change))
        elif event_target_type == "TAG":
            data.append(repo_push_tag_data(payload, change))
        else:
            message = "{}.{}".format(payload["eventKey"], event_target_type)  # nocoverage
            raise UnsupportedWebhookEventType(message)
    return data

def get_assignees_string(pr: Dict[str, Any]) -> Optional[str]:
    reviewers = []
    for reviewer in pr["reviewers"]:
        name = reviewer["user"]["name"]
        link = reviewer["user"]["links"]["self"][0]["href"]
        reviewers.append(f"[{name}]({link})")
    if len(reviewers) == 0:
        assignees = None
    elif len(reviewers) == 1:
        assignees = reviewers[0]
    else:
        assignees = ", ".join(reviewers[:-1]) + " and " + reviewers[-1]
    return assignees

def get_pr_subject(repo: str, type: str, id: str, title: str) -> str:
    return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(repo=repo, type=type, id=id, title=title)

def get_simple_pr_body(payload: Dict[str, Any], action: str, include_title: Optional[bool]) -> str:
    pr = payload["pullRequest"]
    return get_pull_request_event_message(
        user_name=get_user_name(payload),
        action=action,
        url=pr["links"]["self"][0]["href"],
        number=pr["id"],
        title=pr["title"] if include_title else None,
    )

def get_pr_opened_or_modified_body(payload: Dict[str, Any], action: str,
                                   include_title: Optional[bool]) -> str:
    pr = payload["pullRequest"]
    description = pr.get("description")
    assignees_string = get_assignees_string(pr)
    if assignees_string:
        # Then use the custom message template for this particular integration so that we can
        # specify the reviewers at the end of the message (but before the description/message).
        parameters = {"user_name": get_user_name(payload),
                      "action": action,
                      "url": pr["links"]["self"][0]["href"],
                      "number": pr["id"],
                      "source": pr["fromRef"]["displayId"],
                      "destination": pr["toRef"]["displayId"],
                      "message": description,
                      "assignees": assignees_string,
                      "title": pr["title"] if include_title else None}
        if include_title:
            body = PULL_REQUEST_OPENED_OR_MODIFIED_TEMPLATE_WITH_REVIEWERS_WITH_TITLE.format(
                **parameters,
            )
        else:
            body = PULL_REQUEST_OPENED_OR_MODIFIED_TEMPLATE_WITH_REVIEWERS.format(**parameters)
        punctuation = ':' if description else '.'
        body = f"{body}{punctuation}"
        if description:
            body += '\n' + CONTENT_MESSAGE_TEMPLATE.format(message=description)
        return body
    return get_pull_request_event_message(
        user_name=get_user_name(payload),
        action=action,
        url=pr["links"]["self"][0]["href"],
        number=pr["id"],
        target_branch=pr["fromRef"]["displayId"],
        base_branch=pr["toRef"]["displayId"],
        message=pr.get("description"),
        assignee=assignees_string if assignees_string else None,
        title=pr["title"] if include_title else None,
    )

def get_pr_needs_work_body(payload: Dict[str, Any], include_title: Optional[bool]) -> str:
    pr = payload["pullRequest"]
    if not include_title:
        return PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE.format(
            user_name=get_user_name(payload),
            number=pr["id"],
            url=pr["links"]["self"][0]["href"],
        )
    return PULL_REQUEST_MARKED_AS_NEEDS_WORK_TEMPLATE_WITH_TITLE.format(
        user_name=get_user_name(payload),
        number=pr["id"],
        url=pr["links"]["self"][0]["href"],
        title=pr["title"],
    )

def get_pr_reassigned_body(payload: Dict[str, Any], include_title: Optional[bool]) -> str:
    pr = payload["pullRequest"]
    assignees_string = get_assignees_string(pr)
    if not assignees_string:
        if not include_title:
            return PULL_REQUEST_REASSIGNED_TO_NONE_TEMPLATE.format(
                user_name=get_user_name(payload),
                number=pr["id"],
                url=pr["links"]["self"][0]["href"],
            )
        punctuation = '.' if pr['title'][-1] not in string.punctuation else ''
        message = PULL_REQUEST_REASSIGNED_TO_NONE_TEMPLATE_WITH_TITLE.format(
            user_name=get_user_name(payload),
            number=pr["id"],
            url=pr["links"]["self"][0]["href"],
            title=pr["title"],
        )
        message = f"{message}{punctuation}"
        return message
    if not include_title:
        return PULL_REQUEST_REASSIGNED_TEMPLATE.format(
            user_name=get_user_name(payload),
            number=pr["id"],
            url=pr["links"]["self"][0]["href"],
            assignees=assignees_string,
        )
    return PULL_REQUEST_REASSIGNED_TEMPLATE_WITH_TITLE.format(
        user_name=get_user_name(payload),
        number=pr["id"],
        url=pr["links"]["self"][0]["href"],
        assignees=assignees_string,
        title=pr["title"],
    )

def pr_handler(payload: Dict[str, Any], action: str,
               include_title: bool=False) -> List[Dict[str, str]]:
    pr = payload["pullRequest"]
    subject = get_pr_subject(pr["toRef"]["repository"]["name"], type="PR", id=pr["id"],
                             title=pr["title"])
    if action in ["opened", "modified"]:
        body = get_pr_opened_or_modified_body(payload, action, include_title)
    elif action == "needs_work":
        body = get_pr_needs_work_body(payload, include_title)
    elif action == "reviewers_updated":
        body = get_pr_reassigned_body(payload, include_title)
    else:
        body = get_simple_pr_body(payload, action, include_title)

    return [{"subject": subject, "body": body}]

def pr_comment_handler(payload: Dict[str, Any], action: str,
                       include_title: bool=False) -> List[Dict[str, str]]:
    pr = payload["pullRequest"]
    subject = get_pr_subject(pr["toRef"]["repository"]["name"], type="PR", id=pr["id"],
                             title=pr["title"])
    message = payload["comment"]["text"]
    if action == "deleted their comment on":
        message = f"~~{message}~~"
    body = get_pull_request_event_message(
        user_name=get_user_name(payload),
        action=action,
        url=pr["links"]["self"][0]["href"],
        number=pr["id"],
        message=message,
        title=pr["title"] if include_title else None,
    )

    return [{"subject": subject, "body": body}]

EVENT_HANDLER_MAP = {
    "diagnostics:ping": ping_handler,
    "repo:comment:added": partial(repo_comment_handler, action="commented"),
    "repo:comment:edited": partial(repo_comment_handler, action="edited their comment"),
    "repo:comment:deleted": partial(repo_comment_handler, action="deleted their comment"),
    "repo:forked": repo_forked_handler,
    "repo:modified": repo_modified_handler,
    "repo:refs_changed": repo_push_handler,
    "pr:comment:added": partial(pr_comment_handler, action="commented on"),
    "pr:comment:edited": partial(pr_comment_handler, action="edited their comment on"),
    "pr:comment:deleted": partial(pr_comment_handler, action="deleted their comment on"),
    "pr:declined": partial(pr_handler, action="declined"),
    "pr:deleted": partial(pr_handler, action="deleted"),
    "pr:merged": partial(pr_handler, action="merged"),
    "pr:modified": partial(pr_handler, action="modified"),
    "pr:opened": partial(pr_handler, action="opened"),
    "pr:reviewer:approved": partial(pr_handler, action="approved"),
    "pr:reviewer:needs_work": partial(pr_handler, action="needs_work"),
    "pr:reviewer:updated": partial(pr_handler, action="reviewers_updated"),
    "pr:reviewer:unapproved": partial(pr_handler, action="unapproved"),
}  # type Dict[str, Optional[Callable[..., List[Dict[str, str]]]]]

def get_event_handler(eventkey: str) -> Callable[..., List[Dict[str, str]]]:
    # The main reason for this function existence is because of mypy
    handler: Any = EVENT_HANDLER_MAP.get(eventkey)
    if handler is None:
        raise UnsupportedWebhookEventType(eventkey)
    return handler

@webhook_view("Bitbucket3")
@has_request_variables
def api_bitbucket3_webhook(request: HttpRequest, user_profile: UserProfile,
                           payload: Dict[str, Any]=REQ(argument_type="body"),
                           branches: Optional[str]=REQ(default=None),
                           user_specified_topic: Optional[str]=REQ("topic", default=None),
                           ) -> HttpResponse:
    try:
        eventkey = payload["eventKey"]
    except KeyError:
        eventkey = request.META["HTTP_X_EVENT_KEY"]
    handler = get_event_handler(eventkey)

    if "branches" in signature(handler).parameters:
        data = handler(payload, branches)
    elif "include_title" in signature(handler).parameters:
        data = handler(payload, include_title=user_specified_topic)
    else:
        data = handler(payload)
    for element in data:
        check_send_webhook_message(request, user_profile, element["subject"],
                                   element["body"], unquote_url_parameters=True)

    return json_success()

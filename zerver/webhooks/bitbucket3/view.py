from inspect import signature
from functools import partial
from typing import Any, Dict, Optional, List, Callable

from django.http import HttpRequest, HttpResponse

from zerver.models import UserProfile
from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.git import TOPIC_WITH_BRANCH_TEMPLATE, \
    get_push_tag_event_message, get_remove_branch_event_message, \
    get_create_branch_event_message, get_commits_comment_action_message
from zerver.lib.webhooks.common import check_send_webhook_message, \
    UnexpectedWebhookEventType
from zerver.webhooks.bitbucket2.view import BITBUCKET_TOPIC_TEMPLATE, \
    BITBUCKET_FORK_BODY, BITBUCKET_REPO_UPDATED_CHANGED

BRANCH_UPDATED_MESSAGE_TEMPLATE = "{user_name} pushed to branch {branch_name}. Head is now {head}"

def repo_comment_handler(payload: Dict[str, Any], action: str) -> List[Dict[str, str]]:
    repo_name = payload["repository"]["name"]
    user_name = payload["actor"]["name"]
    subject = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    sha = payload["commit"]
    commit_url = payload["repository"]["links"]["self"][0]["href"][:-6]  # remove the "browse" at the end
    commit_url += "commits/%s" % (sha,)
    body = get_commits_comment_action_message(user_name=user_name,
                                              action=action,
                                              commit_url=commit_url,
                                              sha=sha,
                                              message=payload["comment"]["text"])
    return [{"subject": subject, "body": body}]

def repo_forked_handler(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    repo_name = payload["repository"]["origin"]["name"]
    subject = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    body = BITBUCKET_FORK_BODY.format(
        display_name=payload["actor"]["displayName"],
        username=payload["actor"]["name"],
        fork_name=payload["repository"]["name"],
        fork_url=payload["repository"]["links"]["self"][0]["href"]
    )
    return [{"subject": subject, "body": body}]

def repo_modified_handler(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    subject_new = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=payload["new"]["name"])
    body = BITBUCKET_REPO_UPDATED_CHANGED.format(
        actor=payload["actor"]["name"],
        change="name",
        repo_name=payload["old"]["name"],
        old=payload["old"]["name"],
        new=payload["new"]["name"]
    )  # As of writing this, the only change we'd be notified about is a name change.
    return [{"subject": subject_new, "body": body}]

def repo_push_branch_data(payload: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, str]:
    event_type = change["type"]
    repo_name = payload["repository"]["name"]
    user_name = payload["actor"]["name"]
    branch_name = change["ref"]["displayId"]
    branch_head = change["toHash"]

    if event_type == "ADD":
        body = get_create_branch_event_message(user_name=user_name, url=None, branch_name=branch_name)
    elif event_type == "UPDATE":
        body = BRANCH_UPDATED_MESSAGE_TEMPLATE.format(user_name=user_name,
                                                      branch_name=branch_name,
                                                      head=branch_head)
    elif event_type == "DELETE":
        body = get_remove_branch_event_message(user_name, branch_name)
    else:
        message = "%s.%s" % (payload["eventKey"], event_type)  # nocoverage
        raise UnexpectedWebhookEventType("BitBucket Server", message)

    subject = TOPIC_WITH_BRANCH_TEMPLATE.format(repo=repo_name, branch=branch_name)
    return {"subject": subject, "body": body}

def repo_push_tag_data(payload: Dict[str, Any], change: Dict[str, Any]) -> Dict[str, str]:
    event_type = change["type"]
    repo_name = payload["repository"]["name"]
    tag_name = change["ref"]["displayId"]
    user_name = payload["actor"]["name"]

    if event_type == "ADD":
        action = "pushed"
    elif event_type == "DELETE":
        action = "removed"
    else:
        message = "%s.%s" % (payload["eventKey"], event_type)  # nocoverage
        raise UnexpectedWebhookEventType("BitBucket Server", message)

    subject = BITBUCKET_TOPIC_TEMPLATE.format(repository_name=repo_name)
    body = get_push_tag_event_message(
        user_name,
        tag_name,
        action=action)
    return {"subject": subject, "body": body}

def repo_push_handler(payload: Dict[str, Any], branches: Optional[str]=None) -> List[Dict[str, str]]:
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
            message = "%s.%s" % (payload["eventKey"], event_target_type)  # nocoverage
            raise UnexpectedWebhookEventType("BitBucket Server", message)
    return data

EVENT_HANDLER_MAP = {
    "repo:comment:added": partial(repo_comment_handler, action="commented"),
    "repo:comment:edited": partial(repo_comment_handler, action="edited their comment"),
    "repo:comment:deleted": partial(repo_comment_handler, action="deleted their comment"),
    "repo:forked": repo_forked_handler,
    "repo:modified": repo_modified_handler,
    "repo:refs_changed": repo_push_handler,
    "pr:comment:added": None,
    "pr:comment:edited": None,
    "pr:comment:deleted": None,
    "pr:declined": None,
    "pr:deleted": None,
    "pr:merged": None,
    "pr:modified": None,
    "pr:opened": None,
    "pr:reviewer:approved": None,
    "pr:reviewer:needs_work": None,
    "pr:reviewer:updated": None,
    "pr:reviewer:unapproved": None,
}  # type Dict[str, Optional[Callable[..., List[Dict[str, str]]]]]

def get_event_handler(eventkey: str) -> Callable[..., List[Dict[str, str]]]:
    # The main reason for this function existance is because of mypy
    handler = EVENT_HANDLER_MAP.get(eventkey)  # type: Any
    if handler is None:
        raise UnexpectedWebhookEventType("BitBucket Server", eventkey)
    return handler

@api_key_only_webhook_view("Bitbucket3")
@has_request_variables
def api_bitbucket3_webhook(request: HttpRequest, user_profile: UserProfile,
                           payload: Dict[str, Any]=REQ(argument_type="body"),
                           branches: Optional[str]=REQ(default=None),
                           user_specified_topic: Optional[str]=REQ("topic", default=None)
                           ) -> HttpResponse:
    eventkey = payload["eventKey"]
    handler = get_event_handler(eventkey)

    if "branches" in signature(handler).parameters:
        data = handler(payload, branches)
    else:
        data = handler(payload)
    for element in data:
        check_send_webhook_message(request, user_profile, element["subject"],
                                   element["body"], unquote_url_parameters=True)

    return json_success()

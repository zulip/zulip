from typing import Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import (
    TOPIC_WITH_BRANCH_TEMPLATE,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    get_pull_request_event_message,
    get_push_commits_event_message,
)
from zerver.models import UserProfile


def get_code_pull_request_updated_body(payload: WildValue) -> str:
    return get_pull_request_event_message(
        user_name=get_code_pull_request_user_name(payload),
        action="updated",
        url=get_code_pull_request_url(payload),
        number=get_code_pull_request_id(payload),
        message=payload["detailedMessage"]["markdown"].tame(check_string),
        title=get_code_pull_request_title(payload),
    )


def get_code_pull_request_merged_body(payload: WildValue) -> str:
    return get_pull_request_event_message(
        user_name=get_code_pull_request_user_name(payload),
        action="merged",
        url=get_code_pull_request_url(payload),
        number=get_code_pull_request_id(payload),
        target_branch=payload["resource"]["sourceRefName"]
        .tame(check_string)
        .replace("refs/heads/", ""),
        base_branch=payload["resource"]["targetRefName"]
        .tame(check_string)
        .replace("refs/heads/", ""),
        title=get_code_pull_request_title(payload),
    )


def get_code_pull_request_opened_body(payload: WildValue) -> str:
    if payload["resource"].get("description"):
        description = payload["resource"]["description"].tame(check_string)
    else:
        description = None
    return get_pull_request_event_message(
        user_name=get_code_pull_request_user_name(payload),
        action="created",
        url=get_code_pull_request_url(payload),
        number=get_code_pull_request_id(payload),
        target_branch=payload["resource"]["sourceRefName"]
        .tame(check_string)
        .replace("refs/heads/", ""),
        base_branch=payload["resource"]["targetRefName"]
        .tame(check_string)
        .replace("refs/heads/", ""),
        message=description,
        title=get_code_pull_request_title(payload),
    )


def get_code_push_commits_body(payload: WildValue) -> str:
    compare_url = "{}/branchCompare?baseVersion=GC{}&targetVersion=GC{}&_a=files".format(
        get_code_repository_url(payload),
        payload["resource"]["refUpdates"][0]["oldObjectId"].tame(check_string),
        payload["resource"]["refUpdates"][0]["newObjectId"].tame(check_string),
    )
    commits_data = [
        {
            "name": commit["author"]["name"].tame(check_string),
            "sha": commit["commitId"].tame(check_string),
            "url": "{}/commit/{}".format(
                get_code_repository_url(payload), commit["commitId"].tame(check_string)
            ),
            "message": commit["comment"].tame(check_string),
        }
        for commit in payload["resource"].get("commits", [])
    ]
    return get_push_commits_event_message(
        get_code_push_user_name(payload),
        compare_url,
        get_code_push_branch_name(payload),
        commits_data,
    )


def get_code_push_user_name(payload: WildValue) -> str:
    return payload["resource"]["pushedBy"]["displayName"].tame(check_string)


def get_code_push_branch_name(payload: WildValue) -> str:
    return (
        payload["resource"]["refUpdates"][0]["name"].tame(check_string).replace("refs/heads/", "")
    )


def get_code_repository_name(payload: WildValue) -> str:
    return payload["resource"]["repository"]["name"].tame(check_string)


def get_code_repository_url(payload: WildValue) -> str:
    return payload["resource"]["repository"]["remoteUrl"].tame(check_string)


def get_code_pull_request_id(payload: WildValue) -> int:
    return payload["resource"]["pullRequestId"].tame(check_int)


def get_code_pull_request_title(payload: WildValue) -> str:
    return payload["resource"]["title"].tame(check_string)


def get_code_pull_request_url(payload: WildValue) -> str:
    return payload["resource"]["_links"]["web"]["href"].tame(check_string)


def get_code_pull_request_user_name(payload: WildValue) -> str:
    return payload["resource"]["createdBy"]["displayName"].tame(check_string)


def get_topic_based_on_event(payload: WildValue, event: str) -> str:
    if event == "git.push":
        return TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=get_code_repository_name(payload), branch=get_code_push_branch_name(payload)
        )
    elif "pullrequest" in event:
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_code_repository_name(payload),
            type="PR",
            id=get_code_pull_request_id(payload),
            title=get_code_pull_request_title(payload),
        )
    return get_code_repository_name(payload)  # nocoverage


def get_event_name(payload: WildValue, branches: Optional[str]) -> Optional[str]:
    event_name = payload["eventType"].tame(check_string)
    if event_name == "git.push" and branches is not None:
        branch = get_code_push_branch_name(payload)
        if branches.find(branch) == -1:
            return None
    if event_name == "git.pullrequest.merged":
        status = payload["resource"]["status"].tame(check_string)
        merge_status = payload["resource"]["mergeStatus"].tame(check_string)
        # azure devops sends webhook messages when a merge is attempted, i.e. there is a merge conflict
        # after a PR is created, or when there is no conflict when PR is updated
        # we're only interested in the case when the PR is merged successfully
        if status != "completed" or merge_status != "succeeded":
            return None
    if event_name in EVENT_FUNCTION_MAPPER:
        return event_name
    raise UnsupportedWebhookEventTypeError(event_name)


EVENT_FUNCTION_MAPPER: Dict[str, Callable[[WildValue], str]] = {
    "git.push": get_code_push_commits_body,
    "git.pullrequest.created": get_code_pull_request_opened_body,
    "git.pullrequest.merged": get_code_pull_request_merged_body,
    "git.pullrequest.updated": get_code_pull_request_updated_body,
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("AzureDevOps", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_azuredevops_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
    branches: Optional[str] = None,
) -> HttpResponse:
    event = get_event_name(payload, branches)
    if event is None:
        return json_success(request)

    topic = get_topic_based_on_event(payload, event)

    body_function = EVENT_FUNCTION_MAPPER[event]
    body = body_function(payload)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)

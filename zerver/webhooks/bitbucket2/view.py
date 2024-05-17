# Webhooks for external integrations.
import re
import string
from typing import Dict, List, Optional, Protocol

from django.http import HttpRequest, HttpResponse

from zerver.decorator import log_unsupported_webhook_event, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import (
    OptionalUserSpecifiedTopicStr,
    check_send_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.lib.webhooks.git import (
    TOPIC_WITH_BRANCH_TEMPLATE,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    get_commits_comment_action_message,
    get_force_push_commits_event_message,
    get_issue_event_message,
    get_pull_request_event_message,
    get_push_commits_event_message,
    get_push_tag_event_message,
    get_remove_branch_event_message,
    get_short_sha,
)
from zerver.models import UserProfile

BITBUCKET_TOPIC_TEMPLATE = "{repository_name}"

BITBUCKET_FORK_BODY = "{actor} forked the repository into [{fork_name}]({fork_url})."
BITBUCKET_COMMIT_STATUS_CHANGED_BODY = (
    "[System {key}]({system_url}) changed status of {commit_info} to {status}."
)
BITBUCKET_REPO_UPDATED_CHANGED = (
    "{actor} changed the {change} of the **{repo_name}** repo from **{old}** to **{new}**"
)
BITBUCKET_REPO_UPDATED_ADDED = (
    "{actor} changed the {change} of the **{repo_name}** repo to **{new}**"
)

PULL_REQUEST_SUPPORTED_ACTIONS = [
    "approved",
    "unapproved",
    "created",
    "updated",
    "rejected",
    "fulfilled",
    "comment_created",
    "comment_updated",
    "comment_deleted",
]

ALL_EVENT_TYPES = [
    "change_commit_status",
    "pull_request_comment_created",
    "pull_request_updated",
    "pull_request_unapproved",
    "push",
    "pull_request_approved",
    "pull_request_fulfilled",
    "issue_created",
    "issue_commented",
    "fork",
    "pull_request_comment_updated",
    "pull_request_created",
    "pull_request_rejected",
    "repo:updated",
    "issue_updated",
    "commit_comment",
    "pull_request_comment_deleted",
]


@webhook_view("Bitbucket2", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_bitbucket2_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    branches: Optional[str] = None,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    type = get_type(request, payload)
    if type == "push":
        # ignore push events with no changes
        if not payload["push"]["changes"]:
            return json_success(request)
        branch = get_branch_name_for_push_event(payload)
        if branch and branches and branches.find(branch) == -1:
            return json_success(request)

        topic_names = get_push_topics(payload)
        bodies = get_push_bodies(request, payload)

        for b, t in zip(bodies, topic_names):
            check_send_webhook_message(
                request, user_profile, t, b, type, unquote_url_parameters=True
            )
    else:
        topic_name = get_topic_based_on_type(payload, type)
        body_function = get_body_based_on_type(type)
        body = body_function(
            request,
            payload,
            include_title=user_specified_topic is not None,
        )

        check_send_webhook_message(
            request, user_profile, topic_name, body, type, unquote_url_parameters=True
        )

    return json_success(request)


def get_topic_for_branch_specified_events(
    payload: WildValue, branch_name: Optional[str] = None
) -> str:
    return TOPIC_WITH_BRANCH_TEMPLATE.format(
        repo=get_repository_name(payload["repository"]),
        branch=get_branch_name_for_push_event(payload) if branch_name is None else branch_name,
    )


def get_push_topics(payload: WildValue) -> List[str]:
    topics_list = []
    for change in payload["push"]["changes"]:
        potential_tag = (change["new"] or change["old"])["type"].tame(check_string)
        if potential_tag == "tag":
            topics_list.append(get_topic(payload))
        else:
            if change.get("new"):
                branch_name = change["new"]["name"].tame(check_string)
            else:
                branch_name = change["old"]["name"].tame(check_string)
            topics_list.append(get_topic_for_branch_specified_events(payload, branch_name))
    return topics_list


def get_topic(payload: WildValue) -> str:
    return BITBUCKET_TOPIC_TEMPLATE.format(
        repository_name=get_repository_name(payload["repository"])
    )


def get_topic_based_on_type(payload: WildValue, type: str) -> str:
    if type.startswith("pull_request"):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repository_name(payload["repository"]),
            type="PR",
            id=payload["pullrequest"]["id"].tame(check_int),
            title=payload["pullrequest"]["title"].tame(check_string),
        )
    if type.startswith("issue"):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repository_name(payload["repository"]),
            type="issue",
            id=payload["issue"]["id"].tame(check_int),
            title=payload["issue"]["title"].tame(check_string),
        )
    assert type != "push"
    return get_topic(payload)


def get_type(request: HttpRequest, payload: WildValue) -> str:
    if "push" in payload:
        return "push"
    elif "fork" in payload:
        return "fork"
    elif "comment" in payload and "commit" in payload:
        return "commit_comment"
    elif "commit_status" in payload:
        return "change_commit_status"
    elif "issue" in payload:
        if "changes" in payload:
            return "issue_updated"
        if "comment" in payload:
            return "issue_commented"
        return "issue_created"
    elif "pullrequest" in payload:
        pull_request_template = "pull_request_{}"
        # Note that we only need the HTTP header to determine pullrequest events.
        # We rely on the payload itself to determine the other ones.
        event_key = validate_extract_webhook_http_header(request, "X-Event-Key", "BitBucket")
        action = re.match(r"pullrequest:(?P<action>.*)$", event_key)
        if action:
            action_group = action.group("action")
            if action_group in PULL_REQUEST_SUPPORTED_ACTIONS:
                return pull_request_template.format(action_group)
    else:
        event_key = validate_extract_webhook_http_header(request, "X-Event-Key", "BitBucket")
        if event_key == "repo:updated":
            return event_key

    raise UnsupportedWebhookEventTypeError(event_key)


class BodyGetter(Protocol):
    def __call__(self, request: HttpRequest, payload: WildValue, include_title: bool) -> str: ...


def get_body_based_on_type(
    type: str,
) -> BodyGetter:
    return GET_SINGLE_MESSAGE_BODY_DEPENDING_ON_TYPE_MAPPER[type]


def get_push_bodies(request: HttpRequest, payload: WildValue) -> List[str]:
    messages_list = []
    for change in payload["push"]["changes"]:
        potential_tag = (change["new"] or change["old"])["type"].tame(check_string)
        if potential_tag == "tag":
            messages_list.append(get_push_tag_body(request, payload, change))
        # if change['new'] is None, that means a branch was deleted
        elif change["new"].value is None:
            messages_list.append(get_remove_branch_push_body(request, payload, change))
        elif change["forced"].tame(check_bool):
            messages_list.append(get_force_push_body(request, payload, change))
        else:
            messages_list.append(get_normal_push_body(request, payload, change))
    return messages_list


def get_remove_branch_push_body(request: HttpRequest, payload: WildValue, change: WildValue) -> str:
    return get_remove_branch_event_message(
        get_actor_info(request, payload),
        change["old"]["name"].tame(check_string),
    )


def get_force_push_body(request: HttpRequest, payload: WildValue, change: WildValue) -> str:
    return get_force_push_commits_event_message(
        get_actor_info(request, payload),
        change["links"]["html"]["href"].tame(check_string),
        change["new"]["name"].tame(check_string),
        change["new"]["target"]["hash"].tame(check_string),
    )


def get_commit_author_name(request: HttpRequest, commit: WildValue) -> str:
    if "user" in commit["author"]:
        return get_user_info(request, commit["author"]["user"])
    return commit["author"]["raw"].tame(check_string).split()[0]


def get_normal_push_body(request: HttpRequest, payload: WildValue, change: WildValue) -> str:
    commits_data = [
        {
            "name": get_commit_author_name(request, commit),
            "sha": commit["hash"].tame(check_string),
            "url": commit["links"]["html"]["href"].tame(check_string),
            "message": commit["message"].tame(check_string),
        }
        for commit in change["commits"]
    ]

    return get_push_commits_event_message(
        get_actor_info(request, payload),
        change["links"]["html"]["href"].tame(check_string),
        change["new"]["name"].tame(check_string),
        commits_data,
        is_truncated=change["truncated"].tame(check_bool),
    )


def get_fork_body(request: HttpRequest, payload: WildValue, include_title: bool) -> str:
    return BITBUCKET_FORK_BODY.format(
        actor=get_user_info(request, payload["actor"]),
        fork_name=get_repository_full_name(payload["fork"]),
        fork_url=get_repository_url(payload["fork"]),
    )


def get_commit_comment_body(request: HttpRequest, payload: WildValue, include_title: bool) -> str:
    comment = payload["comment"]
    action = "[commented]({})".format(comment["links"]["html"]["href"].tame(check_string))
    return get_commits_comment_action_message(
        get_actor_info(request, payload),
        action,
        comment["commit"]["links"]["html"]["href"].tame(check_string),
        comment["commit"]["hash"].tame(check_string),
        comment["content"]["raw"].tame(check_string),
    )


def get_commit_status_changed_body(
    request: HttpRequest, payload: WildValue, include_title: bool
) -> str:
    commit_api_url = payload["commit_status"]["links"]["commit"]["href"].tame(check_string)
    commit_id = commit_api_url.split("/")[-1]

    commit_info = "[{short_commit_id}]({repo_url}/commits/{commit_id})".format(
        repo_url=get_repository_url(payload["repository"]),
        short_commit_id=get_short_sha(commit_id),
        commit_id=commit_id,
    )

    return BITBUCKET_COMMIT_STATUS_CHANGED_BODY.format(
        key=payload["commit_status"]["key"].tame(check_string),
        system_url=payload["commit_status"]["url"].tame(check_string),
        commit_info=commit_info,
        status=payload["commit_status"]["state"].tame(check_string),
    )


def get_issue_commented_body(request: HttpRequest, payload: WildValue, include_title: bool) -> str:
    action = "[commented]({}) on".format(
        payload["comment"]["links"]["html"]["href"].tame(check_string)
    )
    return get_issue_action_body(action, request, payload, include_title)


def get_issue_action_body(
    action: str, request: HttpRequest, payload: WildValue, include_title: bool
) -> str:
    issue = payload["issue"]
    assignee = None
    message = None
    if action == "created":
        if issue["assignee"]:
            assignee = get_user_info(request, issue["assignee"])
        message = issue["content"]["raw"].tame(check_string)

    return get_issue_event_message(
        user_name=get_actor_info(request, payload),
        action=action,
        url=issue["links"]["html"]["href"].tame(check_string),
        number=issue["id"].tame(check_int),
        message=message,
        assignee=assignee,
        title=issue["title"].tame(check_string) if include_title else None,
    )


def get_pull_request_action_body(
    action: str, request: HttpRequest, payload: WildValue, include_title: bool
) -> str:
    pull_request = payload["pullrequest"]
    target_branch = None
    base_branch = None
    if action == "merged":
        target_branch = pull_request["source"]["branch"]["name"].tame(check_string)
        base_branch = pull_request["destination"]["branch"]["name"].tame(check_string)

    return get_pull_request_event_message(
        user_name=get_actor_info(request, payload),
        action=action,
        url=get_pull_request_url(pull_request),
        number=pull_request["id"].tame(check_int),
        target_branch=target_branch,
        base_branch=base_branch,
        title=pull_request["title"].tame(check_string) if include_title else None,
    )


def get_pull_request_created_or_updated_body(
    action: str, request: HttpRequest, payload: WildValue, include_title: bool
) -> str:
    pull_request = payload["pullrequest"]
    assignee = None
    if pull_request["reviewers"]:
        assignee = get_user_info(request, pull_request["reviewers"][0])

    return get_pull_request_event_message(
        user_name=get_actor_info(request, payload),
        action=action,
        url=get_pull_request_url(pull_request),
        number=pull_request["id"].tame(check_int),
        target_branch=(
            pull_request["source"]["branch"]["name"].tame(check_string)
            if action == "created"
            else None
        ),
        base_branch=(
            pull_request["destination"]["branch"]["name"].tame(check_string)
            if action == "created"
            else None
        ),
        message=pull_request["description"].tame(check_string),
        assignee=assignee,
        title=pull_request["title"].tame(check_string) if include_title else None,
    )


def get_pull_request_comment_created_action_body(
    request: HttpRequest,
    payload: WildValue,
    include_title: bool,
) -> str:
    action = "[commented]({})".format(
        payload["comment"]["links"]["html"]["href"].tame(check_string)
    )
    return get_pull_request_comment_action_body(request, payload, action, include_title)


def get_pull_request_deleted_or_updated_comment_action_body(
    action: str,
    request: HttpRequest,
    payload: WildValue,
    include_title: bool,
) -> str:
    action = "{} a [comment]({})".format(
        action, payload["comment"]["links"]["html"]["href"].tame(check_string)
    )
    return get_pull_request_comment_action_body(request, payload, action, include_title)


def get_pull_request_comment_action_body(
    request: HttpRequest,
    payload: WildValue,
    action: str,
    include_title: bool,
) -> str:
    action += " on"
    return get_pull_request_event_message(
        user_name=get_actor_info(request, payload),
        action=action,
        url=payload["pullrequest"]["links"]["html"]["href"].tame(check_string),
        number=payload["pullrequest"]["id"].tame(check_int),
        message=payload["comment"]["content"]["raw"].tame(check_string),
        title=payload["pullrequest"]["title"].tame(check_string) if include_title else None,
    )


def get_push_tag_body(request: HttpRequest, payload: WildValue, change: WildValue) -> str:
    if change.get("new"):
        tag = change["new"]
        action = "pushed"
    elif change.get("old"):
        tag = change["old"]
        action = "removed"

    return get_push_tag_event_message(
        get_actor_info(request, payload),
        tag["name"].tame(check_string),
        tag_url=tag["links"]["html"]["href"].tame(check_string),
        action=action,
    )


def append_punctuation(title: str, message: str) -> str:
    if title[-1] not in string.punctuation:
        message = f"{message}."

    return message


def get_repo_updated_body(request: HttpRequest, payload: WildValue, include_title: bool) -> str:
    changes = ["website", "name", "links", "language", "full_name", "description"]
    body = ""
    repo_name = payload["repository"]["name"].tame(check_string)
    actor = get_actor_info(request, payload)

    for change in changes:
        new = payload["changes"][change]["new"]
        old = payload["changes"][change]["old"]
        if change == "full_name":
            change = "full name"
        if new and old:
            message = BITBUCKET_REPO_UPDATED_CHANGED.format(
                actor=actor,
                change=change,
                repo_name=repo_name,
                old=str(old.value),
                new=str(new.value),
            )
            message = append_punctuation(str(new.value), message) + "\n"
            body += message
        elif new and not old:
            message = BITBUCKET_REPO_UPDATED_ADDED.format(
                actor=actor,
                change=change,
                repo_name=repo_name,
                new=str(new.value),
            )
            message = append_punctuation(str(new.value), message) + "\n"
            body += message

    return body


def get_pull_request_url(pullrequest_payload: WildValue) -> str:
    return pullrequest_payload["links"]["html"]["href"].tame(check_string)


def get_repository_url(repository_payload: WildValue) -> str:
    return repository_payload["links"]["html"]["href"].tame(check_string)


def get_repository_name(repository_payload: WildValue) -> str:
    return repository_payload["name"].tame(check_string)


def get_repository_full_name(repository_payload: WildValue) -> str:
    return repository_payload["full_name"].tame(check_string)


def get_user_info(request: HttpRequest, dct: WildValue) -> str:
    # See https://developer.atlassian.com/cloud/bitbucket/bitbucket-api-changes-gdpr/
    # Since GDPR, we don't get username; instead, we either get display_name
    # or nickname.
    if "display_name" in dct:
        return dct["display_name"].tame(check_string)

    if "nickname" in dct:
        return dct["nickname"].tame(check_string)

    # We call this an unsupported_event, even though we
    # are technically still sending a message.
    log_unsupported_webhook_event(
        request=request,
        summary="Could not find display_name/nickname field",
    )

    return "Unknown user"


def get_actor_info(request: HttpRequest, payload: WildValue) -> str:
    actor = payload["actor"]
    return get_user_info(request, actor)


def get_branch_name_for_push_event(payload: WildValue) -> Optional[str]:
    change = payload["push"]["changes"][-1]
    potential_tag = (change["new"] or change["old"])["type"].tame(check_string)
    if potential_tag == "tag":
        return None
    else:
        return (change["new"] or change["old"])["name"].tame(check_string)


GET_SINGLE_MESSAGE_BODY_DEPENDING_ON_TYPE_MAPPER: Dict[str, BodyGetter] = {
    "fork": get_fork_body,
    "commit_comment": get_commit_comment_body,
    "change_commit_status": get_commit_status_changed_body,
    "issue_updated": partial(get_issue_action_body, "updated"),
    "issue_created": partial(get_issue_action_body, "created"),
    "issue_commented": get_issue_commented_body,
    "pull_request_created": partial(get_pull_request_created_or_updated_body, "created"),
    "pull_request_updated": partial(get_pull_request_created_or_updated_body, "updated"),
    "pull_request_approved": partial(get_pull_request_action_body, "approved"),
    "pull_request_unapproved": partial(get_pull_request_action_body, "unapproved"),
    "pull_request_fulfilled": partial(get_pull_request_action_body, "merged"),
    "pull_request_rejected": partial(get_pull_request_action_body, "rejected"),
    "pull_request_comment_created": get_pull_request_comment_created_action_body,
    "pull_request_comment_updated": partial(
        get_pull_request_deleted_or_updated_comment_action_body, "updated"
    ),
    "pull_request_comment_deleted": partial(
        get_pull_request_deleted_or_updated_comment_action_body, "deleted"
    ),
    "repo:updated": get_repo_updated_body,
}

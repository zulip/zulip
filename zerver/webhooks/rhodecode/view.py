from typing import Callable, Dict, Optional

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import TOPIC_WITH_BRANCH_TEMPLATE, get_push_commits_event_message
from zerver.models import UserProfile


def get_push_commits_body(payload: WildValue) -> str:
    commits_data = []
    for commit in payload["event"]["push"]["commits"]:
        commits_data.append(
            {
                "name": commit["author"].tame(check_string),
                "sha": commit["raw_id"].tame(check_string),
                "url": commit["url"].tame(check_string),
                "message": commit["message"].tame(check_string),
            }
        )
    return get_push_commits_event_message(
        get_user_name(payload),
        None,
        get_push_branch_name(payload),
        commits_data,
    )


def get_user_name(payload: WildValue) -> str:
    return payload["event"]["actor"]["username"].tame(check_string)


def get_push_branch_name(payload: WildValue) -> str:
    branches = payload["event"]["push"]["branches"]
    try:
        return branches[0]["name"].tame(check_string)
    # this error happens when the event is a push to delete remote branch, where
    # branches will be an empty list
    except ValidationError:
        return payload["event"]["push"]["commits"][0]["raw_id"].tame(check_string).split("=>")[1]


def get_event_name(payload: WildValue, branches: Optional[str]) -> Optional[str]:
    event_name = payload["event"]["name"].tame(check_string)
    if event_name == "repo-push":
        if branches is not None:
            branch = get_push_branch_name(payload)
            if branches.find(branch) == -1:
                return None
    if event_name in EVENT_FUNCTION_MAPPER:
        return event_name
    raise UnsupportedWebhookEventType(event_name)


def get_repository_name(payload: WildValue) -> str:
    return payload["event"]["repo"]["repo_name"].tame(check_string)


def get_topic_based_on_event(payload: WildValue, event: str) -> str:
    if event == "repo-push":
        return TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=get_repository_name(payload), branch=get_push_branch_name(payload)
        )
    return get_repository_name(payload)  # nocoverage


EVENT_FUNCTION_MAPPER: Dict[str, Callable[[WildValue], str]] = {
    "repo-push": get_push_commits_body,
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("RhodeCode", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_rhodecode_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
    branches: Optional[str] = REQ(default=None),
) -> HttpResponse:
    event = get_event_name(payload, branches)
    if event is None:
        return json_success(request)

    topic = get_topic_based_on_event(payload, event)

    body_function = EVENT_FUNCTION_MAPPER[event]
    body = body_function(payload)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)

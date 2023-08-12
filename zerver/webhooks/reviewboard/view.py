from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    get_http_headers_from_filename,
    validate_extract_webhook_http_header,
)
from zerver.models import UserProfile

REVIEW_REQUEST_PUBLISHED = """
**{user_name}** opened [#{id}: {review_request_title}]({review_request_url}):
"""

REVIEW_REQUEST_REOPENED = """
**{user_name}** reopened [#{id}: {review_request_title}]({review_request_url}):
"""

REVIEW_REQUEST_CLOSED = """
**{user_name}** closed [#{id}: {review_request_title}]({review_request_url}):
"""

REVIEW_PUBLISHED = """
**{user_name}** [reviewed]({review_url}) [#{id}: {review_request_title}]({review_request_url}):

**Review**:
``` quote
{review_body_top}
```
"""

REVIEW_REQUEST_DETAILS = """
``` quote
**Description**: {description}
**Status**: {status}
**Target people**: {target_people}
{extra_info}
```
"""

REPLY_PUBLISHED = """
**{user_name}** [replied]({reply_url}) to [#{id}: {review_request_title}]({review_request_url}):

**Reply**:
``` quote
{reply_body_top}
```
"""

BRANCH_TEMPLATE = "**Branch**: {branch_name}"

fixture_to_headers = get_http_headers_from_filename("HTTP_X_REVIEWBOARD_EVENT")


def get_target_people_string(payload: WildValue) -> str:
    result = ""
    target_people = payload["review_request"]["target_people"]
    if len(target_people) == 1:
        result = "**{title}**".format(title=target_people[0]["title"].tame(check_string))
    else:
        for target_index in range(len(target_people) - 1):
            result += "**{title}**, ".format(
                title=target_people[target_index]["title"].tame(check_string)
            )
        result += "and **{title}**".format(title=target_people[-1]["title"].tame(check_string))

    return result


def get_review_published_body(payload: WildValue) -> str:
    kwargs = {
        "review_url": payload["review"]["absolute_url"].tame(check_string),
        "id": payload["review_request"]["id"].tame(check_int),
        "review_request_title": payload["review_request"]["summary"].tame(check_string),
        "review_request_url": payload["review_request"]["absolute_url"].tame(check_string),
        "user_name": payload["review"]["links"]["user"]["title"].tame(check_string),
        "review_body_top": payload["review"]["body_top"].tame(check_string),
    }

    return REVIEW_PUBLISHED.format(**kwargs).strip()


def get_reply_published_body(payload: WildValue) -> str:
    kwargs = {
        "reply_url": payload["reply"]["links"]["self"]["href"].tame(check_string),
        "id": payload["review_request"]["id"].tame(check_int),
        "review_request_title": payload["review_request"]["summary"].tame(check_string),
        "review_request_url": payload["review_request"]["links"]["self"]["href"].tame(check_string),
        "user_name": payload["reply"]["links"]["user"]["title"].tame(check_string),
        "user_url": payload["reply"]["links"]["user"]["href"].tame(check_string),
        "reply_body_top": payload["reply"]["body_top"].tame(check_string),
    }

    return REPLY_PUBLISHED.format(**kwargs).strip()


def get_review_request_published_body(payload: WildValue) -> str:
    kwargs = {
        "id": payload["review_request"]["id"].tame(check_int),
        "review_request_title": payload["review_request"]["summary"].tame(check_string),
        "review_request_url": payload["review_request"]["absolute_url"].tame(check_string),
        "user_name": payload["review_request"]["links"]["submitter"]["title"].tame(check_string),
        "description": payload["review_request"]["description"].tame(check_string),
        "status": payload["review_request"]["status"].tame(check_string),
        "target_people": get_target_people_string(payload),
        "extra_info": "",
    }

    message = REVIEW_REQUEST_PUBLISHED + REVIEW_REQUEST_DETAILS
    branch = payload["review_request"].get("branch").tame(check_none_or(check_string))
    if branch and branch is not None:
        branch_info = BRANCH_TEMPLATE.format(branch_name=branch)
        kwargs["extra_info"] = branch_info

    return message.format(**kwargs).strip()


def get_review_request_reopened_body(payload: WildValue) -> str:
    kwargs = {
        "id": payload["review_request"]["id"].tame(check_int),
        "review_request_title": payload["review_request"]["summary"].tame(check_string),
        "review_request_url": payload["review_request"]["absolute_url"].tame(check_string),
        "user_name": payload["reopened_by"]["username"].tame(check_string),
        "description": payload["review_request"]["description"].tame(check_string),
        "status": payload["review_request"]["status"].tame(check_string),
        "target_people": get_target_people_string(payload),
        "extra_info": "",
    }

    message = REVIEW_REQUEST_REOPENED + REVIEW_REQUEST_DETAILS
    branch = payload["review_request"].get("branch").tame(check_none_or(check_string))
    if branch and branch is not None:
        branch_info = BRANCH_TEMPLATE.format(branch_name=branch)
        kwargs["extra_info"] = branch_info

    return message.format(**kwargs).strip()


def get_review_request_closed_body(payload: WildValue) -> str:
    kwargs = {
        "id": payload["review_request"]["id"].tame(check_int),
        "review_request_title": payload["review_request"]["summary"].tame(check_string),
        "review_request_url": payload["review_request"]["absolute_url"].tame(check_string),
        "user_name": payload["closed_by"]["username"].tame(check_string),
        "description": payload["review_request"]["description"].tame(check_string),
        "status": payload["review_request"]["status"].tame(check_string),
        "target_people": get_target_people_string(payload),
        "extra_info": "**Close type**: {}".format(payload["close_type"].tame(check_string)),
    }

    message = REVIEW_REQUEST_CLOSED + REVIEW_REQUEST_DETAILS
    branch = payload["review_request"].get("branch").tame(check_none_or(check_string))
    if branch and branch is not None:
        branch_info = BRANCH_TEMPLATE.format(branch_name=branch)
        kwargs["extra_info"] = "{}\n{}".format(kwargs["extra_info"], branch_info)

    return message.format(**kwargs).strip()


def get_review_request_repo_title(payload: WildValue) -> str:
    return payload["review_request"]["links"]["repository"]["title"].tame(check_string)


RB_MESSAGE_FUNCTIONS = {
    "review_request_published": get_review_request_published_body,
    "review_request_reopened": get_review_request_reopened_body,
    "review_request_closed": get_review_request_closed_body,
    "review_published": get_review_published_body,
    "reply_published": get_reply_published_body,
}

ALL_EVENT_TYPES = list(RB_MESSAGE_FUNCTIONS.keys())


@webhook_view("ReviewBoard", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_reviewboard_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    event_type = validate_extract_webhook_http_header(
        request, "X-ReviewBoard-Event", "Review Board"
    )
    assert event_type is not None

    body_function = RB_MESSAGE_FUNCTIONS.get(event_type)
    if body_function is not None:
        body = body_function(payload)
        topic = get_review_request_repo_title(payload)
        check_send_webhook_message(request, user_profile, topic, body, event_type)
    else:
        raise UnsupportedWebhookEventTypeError(event_type)

    return json_success(request)

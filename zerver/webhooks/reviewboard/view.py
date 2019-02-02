from typing import Any, Dict, Iterable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message, \
    validate_extract_webhook_http_header, UnexpectedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
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

def get_target_people_string(payload: Dict[str, Any]) -> str:
    result = ""
    target_people = payload['review_request']['target_people']
    if len(target_people) == 1:
        result = "**{title}**".format(**target_people[0])
    else:
        for target_person in target_people[:-1]:
            result += "**{title}**, ".format(**target_person)
        result += "and **{title}**".format(**target_people[-1])

    return result

def get_review_published_body(payload: Dict[str, Any]) -> str:
    kwargs = {
        'review_url': payload['review']['absolute_url'],
        'id': payload['review_request']['id'],
        'review_request_title': payload['review_request']['summary'],
        'review_request_url': payload['review_request']['absolute_url'],
        'user_name': payload['review']['links']['user']['title'],
        'review_body_top': payload['review']['body_top'],
    }

    return REVIEW_PUBLISHED.format(**kwargs).strip()

def get_reply_published_body(payload: Dict[str, Any]) -> str:
    kwargs = {
        'reply_url': payload['reply']['links']['self']['href'],
        'id': payload['review_request']['id'],
        'review_request_title': payload['review_request']['summary'],
        'review_request_url': payload['review_request']['links']['self']['href'],
        'user_name': payload['reply']['links']['user']['title'],
        'user_url': payload['reply']['links']['user']['href'],
        'reply_body_top': payload['reply']['body_top'],
    }

    return REPLY_PUBLISHED.format(**kwargs).strip()

def get_review_request_published_body(payload: Dict[str, Any]) -> str:
    kwargs = {
        'id': payload['review_request']['id'],
        'review_request_title': payload['review_request']['summary'],
        'review_request_url': payload['review_request']['absolute_url'],
        'user_name': payload['review_request']['links']['submitter']['title'],
        'description': payload['review_request']['description'],
        'status': payload['review_request']['status'],
        'target_people': get_target_people_string(payload),
        'extra_info': '',
    }

    message = REVIEW_REQUEST_PUBLISHED + REVIEW_REQUEST_DETAILS
    branch = payload['review_request'].get('branch')
    if branch and branch is not None:
        branch_info = BRANCH_TEMPLATE.format(branch_name=branch)
        kwargs['extra_info'] = branch_info

    return message.format(**kwargs).strip()

def get_review_request_reopened_body(payload: Dict[str, Any]) -> str:
    kwargs = {
        'id': payload['review_request']['id'],
        'review_request_title': payload['review_request']['summary'],
        'review_request_url': payload['review_request']['absolute_url'],
        'user_name': payload['reopened_by']['username'],
        'description': payload['review_request']['description'],
        'status': payload['review_request']['status'],
        'target_people': get_target_people_string(payload),
        'extra_info': '',
    }

    message = REVIEW_REQUEST_REOPENED + REVIEW_REQUEST_DETAILS
    branch = payload['review_request'].get('branch')
    if branch and branch is not None:
        branch_info = BRANCH_TEMPLATE.format(branch_name=branch)
        kwargs['extra_info'] = branch_info

    return message.format(**kwargs).strip()

def get_review_request_closed_body(payload: Dict[str, Any]) -> str:
    kwargs = {
        'id': payload['review_request']['id'],
        'review_request_title': payload['review_request']['summary'],
        'review_request_url': payload['review_request']['absolute_url'],
        'user_name': payload['closed_by']['username'],
        'description': payload['review_request']['description'],
        'status': payload['review_request']['status'],
        'target_people': get_target_people_string(payload),
        'extra_info': '**Close type**: {}'.format(payload['close_type']),
    }

    message = REVIEW_REQUEST_CLOSED + REVIEW_REQUEST_DETAILS
    branch = payload['review_request'].get('branch')
    if branch and branch is not None:
        branch_info = BRANCH_TEMPLATE.format(branch_name=branch)
        kwargs['extra_info'] = '{}\n{}'.format(kwargs['extra_info'], branch_info)

    return message.format(**kwargs).strip()

def get_review_request_repo_title(payload: Dict[str, Any]) -> str:
    return payload['review_request']['links']['repository']['title']

RB_MESSAGE_FUNCTIONS = {
    'review_request_published': get_review_request_published_body,
    'review_request_reopened': get_review_request_reopened_body,
    'review_request_closed': get_review_request_closed_body,
    'review_published': get_review_published_body,
    'reply_published': get_reply_published_body,
}

@api_key_only_webhook_view('ReviewBoard')
@has_request_variables
def api_reviewboard_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body')
) -> HttpResponse:
    event_type = validate_extract_webhook_http_header(
        request, 'X_REVIEWBOARD_EVENT', 'ReviewBoard')
    assert event_type is not None

    body_function = RB_MESSAGE_FUNCTIONS.get(event_type)
    if body_function is not None:
        body = body_function(payload)
        topic = get_review_request_repo_title(payload)
        check_send_webhook_message(request, user_profile, topic, body)
    else:
        raise UnexpectedWebhookEventType('ReviewBoard', event_type)

    return json_success()

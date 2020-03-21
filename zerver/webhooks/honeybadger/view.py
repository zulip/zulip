# Webhooks for external integrations.
from typing import Any, Dict, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view, has_request_variables
from zerver.lib.webhooks.common import check_send_webhook_message, UnexpectedWebhookEventType
from zerver.lib.request import REQ
from zerver.lib.response import json_success
from zerver.models import UserProfile

import re

RATE_EXCEEDED_TEMPLATE = "{message}. For more info: {url}"
ERROR_RESOLVED_TEMPLATE = "The error {id} was resolved by {actor}. For more info: {url}"
ERROR_OCCURRED_TEMPLATE = "{klass}: {message} The error({id}) occurred at: {last_notice}. For more info: {" \
                          "url} "
COMMENT_TEMPLATE = "On error id: {id} {author} commented \n```quote\n{body}\n```\nFor more info: {url}"
CHECK_IN_TEMPLATE = "{message}. {name} was expected to report at: {expected_at} and reported at: " \
                    "{reported_at}. For more info: {url}"
ASSIGNED_TEMPLATE = "{message}. Error with id: {id} has been assigned to {name}. For more info: {url}"
UP_AND_DOWN_TEMPLATE = "{message} For more info: {url}"


def parse_topic(message: str) -> str:
    m = re.match(r'([[\w\W]*])', message)
    if not m:
        return 'default'  # nocoverage fallback case in case there's a change in payload schema
    return m.group(0)[1:-1]


def parse_topic_and_message(message: str) -> Tuple[str, str]:
    m = re.match(r'\[([\s\w/]+)\] (.+)', message)
    if not m:
        return 'default', message  # nocoverage fallback case in case there's a change in payload schema
    return m.group(1), m.group(2)


def get_rate_exceeded_topic_and_message(payload: Dict[str, Any]) -> Tuple[str, str]:
    topic, m = parse_topic_and_message(message=payload["message"])

    message = RATE_EXCEEDED_TEMPLATE.format(message=m, url=payload['notice']['url'])

    return topic, message


def get_resolved_topic_and_message(payload: Dict[str, Any]) -> Tuple[str, str]:
    topic = parse_topic(message=payload["message"])

    message = ERROR_RESOLVED_TEMPLATE.format(id=str(payload['fault']['id']),
                                             actor=payload['actor']['name'],
                                             url=payload['fault']['url'])

    return topic, message


def get_occurred_topic_and_message(payload: Dict[str, Any]) -> Tuple[str, str]:
    topic = parse_topic(message=payload["message"])

    message = ERROR_OCCURRED_TEMPLATE.format(klass=payload['fault']['klass'],
                                             message=payload['fault']['message'],
                                             id=payload['fault']['id'],
                                             last_notice=payload['fault']['last_notice_at'],
                                             url=payload['fault']['url'])

    return topic, message


def get_down_and_up_topic_and_message(event: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    topic, m = parse_topic_and_message(message=payload["message"])
    topic += "/" + payload["project"]["environments"][0]["name"]

    message = UP_AND_DOWN_TEMPLATE.format(message=m, url=payload['site']['details_url'])

    return topic, message


def get_commented_topic_and_message(payload: Dict[str, Any]) -> Tuple[str, str]:
    topic = parse_topic(message=payload["message"])

    message = COMMENT_TEMPLATE.format(id=str(payload['fault']['id']),
                                      author=payload['comment']['author'],
                                      body=payload['comment']['body'],
                                      url=payload['fault']['url'])

    return topic, message


def get_check_in_topic_and_message(payload: Dict[str, Any]) -> Tuple[str, str]:
    topic, m = parse_topic_and_message(message=payload["message"])
    topic += "/" + payload["project"]["environments"][0]["name"]

    message = CHECK_IN_TEMPLATE.format(message=m, name=payload['check_in']['name'],
                                       expected_at=payload['check_in']['expected_at'],
                                       reported_at=payload['check_in']['reported_at'],
                                       url=payload['check_in']['details_url'])

    return topic, message


def get_assigned_topic_and_message(payload: Dict[str, Any]) -> Tuple[str, str]:
    topic, m = parse_topic_and_message(message=payload["message"])

    message = ASSIGNED_TEMPLATE.format(message=m, id=payload['fault']['id'],
                                       name=payload['assignee']['name'],
                                       url=payload['fault']['url'])
    return topic, message


def get_topic_and_message(event: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    if event == "assigned":
        return get_assigned_topic_and_message(payload)
    elif event == "check_in_missing" or event == "check_in_reporting":
        return get_check_in_topic_and_message(payload)
    elif event == "commented":
        return get_commented_topic_and_message(payload)
    elif event == "down" or event == "up":
        return get_down_and_up_topic_and_message(event, payload)
    elif event == "occurred":
        return get_occurred_topic_and_message(payload)
    elif event == "resolved":
        return get_resolved_topic_and_message(payload)
    elif event == "rate_exceeded":
        return get_rate_exceeded_topic_and_message(payload)

    raise UnexpectedWebhookEventType("honeybadger", event)


@api_key_only_webhook_view("honeybadger")
@has_request_variables
def api_honeybadger_webhook(request: HttpRequest, user_profile: UserProfile,
                            payload: Dict[str, Any] = REQ(argument_type='body')) -> HttpResponse:
    event = payload['event']

    topic, message = get_topic_and_message(event, payload)

    check_send_webhook_message(request, user_profile, topic, message)
    return json_success()

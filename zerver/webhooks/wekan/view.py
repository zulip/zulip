import re
from typing import Any, Dict, Iterable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message, UnexpectedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile


URL_REGEX = r"""(
        http(s)?
        (\S)*
    )"""

LINK_TEMPLATE = u"[See in Wekan]({url})"
MESSAGE_TEMPLATE = u"{body}\n\n{footer}"

def get_url(text: str) -> str:
    match = re.compile(URL_REGEX, re.VERBOSE).search(text)
    if match is None:
        return None
    return match.group()

def get_hyperlinked_url(text: str) -> str:
    url = get_url(text)
    return LINK_TEMPLATE.format(url=url)

def clean_payload_text(text: str) -> str:
    url = get_url(text)
    return text.replace(url, '').replace('\n', '')

def get_message_body(payload: Dict[str, Any], action: str) -> str:
    footer = get_hyperlinked_url(payload['text'])
    body = process_message_data(payload, action)
    return MESSAGE_TEMPLATE.format(body=body,footer=footer)

def process_message_data(payload: Dict[str, Any], action: str) -> str:
    payload['text'] = clean_payload_text(payload['text'])
    return u"{text}.".format(**payload)

@api_key_only_webhook_view('Wekan')
@has_request_variables
def api_wekan_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body')
) -> HttpResponse:


    topic = "Wekan Notification"
    body = get_message_body(payload, payload['description'])


    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

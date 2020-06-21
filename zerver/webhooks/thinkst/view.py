# Webhooks for external integrations.
from typing import Any, Dict, Optional, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def is_canarytoken(message: Dict[str, Any]) -> bool:
    """
    There are two types of requests that Thinkst will send - depending on whether it is
    a canary or a canarytoken. Unfortunately, there isn't a great way to differentiate other
    than look at the contents.
    """
    return 'Timestamp' not in message


def canarytoken_message(message: Dict[str, Any]) -> Tuple[str, str]:
    """
    Construct the message for a canarytoken-type request.
    """
    topic = 'canarytoken alert'
    body = (f"**:alert: Canarytoken has been triggered on {message['time']}!**\n\n"
            f"> {message['memo']} \n\n"
            f"[Manage this canarytoken]({message['manage_url']})")

    return (topic, body)


def canary_message(message: Dict[str, Any], user_specified_topic: Optional[str]) -> Tuple[str, str]:
    """
    Construct the message for a canary-type request.
    """
    topic = f"canary alert - {message['CanaryName']}"

    reverse_dns = ''
    if 'ReverseDNS' in message:
        reverse_dns = f" (`{message['ReverseDNS']}`)"

    name = ''
    if user_specified_topic:
        name = f" `{message['CanaryName']}`"

    body = (f"**:alert: Canary{name} has been triggered!**\n\n"
            f"On {message['Timestamp']}, `{message['CanaryName']}` was triggered "
            f"from `{message['SourceIP']}`{reverse_dns}:\n\n"
            f"> {message['Intro']}")

    return (topic, body)


@api_key_only_webhook_view('Thinkst')
@has_request_variables
def api_thinkst_webhook(request: HttpRequest, user_profile: UserProfile,
                        message: Dict[str, Any]=REQ(argument_type='body'),
                        user_specified_topic: Optional[str]=REQ('topic', default=None)) -> HttpResponse:
    """
    Construct a response to a webhook event from a Thinkst canary or canarytoken, see
    linked documentation below for a schema:

    https://help.canary.tools/hc/en-gb/articles/360002426577-How-do-I-configure-notifications-for-a-Generic-Webhook-
    """
    body = None
    topic = None

    if is_canarytoken(message):
        topic, body = canarytoken_message(message)
    else:
        topic, body = canary_message(message, user_specified_topic)

    if user_specified_topic:
        topic = user_specified_topic

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

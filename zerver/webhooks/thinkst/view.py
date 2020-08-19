# Webhooks for external integrations.
from typing import Any, Dict, Optional, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def is_canarytoken(message: Dict[str, Any]) -> bool:
    """
    Requests sent from Thinkst canaries are either from canarytokens or
    canaries, which can be differentiated by the value of the `AlertType`
    field.
    """
    return message['AlertType'] == 'CanarytokenIncident'


def canary_name(message: Dict[str, Any]) -> str:
    """
    Returns the name of the canary or canarytoken.
    """
    if is_canarytoken(message):
        return message['Reminder']
    else:
        return message['CanaryName']


def canary_kind(message: Dict[str, Any]) -> str:
    """
    Returns a description of the kind of request - canary or canarytoken.
    """
    if is_canarytoken(message):
        return 'canarytoken'
    else:
        return 'canary'


def source_ip_and_reverse_dns(
        message: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the source IP and reverse DNS information from a canary request.
    """
    reverse_dns, source_ip = (None, None)

    if 'SourceIP' in message:
        source_ip = message['SourceIP']
    # `ReverseDNS` can sometimes exist and still be empty.
    if 'ReverseDNS' in message and message['ReverseDNS']:
        reverse_dns = message['ReverseDNS']

    return (source_ip, reverse_dns)


def body(message: Dict[str, Any]) -> str:
    """
    Construct the response to a canary or canarytoken request.
    """

    title = canary_kind(message).title()
    name = canary_name(message)
    body = (f"**:alert: {title} *{name}* has been triggered!**\n\n"
            f"{message['Intro']}\n\n")

    if 'IncidentHash' in message:
        body += f"**Incident Id:** `{message['IncidentHash']}`\n"

    if 'Token' in message:
        body += f"**Token:** `{message['Token']}`\n"

    if 'Description' in message:
        body += f"**Kind:** {message['Description']}\n"

    if 'Timestamp' in message:
        body += f"**Timestamp:** {message['Timestamp']}\n"

    if 'CanaryIP' in message:
        body += f"**Canary IP:** `{message['CanaryIP']}`\n"

    if 'CanaryLocation' in message:
        body += f"**Canary Location:** {message['CanaryLocation']}\n"

    if 'Triggered' in message:
        unit = 'times' if message['Triggered'] > 1 else 'time'
        body += f"**Triggered:** {message['Triggered']} {unit}\n"

    source_ip, reverse_dns = source_ip_and_reverse_dns(message)
    if source_ip:
        body += f"**Source IP:** `{source_ip}`\n"
    if reverse_dns:
        body += f"**Reverse DNS:** `{reverse_dns}`\n"

    if 'AdditionalDetails' in message:
        for detail in message['AdditionalDetails']:
            if isinstance(detail[1], str) and '*' in detail[1]:
                # Thinkst sends passwords as a series of stars which can mess with
                # formatting, so wrap these in backticks.
                body += f"**{detail[0]}:** `{detail[1]}`\n"
            else:
                body += f"**{detail[0]}:** {detail[1]}\n"

    return body


@webhook_view('Thinkst')
@has_request_variables
def api_thinkst_webhook(
        request: HttpRequest, user_profile: UserProfile,
        message: Dict[str, Any] = REQ(argument_type='body'),
        user_specified_topic: Optional[str] = REQ('topic', default=None)
) -> HttpResponse:
    """
    Construct a response to a webhook event from a Thinkst canary or canarytoken.

    Thinkst offers public canarytokens with canarytokens.org and with their canary
    product, but the schema returned by these identically named services are
    completely different - canarytokens from canarytokens.org are handled by a
    different Zulip integration.

    Thinkst's documentation for the schema is linked below, but in practice the JSON
    received doesn't always conform.

    https://help.canary.tools/hc/en-gb/articles/360002426577-How-do-I-configure-notifications-for-a-Generic-Webhook-
    """

    response = body(message)

    topic = None
    if user_specified_topic:
        topic = user_specified_topic
    else:
        name = canary_name(message)
        kind = canary_kind(message)

        topic = f"{kind} alert - {name}"

    check_send_webhook_message(request, user_profile, topic, response)
    return json_success()

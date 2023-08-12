# Webhooks for external integrations.
from typing import Optional, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string, check_union
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile


def is_canarytoken(message: WildValue) -> bool:
    """
    Requests sent from Thinkst canaries are either from canarytokens or
    canaries, which can be differentiated by the value of the `AlertType`
    field.
    """
    return message["AlertType"].tame(check_string) == "CanarytokenIncident"


def canary_name(message: WildValue) -> str:
    """
    Returns the name of the canary or canarytoken.
    """
    if is_canarytoken(message):
        return message["Reminder"].tame(check_string)
    else:
        return message["CanaryName"].tame(check_string)


def canary_kind(message: WildValue) -> str:
    """
    Returns a description of the kind of request - canary or canarytoken.
    """
    if is_canarytoken(message):
        return "canarytoken"
    else:
        return "canary"


def source_ip_and_reverse_dns(message: WildValue) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the source IP and reverse DNS information from a canary request.
    """
    reverse_dns, source_ip = (None, None)

    if "SourceIP" in message:
        source_ip = message["SourceIP"].tame(check_string)
    # `ReverseDNS` can sometimes exist and still be empty.
    if "ReverseDNS" in message and message["ReverseDNS"].tame(check_string) != "":
        reverse_dns = message["ReverseDNS"].tame(check_string)

    return (source_ip, reverse_dns)


def body(message: WildValue) -> str:
    """
    Construct the response to a canary or canarytoken request.
    """

    title = canary_kind(message).title()
    name = canary_name(message)
    body = f"**:alert: {title} *{name}* has been triggered!**\n\n{message['Intro'].tame(check_string)}\n\n"

    if "IncidentHash" in message:
        body += f"**Incident ID:** `{message['IncidentHash'].tame(check_string)}`\n"

    if "Token" in message:
        body += f"**Token:** `{message['Token'].tame(check_string)}`\n"

    if "Description" in message:
        body += f"**Kind:** {message['Description'].tame(check_string)}\n"

    if "Timestamp" in message:
        body += f"**Timestamp:** {message['Timestamp'].tame(check_string)}\n"

    if "CanaryIP" in message:
        body += f"**Canary IP:** `{message['CanaryIP'].tame(check_string)}`\n"

    if "CanaryLocation" in message:
        body += f"**Canary location:** {message['CanaryLocation'].tame(check_string)}\n"

    if "Triggered" in message:
        unit = "times" if message["Triggered"].tame(check_int) > 1 else "time"
        body += f"**Triggered:** {message['Triggered'].tame(check_int)} {unit}\n"

    source_ip, reverse_dns = source_ip_and_reverse_dns(message)
    if source_ip:
        body += f"**Source IP:** `{source_ip}`\n"
    if reverse_dns:
        body += f"**Reverse DNS:** `{reverse_dns}`\n"

    if "AdditionalDetails" in message:
        for detail in message["AdditionalDetails"]:
            key = detail[0].tame(check_string)
            value = detail[1].tame(check_union([check_string, check_int]))
            if isinstance(value, str) and "*" in value:
                # Thinkst sends passwords as a series of stars which can mess with
                # formatting, so wrap these in backticks.
                body += f"**{key}:** `{value}`\n"
            else:
                body += f"**{key}:** {value}\n"

    return body


@webhook_view("Thinkst")
@typed_endpoint
def api_thinkst_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message: WebhookPayload[WildValue],
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
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
    return json_success(request)

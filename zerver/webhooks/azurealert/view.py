# Webhooks for external integrations.
from typing import Any, Dict

import dateutil.parser
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALERT_BODY_TEMPLATE = """
A {severity} alert was {monitorCondition} on {firedDateTime} by service - '{monitoringService}' on the following configuration items - {configurationItems}
Description -
{description}
""".strip()


def alert_body(payload: Dict[str, Any]) -> str:
    return ALERT_BODY_TEMPLATE.format(**payload)


def get_topic(payload: Dict[str, Any]) -> str:
    return payload["data"]["essentials"]["signalType"]


ALL_EVENT_TYPES = ["Activity Log", "Log", "Metric"]


@webhook_view("AzureAlert", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_azurealert_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:

    body_data = {
        "severity": payload["data"]["essentials"]["severity"].lower(),
        "monitorCondition": payload["data"]["essentials"]["monitorCondition"].lower(),
        "firedDateTime": dateutil.parser.parse(
            payload["data"]["essentials"]["firedDateTime"]
        ).strftime("%Y-%m-%d %H:%M %Z"),
        "monitoringService": payload["data"]["essentials"]["monitoringService"],
        "configurationItems": payload["data"]["essentials"]["configurationItems"],
        "description": payload["data"]["essentials"]["description"],
    }

    body = alert_body(body_data)
    topic = get_topic(payload)

    if body is not None:
        check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

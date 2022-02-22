# Webhooks for external integrations.
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

INCIDENT_TEMPLATE = """
**{name}**:
* State: **{state}**
* Description: {content}
""".strip()

COMPONENT_TEMPLATE = "**{name}** has changed status from **{old_status}** to **{new_status}**."

TOPIC_TEMPLATE = "{name}: {description}"

ALL_EVENT_TYPES = ["incident", "component"]


def get_incident_events_body(payload: Dict[str, Any]) -> str:
    return INCIDENT_TEMPLATE.format(
        name=payload["incident"]["name"],
        state=payload["incident"]["status"],
        content=payload["incident"]["incident_updates"][0]["body"],
    )


def get_components_update_body(payload: Dict[str, Any]) -> str:
    return COMPONENT_TEMPLATE.format(
        name=payload["component"]["name"],
        old_status=payload["component_update"]["old_status"],
        new_status=payload["component_update"]["new_status"],
    )


def get_incident_topic(payload: Dict[str, Any]) -> str:
    return TOPIC_TEMPLATE.format(
        name=payload["incident"]["name"],
        description=payload["page"]["status_description"],
    )


def get_component_topic(payload: Dict[str, Any]) -> str:
    return TOPIC_TEMPLATE.format(
        name=payload["component"]["name"],
        description=payload["page"]["status_description"],
    )


@webhook_view("Statuspage", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_statuspage_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:

    if "incident" in payload:
        event = "incident"
        topic = get_incident_topic(payload)
        body = get_incident_events_body(payload)
    elif "component" in payload:
        event = "component"
        topic = get_component_topic(payload)
        body = get_components_update_body(payload)
    else:
        raise UnsupportedWebhookEventType("unknown-event")

    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)

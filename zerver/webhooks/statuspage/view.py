# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
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


def get_incident_events_body(payload: WildValue) -> str:
    return INCIDENT_TEMPLATE.format(
        name=payload["incident"]["name"].tame(check_string),
        state=payload["incident"]["status"].tame(check_string),
        content=payload["incident"]["incident_updates"][0]["body"].tame(check_string),
    )


def get_components_update_body(payload: WildValue) -> str:
    return COMPONENT_TEMPLATE.format(
        name=payload["component"]["name"].tame(check_string),
        old_status=payload["component_update"]["old_status"].tame(check_string),
        new_status=payload["component_update"]["new_status"].tame(check_string),
    )


def get_incident_topic(payload: WildValue) -> str:
    return TOPIC_TEMPLATE.format(
        name=payload["incident"]["name"].tame(check_string),
        description=payload["page"]["status_description"].tame(check_string),
    )


def get_component_topic(payload: WildValue) -> str:
    return TOPIC_TEMPLATE.format(
        name=payload["component"]["name"].tame(check_string),
        description=payload["page"]["status_description"].tame(check_string),
    )


@webhook_view("Statuspage", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_statuspage_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
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
        raise UnsupportedWebhookEventTypeError("unknown-event")

    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)

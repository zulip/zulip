# Webhooks for external integrations.
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile
from django.http import HttpRequest, HttpResponse
from typing import Dict, Any

INCIDENT_TEMPLATE = u'**{name}** \n * State: **{state}** \n * Description: {content}'
COMPONENT_TEMPLATE = u'**{name}** has changed status from **{old_status}** to **{new_status}**'
TOPIC_TEMPLATE = u'{name}: {description}'

def get_incident_events_body(payload: Dict[str, Any]) -> str:
    return INCIDENT_TEMPLATE.format(
        name = payload["incident"]["name"],
        state = payload["incident"]["status"],
        content = payload["incident"]["incident_updates"][0]["body"],
    )

def get_components_update_body(payload: Dict[str, Any]) -> str:
    return COMPONENT_TEMPLATE.format(
        name = payload["component"]["name"],
        old_status = payload["component_update"]["old_status"],
        new_status = payload["component_update"]["new_status"],
    )

def get_incident_topic(payload: Dict[str, Any]) -> str:
    return TOPIC_TEMPLATE.format(
        name = payload["incident"]["name"],
        description = payload["page"]["status_description"],
    )

def get_component_topic(payload: Dict[str, Any]) -> str:
    return TOPIC_TEMPLATE.format(
        name = payload["component"]["name"],
        description = payload["page"]["status_description"],
    )

@api_key_only_webhook_view('Statuspage')
@has_request_variables
def api_statuspage_webhook(request: HttpRequest, user_profile: UserProfile,
                           payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    status = payload["page"]["status_indicator"]

    if status == "none":
        topic = get_incident_topic(payload)
        body = get_incident_events_body(payload)
    else:
        topic = get_component_topic(payload)
        body = get_components_update_body(payload)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

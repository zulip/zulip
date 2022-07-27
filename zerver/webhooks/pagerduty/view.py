from email.headerregistry import Address
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

PAGER_DUTY_EVENT_NAMES = {
    "incident.trigger": "triggered",
    "incident.acknowledge": "acknowledged",
    "incident.unacknowledge": "unacknowledged",
    "incident.resolve": "resolved",
    "incident.assign": "assigned",
    "incident.escalate": "escalated",
    "incident.delegate": "delineated",
}

PAGER_DUTY_EVENT_NAMES_V2 = {
    "incident.trigger": "triggered",
    "incident.acknowledge": "acknowledged",
    "incident.resolve": "resolved",
    "incident.assign": "assigned",
}

PAGER_DUTY_EVENT_NAMES_V3 = {
    "incident.triggered": "triggered",
    "incident.acknowledged": "acknowledged",
    "incident.unacknowledged": "unacknowledged",
    "incident.resolved": "resolved",
    "incident.reassigned": "reassigned",
}

ALL_EVENT_TYPES = [
    "resolved",
    "assigned",
    "unacknowledged",
    "acknowledged",
    "triggered",
    "reassigned",
]

AGENT_TEMPLATE = "[{username}]({url})"

INCIDENT_WITH_SERVICE_AND_ASSIGNEE = (
    "Incident [{incident_num_title}]({incident_url}) {action} by [{service_name}]"
    "({service_url}) (assigned to {assignee_info}).\n\n{trigger_message}"
)

TRIGGER_MESSAGE = "``` quote\n{message}\n```"

NUM_TITLE = "{incident_title} (#{incident_num})"

INCIDENT_WITH_ASSIGNEE = """
Incident [{incident_num_title}]({incident_url}) {action} by {assignee_info}.

{trigger_message}
""".strip()

INCIDENT_ASSIGNED = """
Incident [{incident_num_title}]({incident_url}) {action} to {assignee_info}.

{trigger_message}
""".strip()

INCIDENT_RESOLVED_WITH_AGENT = """
Incident [{incident_num_title}]({incident_url}) resolved by {agent_info}.

{trigger_message}
""".strip()

INCIDENT_RESOLVED = """
Incident [{incident_num_title}]({incident_url}) resolved.

{trigger_message}
""".strip()


def build_pagerduty_formatdict(message: Dict[str, Any]) -> Dict[str, Any]:
    format_dict: Dict[str, Any] = {}
    format_dict["action"] = PAGER_DUTY_EVENT_NAMES[message["type"]]

    format_dict["incident_id"] = message["data"]["incident"]["id"]
    format_dict["incident_num_title"] = message["data"]["incident"]["incident_number"]
    format_dict["incident_url"] = message["data"]["incident"]["html_url"]

    format_dict["service_name"] = message["data"]["incident"]["service"]["name"]
    format_dict["service_url"] = message["data"]["incident"]["service"]["html_url"]

    if message["data"]["incident"].get("assigned_to_user", None):
        assigned_to_user = message["data"]["incident"]["assigned_to_user"]
        format_dict["assignee_info"] = AGENT_TEMPLATE.format(
            username=Address(addr_spec=assigned_to_user["email"]).username,
            url=assigned_to_user["html_url"],
        )
    else:
        format_dict["assignee_info"] = "nobody"

    if message["data"]["incident"].get("resolved_by_user", None):
        resolved_by_user = message["data"]["incident"]["resolved_by_user"]
        format_dict["agent_info"] = AGENT_TEMPLATE.format(
            username=Address(addr_spec=resolved_by_user["email"]).username,
            url=resolved_by_user["html_url"],
        )

    trigger_message = []
    trigger_summary_data = message["data"]["incident"]["trigger_summary_data"]
    if trigger_summary_data is not None:
        trigger_subject = trigger_summary_data.get("subject", "")
        if trigger_subject:
            trigger_message.append(trigger_subject)

        trigger_description = trigger_summary_data.get("description", "")
        if trigger_description:
            trigger_message.append(trigger_description)

    format_dict["trigger_message"] = TRIGGER_MESSAGE.format(message="\n".join(trigger_message))
    return format_dict


def build_pagerduty_formatdict_v2(message: Dict[str, Any]) -> Dict[str, Any]:
    format_dict = {}
    format_dict["action"] = PAGER_DUTY_EVENT_NAMES_V2[message["event"]]

    format_dict["incident_id"] = message["incident"]["id"]
    format_dict["incident_num_title"] = message["incident"]["incident_number"]
    format_dict["incident_url"] = message["incident"]["html_url"]

    format_dict["service_name"] = message["incident"]["service"]["name"]
    format_dict["service_url"] = message["incident"]["service"]["html_url"]

    assignments = message["incident"]["assignments"]
    if assignments:
        assignee = assignments[0]["assignee"]
        format_dict["assignee_info"] = AGENT_TEMPLATE.format(
            username=assignee["summary"], url=assignee["html_url"]
        )
    else:
        format_dict["assignee_info"] = "nobody"

    last_status_change_by = message["incident"].get("last_status_change_by")
    if last_status_change_by is not None:
        format_dict["agent_info"] = AGENT_TEMPLATE.format(
            username=last_status_change_by["summary"],
            url=last_status_change_by["html_url"],
        )

    trigger_description = message["incident"].get("description")
    if trigger_description is not None:
        format_dict["trigger_message"] = TRIGGER_MESSAGE.format(message=trigger_description)
    return format_dict


def build_pagerduty_formatdict_v3(event: Dict[str, Any]) -> Dict[str, Any]:
    format_dict = {}
    format_dict["action"] = PAGER_DUTY_EVENT_NAMES_V3[event["event_type"]]

    format_dict["incident_id"] = event["data"]["id"]
    format_dict["incident_url"] = event["data"]["html_url"]
    format_dict["incident_num_title"] = NUM_TITLE.format(
        incident_num=event["data"]["number"], incident_title=event["data"]["title"]
    )

    format_dict["service_name"] = event["data"]["service"]["summary"]
    format_dict["service_url"] = event["data"]["service"]["html_url"]

    assignees = event["data"]["assignees"]
    if assignees:
        assignee = assignees[0]
        format_dict["assignee_info"] = AGENT_TEMPLATE.format(
            username=assignee["summary"], url=assignee["html_url"]
        )
    else:
        format_dict["assignee_info"] = "nobody"

    agent = event.get("agent")
    if agent is not None:
        format_dict["agent_info"] = AGENT_TEMPLATE.format(
            username=agent["summary"],
            url=agent["html_url"],
        )

    # V3 doesn't have trigger_message
    format_dict["trigger_message"] = ""

    return format_dict


def send_formated_pagerduty(
    request: HttpRequest, user_profile: UserProfile, message_type: str, format_dict: Dict[str, Any]
) -> None:
    if message_type in (
        "incident.trigger",
        "incident.triggered",
        "incident.unacknowledge",
        "incident.unacknowledged",
    ):
        template = INCIDENT_WITH_SERVICE_AND_ASSIGNEE
    elif (
        message_type == "incident.resolve" or message_type == "incident.resolved"
    ) and format_dict.get("agent_info") is not None:
        template = INCIDENT_RESOLVED_WITH_AGENT
    elif (
        message_type == "incident.resolve" or message_type == "incident.resolved"
    ) and format_dict.get("agent_info") is None:
        template = INCIDENT_RESOLVED
    elif message_type == "incident.assign" or message_type == "incident.reassigned":
        template = INCIDENT_ASSIGNED
    else:
        template = INCIDENT_WITH_ASSIGNEE

    subject = "Incident {incident_num_title}".format(**format_dict)
    body = template.format(**format_dict)
    check_send_webhook_message(request, user_profile, subject, body, format_dict["action"])


@webhook_view("PagerDuty", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_pagerduty_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    messages = payload.get("messages")

    if messages is not None:
        for message in messages:
            message_type = message.get("type")

            # If the message has no "type" key, then this payload came from a
            # Pagerduty Webhook V2.
            if message_type is None:
                break

            if message_type not in PAGER_DUTY_EVENT_NAMES:
                raise UnsupportedWebhookEventType(message_type)

            format_dict = build_pagerduty_formatdict(message)
            send_formated_pagerduty(request, user_profile, message_type, format_dict)

        for message in messages:
            event = message.get("event")

            # If the message has no "event" key, then this payload came from a
            # Pagerduty Webhook V1.
            if event is None:
                break

            if event not in PAGER_DUTY_EVENT_NAMES_V2:
                raise UnsupportedWebhookEventType(event)

            format_dict = build_pagerduty_formatdict_v2(message)
            send_formated_pagerduty(request, user_profile, event, format_dict)
    else:
        if "event" in payload:
            # V3 has no "messages" field, and it has key "event" instead
            event = payload["event"]
            event_type = event.get("event_type")

            if event_type not in PAGER_DUTY_EVENT_NAMES_V3:
                raise UnsupportedWebhookEventType(event_type)

            format_dict = build_pagerduty_formatdict_v3(event)
            send_formated_pagerduty(request, user_profile, event_type, format_dict)

    return json_success(request)

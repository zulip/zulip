from email.headerregistry import Address
from typing import TypeAlias

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_dict, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

FormatDictType: TypeAlias = dict[str, str | int]

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

ALL_EVENT_TYPES = [
    "triggered",
    "acknowledged",
    "unacknowledged",
    "resolved",
    "assigned",
    "reassigned",
    "escalated",
    "delegated",
    "reopened",
    "priority updated",
    "status updated",
    "annotated",
    "responder added",
    "responder replied",
    "conference bridge updated",
    "service updated",
    "workflow started",
    "workflow completed",
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

INCIDENT_ESCALATED = (
    """Incident [{incident_num_title}]({incident_url}) escalated to {assignee_info}."""
)

INCIDENT_DELEGATED = """Incident [{incident_num_title}]({incident_url}) delegated; {escalation_policy_clause}current assignee is {assignee_info}."""

INCIDENT_REOPENED = """Incident [{incident_num_title}]({incident_url}) reopened."""

INCIDENT_PRIORITY_UPDATED = (
    """Incident [{incident_num_title}]({incident_url}) priority updated to {event_details}"""
)

INCIDENT_STATUS_UPDATED = (
    """Incident [{incident_num_title}]({incident_url}) status update published: {event_details}"""
)

INCIDENT_ANNOTATED = (
    """Incident [{incident_num_title}]({incident_url}) annotated with: {event_details}"""
)

INCIDENT_RESPONDER_ADDED = """Responder {assignee_info} added to incident [{incident_num_title}]({incident_url}).

``` quote
{event_details}
```"""

INCIDENT_RESPONDER_REPLIED = """Responder {assignee_info} replied to incident [{incident_num_title}]({incident_url}).

``` quote
{event_details}
```"""

INCIDENT_CONFERENCE_BRIDGE_UPDATED = (
    """Incident [{incident_num_title}]({incident_url}) conference bridge updated: {event_details}"""
)

INCIDENT_SERVICE_UPDATED = (
    """Incident [{incident_num_title}]({incident_url}) service updated to {event_details}"""
)

INCIDENT_WORKFLOW_STARTED = (
    """Incident [{incident_num_title}]({incident_url}) workflow started: {event_details}"""
)

INCIDENT_WORKFLOW_COMPLETED = (
    """Incident [{incident_num_title}]({incident_url}) workflow completed: {event_details}"""
)

INCIDENT_WITH_SERVICE_EVENT_TYPES = {
    "incident.trigger",
    "incident.triggered",
    "incident.unacknowledge",
    "incident.unacknowledged",
}

INCIDENT_RESOLVED_EVENT_TYPES = {"incident.resolve", "incident.resolved"}
INCIDENT_ASSIGNED_EVENT_TYPES = {"incident.assign", "incident.reassigned"}

PAGER_DUTY_V3_EVENT_MAPPER: dict[str, tuple[str, str]] = {
    "incident.triggered": ("triggered", INCIDENT_WITH_SERVICE_AND_ASSIGNEE),
    "incident.acknowledged": ("acknowledged", INCIDENT_WITH_ASSIGNEE),
    "incident.unacknowledged": ("unacknowledged", INCIDENT_WITH_SERVICE_AND_ASSIGNEE),
    "incident.resolved": ("resolved", INCIDENT_RESOLVED),
    "incident.reassigned": ("reassigned", INCIDENT_ASSIGNED),
    "incident.escalated": ("escalated", INCIDENT_ESCALATED),
    "incident.delegated": ("delegated", INCIDENT_DELEGATED),
    "incident.reopened": ("reopened", INCIDENT_REOPENED),
    "incident.priority_updated": ("priority updated", INCIDENT_PRIORITY_UPDATED),
    "incident.status_update_published": ("status updated", INCIDENT_STATUS_UPDATED),
    "incident.annotated": ("annotated", INCIDENT_ANNOTATED),
    "incident.responder.added": ("responder added", INCIDENT_RESPONDER_ADDED),
    "incident.responder.replied": ("responder replied", INCIDENT_RESPONDER_REPLIED),
    "incident.conference_bridge.updated": (
        "conference bridge updated",
        INCIDENT_CONFERENCE_BRIDGE_UPDATED,
    ),
    "incident.service_updated": ("service updated", INCIDENT_SERVICE_UPDATED),
    "incident.workflow.started": ("workflow started", INCIDENT_WORKFLOW_STARTED),
    "incident.workflow.completed": ("workflow completed", INCIDENT_WORKFLOW_COMPLETED),
}


def build_pagerduty_formatdict(message: WildValue) -> FormatDictType:
    format_dict: FormatDictType = {}
    format_dict["action"] = PAGER_DUTY_EVENT_NAMES[message["type"].tame(check_string)]

    format_dict["incident_id"] = message["data"]["incident"]["id"].tame(check_string)
    format_dict["incident_num_title"] = message["data"]["incident"]["incident_number"].tame(
        check_int
    )
    format_dict["incident_url"] = message["data"]["incident"]["html_url"].tame(check_string)

    format_dict["service_name"] = message["data"]["incident"]["service"]["name"].tame(check_string)
    format_dict["service_url"] = message["data"]["incident"]["service"]["html_url"].tame(
        check_string
    )

    if message["data"]["incident"].get("assigned_to_user"):
        assigned_to_user = message["data"]["incident"]["assigned_to_user"]
        format_dict["assignee_info"] = AGENT_TEMPLATE.format(
            username=Address(addr_spec=assigned_to_user["email"].tame(check_string)).username,
            url=assigned_to_user["html_url"].tame(check_string),
        )
    else:
        format_dict["assignee_info"] = "nobody"

    if message["data"]["incident"].get("resolved_by_user"):
        resolved_by_user = message["data"]["incident"]["resolved_by_user"]
        format_dict["agent_info"] = AGENT_TEMPLATE.format(
            username=Address(addr_spec=resolved_by_user["email"].tame(check_string)).username,
            url=resolved_by_user["html_url"].tame(check_string),
        )

    trigger_message = []
    trigger_summary_data = message["data"]["incident"].get("trigger_summary_data")
    if trigger_summary_data:
        trigger_subject = trigger_summary_data.get("subject", "").tame(check_string)
        if trigger_subject:
            trigger_message.append(trigger_subject)

        trigger_description = trigger_summary_data.get("description", "").tame(check_string)
        if trigger_description:
            trigger_message.append(trigger_description)

    format_dict["trigger_message"] = TRIGGER_MESSAGE.format(message="\n".join(trigger_message))
    return format_dict


def build_pagerduty_formatdict_v2(message: WildValue) -> FormatDictType:
    format_dict: FormatDictType = {}
    format_dict["action"] = PAGER_DUTY_EVENT_NAMES_V2[message["event"].tame(check_string)]

    format_dict["incident_id"] = message["incident"]["id"].tame(check_string)
    format_dict["incident_num_title"] = message["incident"]["incident_number"].tame(check_int)
    format_dict["incident_url"] = message["incident"]["html_url"].tame(check_string)

    format_dict["service_name"] = message["incident"]["service"]["name"].tame(check_string)
    format_dict["service_url"] = message["incident"]["service"]["html_url"].tame(check_string)

    assignments = message["incident"]["assignments"]
    if assignments:
        assignee = assignments[0]["assignee"]
        format_dict["assignee_info"] = AGENT_TEMPLATE.format(
            username=assignee["summary"].tame(check_string),
            url=assignee["html_url"].tame(check_string),
        )
    else:
        format_dict["assignee_info"] = "nobody"

    last_status_change_by = message["incident"].get("last_status_change_by")
    if last_status_change_by is not None:
        format_dict["agent_info"] = AGENT_TEMPLATE.format(
            username=last_status_change_by["summary"].tame(check_string),
            url=last_status_change_by["html_url"].tame(check_string),
        )

    trigger_description = message["incident"].get("description").tame(check_none_or(check_string))
    if trigger_description is not None:
        format_dict["trigger_message"] = TRIGGER_MESSAGE.format(message=trigger_description)
    return format_dict


def get_v3_event_details(event_type: str, data: WildValue) -> str:
    """Extract event-specific detail text for V3 events."""
    match event_type:
        case "incident.priority_updated":
            priority = data.get("priority")
            if priority:
                return priority["summary"].tame(check_string)
        case "incident.status_update_published":
            return data["message"].tame(check_string)
        case "incident.annotated":
            return data["content"].tame(check_string)
        case "incident.responder.added" | "incident.responder.replied":
            return data["message"].tame(check_string)
        case "incident.conference_bridge.updated":
            conference_url = data.get("conference_url")
            if conference_url:
                return conference_url.tame(check_string)
        case "incident.service_updated":
            service = data.get("service")
            if service:
                return service["summary"].tame(check_string)
        case "incident.workflow.started" | "incident.workflow.completed":
            workflow = data["incident_workflow"]["summary"].tame(check_string)
            summary = data.get("summary", "").tame(check_string)
            if summary:
                return f"{workflow} ({summary})"
            return workflow
        case _:
            pass
    return ""


def build_pagerduty_formatdict_v3(event: WildValue) -> FormatDictType:
    format_dict: FormatDictType = {}
    event_type = event["event_type"].tame(check_string)
    action, _ = PAGER_DUTY_V3_EVENT_MAPPER[event_type]
    format_dict["action"] = action

    data = event["data"]
    incident = data.get("incident")
    if incident:
        format_dict["incident_id"] = incident["id"].tame(check_string)
        format_dict["incident_url"] = incident["html_url"].tame(check_string)
        format_dict["incident_num_title"] = incident["summary"].tame(check_string)
    else:
        format_dict["incident_id"] = data["id"].tame(check_string)
        format_dict["incident_url"] = data["html_url"].tame(check_string)
        format_dict["incident_num_title"] = NUM_TITLE.format(
            incident_num=data["number"].tame(check_int),
            incident_title=data["title"].tame(check_string),
        )

    service = data.get("service")
    if service:
        format_dict["service_name"] = service["summary"].tame(check_string)
        format_dict["service_url"] = service["html_url"].tame(check_string)
    else:
        format_dict["service_name"] = ""
        format_dict["service_url"] = ""

    assignees = data.get("assignees")
    if assignees:
        assignee = assignees[0]
        format_dict["assignee_info"] = AGENT_TEMPLATE.format(
            username=assignee["summary"].tame(check_string),
            url=assignee["html_url"].tame(check_string),
        )
    elif data.get("user"):
        user = data["user"]
        format_dict["assignee_info"] = AGENT_TEMPLATE.format(
            username=user["summary"].tame(check_string),
            url=user["html_url"].tame(check_string),
        )
    else:
        format_dict["assignee_info"] = "nobody"

    escalation_policy = data.get("escalation_policy")
    if escalation_policy:
        format_dict["escalation_policy_clause"] = (
            "current escalation policy is [{name}]({url}) and ".format(
                name=escalation_policy["summary"].tame(check_string),
                url=escalation_policy["html_url"].tame(check_string),
            )
        )
    else:
        format_dict["escalation_policy_clause"] = ""

    agent = event.get("agent").tame(
        check_none_or(check_dict([("summary", check_string), ("html_url", check_string)]))
    )
    if agent is not None:
        format_dict["agent_info"] = AGENT_TEMPLATE.format(
            username=agent["summary"],
            url=agent["html_url"],
        )

    format_dict["trigger_message"] = ""
    format_dict["event_details"] = get_v3_event_details(event_type, data)

    return format_dict


def send_formatted_pagerduty(
    request: HttpRequest,
    user_profile: UserProfile,
    message_type: str,
    format_dict: FormatDictType,
) -> None:
    if message_type in INCIDENT_WITH_SERVICE_EVENT_TYPES:
        template = INCIDENT_WITH_SERVICE_AND_ASSIGNEE
    elif message_type in INCIDENT_ASSIGNED_EVENT_TYPES:
        template = INCIDENT_ASSIGNED
    elif message_type in INCIDENT_RESOLVED_EVENT_TYPES:
        if "agent_info" in format_dict:
            template = INCIDENT_RESOLVED_WITH_AGENT
        else:
            template = INCIDENT_RESOLVED
    else:
        event_config = PAGER_DUTY_V3_EVENT_MAPPER.get(message_type)
        if event_config is not None:
            _, template = event_config
        else:
            template = INCIDENT_WITH_ASSIGNEE

    topic_name = "Incident {incident_num_title}".format(**format_dict)
    body = template.format(**format_dict)
    action = format_dict["action"]
    assert isinstance(action, str)
    check_send_webhook_message(request, user_profile, topic_name, body, action)


@webhook_view("PagerDuty", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_pagerduty_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    messages = payload.get("messages")
    if messages:
        for message in messages:
            message_type = message.get("type").tame(check_none_or(check_string))

            # If the message has no "type" key, then this payload came from a
            # Pagerduty Webhook V2.
            if message_type is None:
                break

            if message_type not in PAGER_DUTY_EVENT_NAMES:
                raise UnsupportedWebhookEventTypeError(message_type)

            format_dict = build_pagerduty_formatdict(message)
            send_formatted_pagerduty(request, user_profile, message_type, format_dict)

        for message in messages:
            message_event = message.get("event").tame(check_none_or(check_string))

            # If the message has no "event" key, then this payload came from a
            # Pagerduty Webhook V1.
            if message_event is None:
                break

            if message_event not in PAGER_DUTY_EVENT_NAMES_V2:
                raise UnsupportedWebhookEventTypeError(message_event)

            format_dict = build_pagerduty_formatdict_v2(message)
            send_formatted_pagerduty(request, user_profile, message_event, format_dict)
    else:
        if "event" in payload:
            # V3 has no "messages" field, and it has key "event" instead
            event = payload["event"]
            event_type = event.get("event_type").tame(check_none_or(check_string))

            if event_type not in PAGER_DUTY_V3_EVENT_MAPPER:
                raise UnsupportedWebhookEventTypeError(event_type)

            format_dict = build_pagerduty_formatdict_v3(event)
            send_formatted_pagerduty(request, user_profile, event_type, format_dict)

    return json_success(request)

from typing import Dict, List

import dateutil.parser
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_send import send_rate_limited_pm_notification_to_bot_owner
from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

MISCONFIGURED_PAYLOAD_ERROR_MESSAGE = """
Hi there! Your bot {bot_name} just received a Freshstatus payload that is missing
some data that Zulip requires. This usually indicates a configuration issue
in your Freshstatus webhook settings. Please make sure that you provide all the required parameters
when configuring the Freshstatus webhook. Contact {support_email} if you
need further help!
"""

FRESHSTATUS_TOPIC_TEMPLATE = "{title}".strip()
FRESHSTATUS_TOPIC_TEMPLATE_TEST = "Freshstatus"

FRESHSTATUS_MESSAGE_TEMPLATE_INCIDENT_OPEN = """
The following incident has been opened: **{title}**
**Description:** {description}
**Start Time:** {start_time}
**Affected Services:**
{affected_services}
""".strip()

FRESHSTATUS_MESSAGE_TEMPLATE_INCIDENT_CLOSED = """
The following incident has been closed: **{title}**
**Note:** {message}
""".strip()

FRESHSTATUS_MESSAGE_TEMPLATE_INCIDENT_NOTE_CREATED = """
The following note has been added to the incident: **{title}**
**Note:** {message}
""".strip()

FRESHSTATUS_MESSAGE_TEMPLATE_SCHEDULED_MAINTENANCE_PLANNED = """
The following scheduled maintenance has been opened: **{title}**
**Description:** {description}
**Scheduled Start Time:** {scheduled_start_time}
**Scheduled End Time:** {scheduled_end_time}
**Affected Services:**
{affected_services}
""".strip()

FRESHSTATUS_MESSAGE_TEMPLATE_SCHEDULED_MAINTENANCE_CLOSED = """
The following scheduled maintenance has been closed: **{title}**
**Note:** {message}
""".strip()

FRESHSTATUS_MESSAGE_TEMPLATE_SCHEDULED_MAINTENANCE_NOTE_CREATED = """
The following note has been added to the scheduled maintenance: **{title}**
**Note:** {message}
""".strip()

FRESHSTATUS_MESSAGE_EVENT_NOT_SUPPORTED = "The event ({event_type}) is not supported yet."

FRESHSTATUS_SERVICES_ROW_TEMPLATE = "* {service_name}\n"
FRESHSTATUS_SERVICES_OTHERS_ROW_TEMPLATE = "[and {services_number} more service(s)]"
FRESHSTATUS_SERVICES_LIMIT = 5

ALL_EVENT_TYPES = [
    "MAINTENANCE_NOTE_CREATE",
    "INCIDENT_NOTE_CREATE",
    "INCIDENT_OPEN",
    "MAINTENANCE_PLANNED",
    "INCIDENT_REOPEN",
]


@webhook_view("Freshstatus", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_freshstatus_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    try:
        body = get_body_for_http_request(payload)
        subject = get_subject_for_http_request(payload)
    except ValidationError:
        message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=user_profile.full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()
        send_rate_limited_pm_notification_to_bot_owner(user_profile, user_profile.realm, message)

        raise JsonableError(_("Invalid payload"))

    check_send_webhook_message(
        request, user_profile, subject, body, payload["event_data"]["event_type"].tame(check_string)
    )
    return json_success(request)


def get_services_content(services_data: List[Dict[str, str]]) -> str:
    services_content = ""
    for service in services_data[:FRESHSTATUS_SERVICES_LIMIT]:
        services_content += FRESHSTATUS_SERVICES_ROW_TEMPLATE.format(
            service_name=service.get("service_name")
        )

    if len(services_data) > FRESHSTATUS_SERVICES_LIMIT:
        services_content += FRESHSTATUS_SERVICES_OTHERS_ROW_TEMPLATE.format(
            services_number=len(services_data) - FRESHSTATUS_SERVICES_LIMIT,
        )
    return services_content.rstrip()


def get_subject_for_http_request(payload: WildValue) -> str:
    event_data = payload["event_data"]
    if (
        event_data["event_type"].tame(check_string) == "INCIDENT_OPEN"
        and payload["id"].tame(check_string) == "1"
    ):
        return FRESHSTATUS_TOPIC_TEMPLATE_TEST
    else:
        return FRESHSTATUS_TOPIC_TEMPLATE.format(title=payload["title"].tame(check_string))


def get_body_for_maintenance_planned_event(payload: WildValue) -> str:
    services_data = []
    for service in payload["affected_services"].tame(check_string).split(","):
        services_data.append({"service_name": service})
    data = {
        "title": payload["title"].tame(check_string),
        "description": payload["description"].tame(check_string),
        "scheduled_start_time": dateutil.parser.parse(
            payload["scheduled_start_time"].tame(check_string)
        ).strftime("%Y-%m-%d %H:%M %Z"),
        "scheduled_end_time": dateutil.parser.parse(
            payload["scheduled_end_time"].tame(check_string)
        ).strftime("%Y-%m-%d %H:%M %Z"),
        "affected_services": get_services_content(services_data),
    }
    return FRESHSTATUS_MESSAGE_TEMPLATE_SCHEDULED_MAINTENANCE_PLANNED.format(**data)


def get_body_for_incident_open_event(payload: WildValue) -> str:
    services_data = []
    for service in payload["affected_services"].tame(check_string).split(","):
        services_data.append({"service_name": service})
    data = {
        "title": payload["title"].tame(check_string),
        "description": payload["description"].tame(check_string),
        "start_time": dateutil.parser.parse(payload["start_time"].tame(check_string)).strftime(
            "%Y-%m-%d %H:%M %Z"
        ),
        "affected_services": get_services_content(services_data),
    }
    return FRESHSTATUS_MESSAGE_TEMPLATE_INCIDENT_OPEN.format(**data)


def get_body_for_http_request(payload: WildValue) -> str:
    event_data = payload["event_data"]
    event_type = event_data["event_type"].tame(check_string)
    if event_type == "INCIDENT_OPEN" and payload["id"].tame(check_string) == "1":
        return get_setup_webhook_message("Freshstatus")
    elif event_type == "INCIDENT_OPEN":
        return get_body_for_incident_open_event(payload)
    elif event_type == "INCIDENT_NOTE_CREATE":
        incident_status = payload["incident_status"].tame(check_string)
        title = payload["title"].tame(check_string)
        message = payload["message"].tame(check_string)
        if incident_status == "Closed":
            return FRESHSTATUS_MESSAGE_TEMPLATE_INCIDENT_CLOSED.format(title=title, message=message)
        elif incident_status == "Open":
            return FRESHSTATUS_MESSAGE_TEMPLATE_INCIDENT_NOTE_CREATED.format(
                title=title, message=message
            )
    elif event_type == "MAINTENANCE_PLANNED":
        return get_body_for_maintenance_planned_event(payload)
    elif event_type == "MAINTENANCE_NOTE_CREATE":
        title = payload["title"].tame(check_string)
        message = payload["message"].tame(check_string)
        if payload["incident_status"].tame(check_string) == "Closed":
            return FRESHSTATUS_MESSAGE_TEMPLATE_SCHEDULED_MAINTENANCE_CLOSED.format(
                title=title, message=message
            )
        else:
            return FRESHSTATUS_MESSAGE_TEMPLATE_SCHEDULED_MAINTENANCE_NOTE_CREATED.format(
                title=title, message=message
            )

    return FRESHSTATUS_MESSAGE_EVENT_NOT_SUPPORTED.format(event_type=event_type)

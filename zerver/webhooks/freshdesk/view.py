"""Webhooks for external integrations."""
from typing import List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.email_notifications import convert_html_to_markdown
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

NOTE_TEMPLATE = "{name} <{email}> added a {note_type} note to [ticket #{ticket_id}]({ticket_url})."
PROPERTY_CHANGE_TEMPLATE = """
{name} <{email}> updated [ticket #{ticket_id}]({ticket_url}):

* **{property_name}**: {old} -> {new}
""".strip()
TICKET_CREATION_TEMPLATE = """
{name} <{email}> created [ticket #{ticket_id}]({ticket_url}):

``` quote
{description}
```

* **Type**: {type}
* **Priority**: {priority}
* **Status**: {status}
""".strip()


def property_name(property: str, index: int) -> str:
    """The Freshdesk API is currently pretty broken: statuses are customizable
    but the API will only tell you the number associated with the status, not
    the name. While we engage the Freshdesk developers about exposing this
    information through the API, since only FlightCar uses this integration,
    hardcode their statuses.
    """
    statuses = [
        "",
        "",
        "Open",
        "Pending",
        "Resolved",
        "Closed",
        "Waiting on Customer",
        "Job Application",
        "Monthly",
    ]
    priorities = ["", "Low", "Medium", "High", "Urgent"]

    name = ""
    if property == "status":
        name = statuses[index] if index < len(statuses) else str(index)
    elif property == "priority":
        name = priorities[index] if index < len(priorities) else str(index)

    return name


def parse_freshdesk_event(event_string: str) -> List[str]:
    """These are always of the form "{ticket_action:created}" or
    "{status:{from:4,to:6}}". Note the lack of string quoting: this isn't
    valid JSON so we have to parse it ourselves.
    """
    data = event_string.replace("{", "").replace("}", "").replace(",", ":").split(":")

    if len(data) == 2:
        # This is a simple ticket action event, like
        # {ticket_action:created}.
        return data
    else:
        # This is a property change event, like {status:{from:4,to:6}}. Pull out
        # the property, from, and to states.
        property, _, from_state, _, to_state = data
        return [
            property,
            property_name(property, int(from_state)),
            property_name(property, int(to_state)),
        ]


def format_freshdesk_note_message(ticket: WildValue, event_info: List[str]) -> str:
    """There are public (visible to customers) and private note types."""
    note_type = event_info[1]
    content = NOTE_TEMPLATE.format(
        name=ticket["requester_name"].tame(check_string),
        email=ticket["requester_email"].tame(check_string),
        note_type=note_type,
        ticket_id=ticket["ticket_id"].tame(check_string),
        ticket_url=ticket["ticket_url"].tame(check_string),
    )

    return content


def format_freshdesk_property_change_message(ticket: WildValue, event_info: List[str]) -> str:
    """Freshdesk will only tell us the first event to match our webhook
    configuration, so if we change multiple properties, we only get the before
    and after data for the first one.
    """
    content = PROPERTY_CHANGE_TEMPLATE.format(
        name=ticket["requester_name"].tame(check_string),
        email=ticket["requester_email"].tame(check_string),
        ticket_id=ticket["ticket_id"].tame(check_string),
        ticket_url=ticket["ticket_url"].tame(check_string),
        property_name=event_info[0].capitalize(),
        old=event_info[1],
        new=event_info[2],
    )

    return content


def format_freshdesk_ticket_creation_message(ticket: WildValue) -> str:
    """They send us the description as HTML."""
    cleaned_description = convert_html_to_markdown(ticket["ticket_description"].tame(check_string))
    content = TICKET_CREATION_TEMPLATE.format(
        name=ticket["requester_name"].tame(check_string),
        email=ticket["requester_email"].tame(check_string),
        ticket_id=ticket["ticket_id"].tame(check_string),
        ticket_url=ticket["ticket_url"].tame(check_string),
        description=cleaned_description,
        type=ticket["ticket_type"].tame(check_string),
        priority=ticket["ticket_priority"].tame(check_string),
        status=ticket["ticket_status"].tame(check_string),
    )

    return content


@authenticated_rest_api_view(webhook_client_name="Freshdesk")
@typed_endpoint
def api_freshdesk_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    ticket = payload["freshdesk_webhook"]

    topic = (
        f"#{ticket['ticket_id'].tame(check_string)}: {ticket['ticket_subject'].tame(check_string)}"
    )
    event_info = parse_freshdesk_event(ticket["triggered_event"].tame(check_string))

    if event_info[1] == "created":
        content = format_freshdesk_ticket_creation_message(ticket)
    elif event_info[0] == "note_type":
        content = format_freshdesk_note_message(ticket, event_info)
    elif event_info[0] in ("status", "priority"):
        content = format_freshdesk_property_change_message(ticket, event_info)
    else:
        # Not an event we know handle; do nothing.
        return json_success(request)

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success(request)

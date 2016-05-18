"""Webhooks for external integrations."""
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.models import get_client, UserProfile
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.lib.notifications import convert_html_to_markdown
from zerver.decorator import REQ, has_request_variables, authenticated_rest_api_view

import logging
import ujson

from six import text_type
from typing import Any, Dict, Optional, Tuple, Union


class TicketDict(dict):
    """
    A helper class to turn a dictionary with ticket information into
    an object where each of the keys is an attribute for easy access.
    """

    def __getattr__(self, field):
        # type: (str) -> Any
        if "_" in field:
            return self.get(field)
        else:
            return self.get("ticket_" + field)


def property_name(property, index):
    # type: (str, int) -> str
    """The Freshdesk API is currently pretty broken: statuses are customizable
    but the API will only tell you the number associated with the status, not
    the name. While we engage the Freshdesk developers about exposing this
    information through the API, since only FlightCar uses this integration,
    hardcode their statuses.
    """
    statuses = ["", "", "Open", "Pending", "Resolved", "Closed",
                "Waiting on Customer", "Job Application", "Monthly"]
    priorities = ["", "Low", "Medium", "High", "Urgent"]

    if property == "status":
        return statuses[index] if index < len(statuses) else str(index)
    elif property == "priority":
        return priorities[index] if index < len(priorities) else str(index)
    else:
        raise ValueError("Unknown property")


def parse_freshdesk_event(event_string):
    # type: (str) -> List[str]
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
        return [property, property_name(property, int(from_state)),
                property_name(property, int(to_state))]


def format_freshdesk_note_message(ticket, event_info):
    # type: (TicketDict, List[str]) -> str
    """There are public (visible to customers) and private note types."""
    note_type = event_info[1]
    content = "%s <%s> added a %s note to [ticket #%s](%s)." % (
        ticket.requester_name, ticket.requester_email, note_type,
        ticket.id, ticket.url)

    return content


def format_freshdesk_property_change_message(ticket, event_info):
    # type: (TicketDict, List[str]) -> str
    """Freshdesk will only tell us the first event to match our webhook
    configuration, so if we change multiple properties, we only get the before
    and after data for the first one.
    """
    content = "%s <%s> updated [ticket #%s](%s):\n\n" % (
        ticket.requester_name, ticket.requester_email, ticket.id, ticket.url)
    # Why not `"%s %s %s" % event_info`? Because the linter doesn't like it.
    content += "%s: **%s** => **%s**" % (
        event_info[0].capitalize(), event_info[1], event_info[2])

    return content


def format_freshdesk_ticket_creation_message(ticket):
    # type: (TicketDict) -> str
    """They send us the description as HTML."""
    cleaned_description = convert_html_to_markdown(ticket.description)
    content = "%s <%s> created [ticket #%s](%s):\n\n" % (
        ticket.requester_name, ticket.requester_email, ticket.id, ticket.url)
    content += """~~~ quote
%s
~~~\n
""" % (cleaned_description,)
    content += "Type: **%s**\nPriority: **%s**\nStatus: **%s**" % (
        ticket.type, ticket.priority, ticket.status)

    return content

@authenticated_rest_api_view(is_webhook=True)
@has_request_variables
def api_freshdesk_webhook(request, user_profile, payload=REQ(argument_type='body'),
                          stream=REQ(default='freshdesk')):
    # type: (HttpRequest, UserProfile, Dict[str, Any], text_type) -> HttpResponse
    ticket_data = payload["freshdesk_webhook"]

    required_keys = [
        "triggered_event", "ticket_id", "ticket_url", "ticket_type",
        "ticket_subject", "ticket_description", "ticket_status",
        "ticket_priority", "requester_name", "requester_email",
        ]

    for key in required_keys:
        if ticket_data.get(key) is None:
            logging.warning("Freshdesk webhook error. Payload was:")
            logging.warning(request.body)
            return json_error(_("Missing key %s in JSON") % (key,))

    ticket = TicketDict(ticket_data)

    subject = "#%s: %s" % (ticket.id, ticket.subject)

    try:
        event_info = parse_freshdesk_event(ticket.triggered_event)
    except ValueError:
        return json_error(_("Malformed event %s") % (ticket.triggered_event,))

    if event_info[1] == "created":
        content = format_freshdesk_ticket_creation_message(ticket)
    elif event_info[0] == "note_type":
        content = format_freshdesk_note_message(ticket, event_info)
    elif event_info[0] in ("status", "priority"):
        content = format_freshdesk_property_change_message(ticket, event_info)
    else:
        # Not an event we know handle; do nothing.
        return json_success()

    check_send_message(user_profile, get_client("ZulipFreshdeskWebhook"), "stream",
                       [stream], subject, content)
    return json_success()

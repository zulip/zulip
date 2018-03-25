# Webhooks for external integrations.
from typing import Any, Dict, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

import logging

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

def ticket_started_body(payload: Dict[str, Any]) -> Text:
    body = u'New ticket from {customer_name}'
    body += u"\n```quote\n**[Ticket #{number}: {title}]({app_url})**\n{summary}\n```"
    return body.format(**payload)

def ticket_assigned_body(payload: Dict[str, Any]) -> Optional[Text]:
    # Take the state, assignee, and assigned group from the payload.
    state = payload['state']
    assignee = payload['assignee']
    assigned_group = payload['assigned_group']

    # There are three states on a ticket: opened,
    # pending, and closed. This creates the message
    # based on the state of the ticket.
    if state == "opened":
        body = u"An open ticket has been assigned to"
    else:
        body = u"A {state} ticket has been assigned to"

    # If there is a person and/or a group assigned,
    # make a notification message. Otherwise, ignore it.
    if assignee or assigned_group:
        if assignee and assigned_group:
            body += u" {assignee} from {assigned_group}"
        elif assignee:
            body += u" {assignee}"
        elif assigned_group:
            body += u" {assigned_group}"
        body += u"\n```quote\n**[Ticket #{number}: {title}]({app_url})**\n```"
        return body.format(**payload)
    else:
        return None

def agent_replied_body(payload: Dict[str, Any]) -> Text:
    # Take the agent's email and the ticket number from the payload.
    agent = payload['links']['author']['href'].split("http://api.groovehq.com/v1/agents/")[1]
    number = payload['links']['ticket']['href'].split("http://api.groovehq.com/v1/tickets/")[1]

    # Create the notification message.
    body = u"%s has just replied to a ticket\n```quote\n**[Ticket #%s]" % (agent, number)
    body += u"({app_ticket_url})**\n{plain_text_body}\n```"
    return body.format(**payload)

def customer_replied_body(payload: Dict[str, Any]) -> Text:
    # Take the customer's email and the ticket number from the payload.
    customer = payload['links']['author']['href'].split("http://api.groovehq.com/v1/customers/")[1]
    number = payload['links']['ticket']['href'].split("http://api.groovehq.com/v1/tickets/")[1]

    # Create the notification message.
    body = u"%s has just replied to a ticket\n```quote\n**[Ticket #%s]" % (customer, number)
    body += u"({app_ticket_url})**\n{plain_text_body}\n```"
    return body.format(**payload)

def note_added_body(payload: Dict[str, Any]) -> Text:
    # Take the agent's email and the ticket number from the payload.
    agent = payload['links']['author']['href'].split("http://api.groovehq.com/v1/agents/")[1]
    number = payload['links']['ticket']['href'].split("http://api.groovehq.com/v1/tickets/")[1]

    # Create the notification message.
    body = u"%s has left a note\n```quote\n**[Ticket #%s]" % (agent, number)
    body += u"({app_ticket_url})**\n{plain_text_body}\n```"
    return body.format(**payload)

@api_key_only_webhook_view('Groove')
@has_request_variables
def api_groove_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    try:
        # The event identifier is stored in the X_GROOVE_EVENT header.
        event = request.META['X_GROOVE_EVENT']
    except KeyError:
        logging.error('No header with the Groove payload')
        return json_error(_('Missing event header'))
    # We listen to several events that are used for notifications.
    # Other events are ignored.
    if event in EVENTS_FUNCTION_MAPPER:
        try:
            body = EVENTS_FUNCTION_MAPPER[event](payload)
        except KeyError as e:
            logging.error('Required key not found : ' + e.args[0])
            return json_error(_('Missing required data'))
        if body is not None:
            topic = 'notifications'
            check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

EVENTS_FUNCTION_MAPPER = {
    'ticket_started': ticket_started_body,
    'ticket_assigned': ticket_assigned_body,
    'agent_replied': agent_replied_body,
    'customer_replied': customer_replied_body,
    'note_added': note_added_body
}

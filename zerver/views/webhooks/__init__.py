# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.notifications import convert_html_to_markdown
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, \
    has_request_variables, authenticated_rest_api_view, \
    api_key_only_webhook_view

import pprint
import logging
import ujson

from .github import build_commit_list_content, build_message_from_gitlog


class TicketDict(dict):
    """
    A helper class to turn a dictionary with ticket information into
    an object where each of the keys is an attribute for easy access.
    """
    def __getattr__(self, field):
        if "_" in field:
            return self.get(field)
        else:
            return self.get("ticket_" + field)

def property_name(property, index):
    # The Freshdesk API is currently pretty broken: statuses are customizable
    # but the API will only tell you the number associated with the status, not
    # the name. While we engage the Freshdesk developers about exposing this
    # information through the API, since only FlightCar uses this integration,
    # hardcode their statuses.
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
    # These are always of the form "{ticket_action:created}" or
    # "{status:{from:4,to:6}}". Note the lack of string quoting: this isn't
    # valid JSON so we have to parse it ourselves.
    data = event_string.replace("{", "").replace("}", "").replace(",", ":").split(":")

    if len(data) == 2:
        # This is a simple ticket action event, like
        # {ticket_action:created}.
        return data
    else:
        # This is a property change event, like {status:{from:4,to:6}}. Pull out
        # the property, from, and to states.
        property, _, from_state, _, to_state = data
        return (property, property_name(property, int(from_state)),
                property_name(property, int(to_state)))

def format_freshdesk_note_message(ticket, event_info):
    # There are public (visible to customers) and private note types.
    note_type = event_info[1]
    content = "%s <%s> added a %s note to [ticket #%s](%s)." % (
        ticket.requester_name, ticket.requester_email, note_type,
        ticket.id, ticket.url)

    return content

def format_freshdesk_property_change_message(ticket, event_info):
    # Freshdesk will only tell us the first event to match our webhook
    # configuration, so if we change multiple properties, we only get the before
    # and after data for the first one.
    content = "%s <%s> updated [ticket #%s](%s):\n\n" % (
        ticket.requester_name, ticket.requester_email, ticket.id, ticket.url)
    # Why not `"%s %s %s" % event_info`? Because the linter doesn't like it.
    content += "%s: **%s** => **%s**" % (
        event_info[0].capitalize(), event_info[1], event_info[2])

    return content

def format_freshdesk_ticket_creation_message(ticket):
    # They send us the description as HTML.
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

@authenticated_rest_api_view
@has_request_variables
def api_freshdesk_webhook(request, user_profile, stream=REQ(default='')):
    try:
        payload = ujson.loads(request.body)
        ticket_data = payload["freshdesk_webhook"]
    except ValueError:
        return json_error("Malformed JSON input")

    required_keys = [
        "triggered_event", "ticket_id", "ticket_url", "ticket_type",
        "ticket_subject", "ticket_description", "ticket_status",
        "ticket_priority", "requester_name", "requester_email",
        ]

    for key in required_keys:
        if ticket_data.get(key) is None:
            logging.warning("Freshdesk webhook error. Payload was:")
            logging.warning(request.body)
            return json_error("Missing key %s in JSON" % (key,))

    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        stream = 'freshdesk'

    ticket = TicketDict(ticket_data)

    subject = "#%s: %s" % (ticket.id, ticket.subject)

    try:
        event_info = parse_freshdesk_event(ticket.triggered_event)
    except ValueError:
        return json_error("Malformed event %s" % (ticket.triggered_event,))

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

def truncate(string, length):
    if len(string) > length:
        string = string[:length-3] + '...'
    return string

@authenticated_rest_api_view
def api_zendesk_webhook(request, user_profile):
    """
    Zendesk uses trigers with message templates. This webhook uses the
    ticket_id and ticket_title to create a subject. And passes with zendesk
    user's configured message to zulip.
    """
    try:
        ticket_title = request.POST['ticket_title']
        ticket_id = request.POST['ticket_id']
        message = request.POST['message']
        stream = request.POST.get('stream', 'zendesk')
    except KeyError as e:
        return json_error('Missing post parameter %s' % (e.message,))

    subject = truncate('#%s: %s' % (ticket_id, ticket_title), 60)
    check_send_message(user_profile, get_client('ZulipZenDeskWebhook'), 'stream',
                       [stream], subject, message)
    return json_success()


PAGER_DUTY_EVENT_NAMES = {
    'incident.trigger': 'triggered',
    'incident.acknowledge': 'acknowledged',
    'incident.unacknowledge': 'unacknowledged',
    'incident.resolve': 'resolved',
    'incident.assign': 'assigned',
    'incident.escalate': 'escalated',
    'incident.delegate': 'delineated',
}

def build_pagerduty_formatdict(message):
    # Normalize the message dict, after this all keys will exist. I would
    # rather some strange looking messages than dropping pages.

    format_dict = {}
    format_dict['action'] = PAGER_DUTY_EVENT_NAMES[message['type']]

    format_dict['incident_id'] = message['data']['incident']['id']
    format_dict['incident_num'] = message['data']['incident']['incident_number']
    format_dict['incident_url'] = message['data']['incident']['html_url']

    format_dict['service_name'] = message['data']['incident']['service']['name']
    format_dict['service_url'] = message['data']['incident']['service']['html_url']

    # This key can be missing on null
    if message['data']['incident'].get('assigned_to_user', None):
        format_dict['assigned_to_email'] = message['data']['incident']['assigned_to_user']['email']
        format_dict['assigned_to_username'] = message['data']['incident']['assigned_to_user']['email'].split('@')[0]
        format_dict['assigned_to_url'] = message['data']['incident']['assigned_to_user']['html_url']
    else:
        format_dict['assigned_to_email'] = 'nobody'
        format_dict['assigned_to_username'] = 'nobody'
        format_dict['assigned_to_url'] = ''

    # This key can be missing on null
    if message['data']['incident'].get('resolved_by_user', None):
        format_dict['resolved_by_email'] = message['data']['incident']['resolved_by_user']['email']
        format_dict['resolved_by_username'] = message['data']['incident']['resolved_by_user']['email'].split('@')[0]
        format_dict['resolved_by_url'] = message['data']['incident']['resolved_by_user']['html_url']
    else:
        format_dict['resolved_by_email'] = 'nobody'
        format_dict['resolved_by_username'] = 'nobody'
        format_dict['resolved_by_url'] = ''

    trigger_message = []
    trigger_subject = message['data']['incident']['trigger_summary_data'].get('subject', '')
    if trigger_subject:
        trigger_message.append(trigger_subject)
    trigger_description = message['data']['incident']['trigger_summary_data'].get('description', '')
    if trigger_description:
        trigger_message.append(trigger_description)
    format_dict['trigger_message'] = u'\n'.join(trigger_message)
    return format_dict


def send_raw_pagerduty_json(user_profile, stream, message, topic):
    subject = topic or 'pagerduty'
    body = (
        u'Unknown pagerduty message\n'
        u'``` py\n'
        u'%s\n'
        u'```') % (pprint.pformat(message),)
    check_send_message(user_profile, get_client('ZulipPagerDutyWebhook'), 'stream',
                       [stream], subject, body)


def send_formated_pagerduty(user_profile, stream, message_type, format_dict, topic):
    if message_type in ('incident.trigger', 'incident.unacknowledge'):
        template = (u':imp: Incident '
        u'[{incident_num}]({incident_url}) {action} by '
        u'[{service_name}]({service_url}) and assigned to '
        u'[{assigned_to_username}@]({assigned_to_url})\n\n>{trigger_message}')

    elif message_type == 'incident.resolve' and format_dict['resolved_by_url']:
        template = (u':grinning: Incident '
        u'[{incident_num}]({incident_url}) resolved by '
        u'[{resolved_by_username}@]({resolved_by_url})\n\n>{trigger_message}')
    elif message_type == 'incident.resolve' and not format_dict['resolved_by_url']:
        template = (u':grinning: Incident '
        u'[{incident_num}]({incident_url}) resolved\n\n>{trigger_message}')
    else:
        template = (u':no_good: Incident [{incident_num}]({incident_url}) '
        u'{action} by [{assigned_to_username}@]({assigned_to_url})\n\n>{trigger_message}')

    subject = topic or u'incident {incident_num}'.format(**format_dict)
    body = template.format(**format_dict)

    check_send_message(user_profile, get_client('ZulipPagerDutyWebhook'), 'stream',
                       [stream], subject, body)


@api_key_only_webhook_view
@has_request_variables
def api_pagerduty_webhook(request, user_profile, stream=REQ(default='pagerduty'), topic=REQ(default=None)):
    payload = ujson.loads(request.body)

    for message in payload['messages']:
        message_type = message['type']

        if message_type not in PAGER_DUTY_EVENT_NAMES:
            send_raw_pagerduty_json(user_profile, stream, message, topic)

        try:
            format_dict = build_pagerduty_formatdict(message)
        except:
            send_raw_pagerduty_json(user_profile, stream, message, topic)
        else:
            send_formated_pagerduty(user_profile, stream, message_type, format_dict, topic)

    return json_success()

@api_key_only_webhook_view
@has_request_variables
def api_travis_webhook(request, user_profile, stream=REQ(default='travis'), topic=REQ(default=None)):
    message = ujson.loads(request.POST['payload'])

    author = message['author_name']
    message_type = message['status_message']
    changes = message['compare_url']

    good_status = ['Passed', 'Fixed']
    bad_status  = ['Failed', 'Broken', 'Still Failing']
    emoji = ''
    if message_type in good_status:
        emoji = ':thumbsup:'
    elif message_type in bad_status:
        emoji = ':thumbsdown:'
    else:
        emoji = "(No emoji specified for status '%s'.)" % (message_type,)

    build_url = message['build_url']

    template = (
        u'Author: %s\n'
        u'Build status: %s %s\n'
        u'Details: [changes](%s), [build log](%s)')

    body = template % (author, message_type, emoji, changes, build_url)

    check_send_message(user_profile, get_client('ZulipTravisWebhook'), 'stream', [stream], topic, body)
    return json_success()

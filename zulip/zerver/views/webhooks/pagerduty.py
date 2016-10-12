# Webhooks for external integrations.
from __future__ import absolute_import

from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse

import pprint
import ujson
import six
from typing import Dict, Any, Iterable, Optional


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
    # type: (Dict[str, Any]) -> Dict[str, Any]
    # Normalize the message dict, after this all keys will exist. I would
    # rather some strange looking messages than dropping pages.

    format_dict = {} # type: Dict[str, Any]
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


def send_raw_pagerduty_json(user_profile, client, stream, message, topic):
    # type: (UserProfile, Client, six.text_type, Dict[str, Any], six.text_type) -> None
    subject = topic or 'pagerduty'
    body = (
        u'Unknown pagerduty message\n'
        u'```\n'
        u'%s\n'
        u'```') % (ujson.dumps(message, indent=2),)
    check_send_message(user_profile, client, 'stream',
                       [stream], subject, body)


def send_formated_pagerduty(user_profile, client, stream, message_type, format_dict, topic):
    # type: (UserProfile, Client, six.text_type, six.text_type, Dict[str, Any], six.text_type) -> None
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

    check_send_message(user_profile, client, 'stream',
                       [stream], subject, body)


@api_key_only_webhook_view('PagerDuty')
@has_request_variables
def api_pagerduty_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                          stream=REQ(default='pagerduty'), topic=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Iterable[Dict[str, Any]]], six.text_type, Optional[six.text_type]) -> HttpResponse
    for message in payload['messages']:
        message_type = message['type']

        if message_type not in PAGER_DUTY_EVENT_NAMES:
            send_raw_pagerduty_json(user_profile, client, stream, message, topic)

        try:
            format_dict = build_pagerduty_formatdict(message)
        except:
            send_raw_pagerduty_json(user_profile, client, stream, message, topic)
        else:
            send_formated_pagerduty(user_profile, client, stream, message_type, format_dict, topic)

    return json_success()

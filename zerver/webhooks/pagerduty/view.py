# Webhooks for external integrations.

import pprint
from typing import Any, Dict, Iterable, Optional, Text

import ujson
from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import Client, UserProfile

PAGER_DUTY_EVENT_NAMES = {
    'incident.trigger': 'triggered',
    'incident.acknowledge': 'acknowledged',
    'incident.unacknowledge': 'unacknowledged',
    'incident.resolve': 'resolved',
    'incident.assign': 'assigned',
    'incident.escalate': 'escalated',
    'incident.delegate': 'delineated',
}

def build_pagerduty_formatdict(message: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize the message dict, after this all keys will exist. I would
    # rather some strange looking messages than dropping pages.

    format_dict = {}  # type: Dict[str, Any]
    format_dict['action'] = PAGER_DUTY_EVENT_NAMES[message['type']]

    format_dict['incident_id'] = message['data']['incident']['id']
    format_dict['incident_num'] = message['data']['incident']['incident_number']
    format_dict['incident_url'] = message['data']['incident']['html_url']

    format_dict['service_name'] = message['data']['incident']['service']['name']
    format_dict['service_url'] = message['data']['incident']['service']['html_url']

    # This key can be missing on null
    if message['data']['incident'].get('assigned_to_user', None):
        assigned_to_user = message['data']['incident']['assigned_to_user']
        format_dict['assigned_to_email'] = assigned_to_user['email']
        format_dict['assigned_to_username'] = assigned_to_user['email'].split('@')[0]
        format_dict['assigned_to_url'] = assigned_to_user['html_url']
    else:
        format_dict['assigned_to_email'] = 'nobody'
        format_dict['assigned_to_username'] = 'nobody'
        format_dict['assigned_to_url'] = ''

    # This key can be missing on null
    if message['data']['incident'].get('resolved_by_user', None):
        resolved_by_user = message['data']['incident']['resolved_by_user']
        format_dict['resolved_by_email'] = resolved_by_user['email']
        format_dict['resolved_by_username'] = resolved_by_user['email'].split('@')[0]
        format_dict['resolved_by_url'] = resolved_by_user['html_url']
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


def send_raw_pagerduty_json(request: HttpRequest,
                            user_profile: UserProfile,
                            message: Dict[str, Any]) -> None:
    subject = 'pagerduty'
    body = (
        u'Unknown pagerduty message\n'
        u'```\n'
        u'%s\n'
        u'```') % (ujson.dumps(message, indent=2),)
    check_send_webhook_message(request, user_profile, subject, body)


def send_formated_pagerduty(request: HttpRequest,
                            user_profile: UserProfile,
                            message_type: Text,
                            format_dict: Dict[str, Any]) -> None:
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

    subject = u'incident {incident_num}'.format(**format_dict)
    body = template.format(**format_dict)

    check_send_webhook_message(request, user_profile, subject, body)


@api_key_only_webhook_view('PagerDuty')
@has_request_variables
def api_pagerduty_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body'),
) -> HttpResponse:
    for message in payload['messages']:
        message_type = message['type']

        if message_type not in PAGER_DUTY_EVENT_NAMES:
            send_raw_pagerduty_json(request, user_profile, message)

        try:
            format_dict = build_pagerduty_formatdict(message)
        except Exception:
            send_raw_pagerduty_json(request, user_profile, message)
        else:
            send_formated_pagerduty(request, user_profile, message_type, format_dict)

    return json_success()

# Webhooks for external integrations.

from typing import Any, Dict, Iterable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    UnexpectedWebhookEventType
from zerver.models import UserProfile

PAGER_DUTY_EVENT_NAMES = {
    'incident.trigger': 'triggered',
    'incident.acknowledge': 'acknowledged',
    'incident.unacknowledge': 'unacknowledged',
    'incident.resolve': 'resolved',
    'incident.assign': 'assigned',
    'incident.escalate': 'escalated',
    'incident.delegate': 'delineated',
}

PAGER_DUTY_EVENT_NAMES_V2 = {
    'incident.trigger': 'triggered',
    'incident.acknowledge': 'acknowledged',
    'incident.resolve': 'resolved',
    'incident.assign': 'assigned',
}

ASSIGNEE_TEMPLATE = '[{username}]({url})'

INCIDENT_WITH_SERVICE_AND_ASSIGNEE = (
    'Incident [{incident_num}]({incident_url}) {action} by [{service_name}]'
    '({service_url}) (assigned to {assignee_info})\n\n``` quote\n{trigger_message}\n```'
)

INCIDENT_WITH_ASSIGNEE = """
Incident [{incident_num}]({incident_url}) {action} by {assignee_info}

``` quote
{trigger_message}
```
""".strip()

INCIDENT_ASSIGNED = """
Incident [{incident_num}]({incident_url}) {action} to {assignee_info}

``` quote
{trigger_message}
```
""".strip()

INCIDENT_RESOLVED_WITH_AGENT = """
Incident [{incident_num}]({incident_url}) resolved by {resolving_agent_info}

``` quote
{trigger_message}
```
""".strip()

INCIDENT_RESOLVED = """
Incident [{incident_num}]({incident_url}) resolved

``` quote
{trigger_message}
```
""".strip()

def build_pagerduty_formatdict(message: Dict[str, Any]) -> Dict[str, Any]:
    format_dict = {}  # type: Dict[str, Any]
    format_dict['action'] = PAGER_DUTY_EVENT_NAMES[message['type']]

    format_dict['incident_id'] = message['data']['incident']['id']
    format_dict['incident_num'] = message['data']['incident']['incident_number']
    format_dict['incident_url'] = message['data']['incident']['html_url']

    format_dict['service_name'] = message['data']['incident']['service']['name']
    format_dict['service_url'] = message['data']['incident']['service']['html_url']

    if message['data']['incident'].get('assigned_to_user', None):
        assigned_to_user = message['data']['incident']['assigned_to_user']
        format_dict['assignee_info'] = ASSIGNEE_TEMPLATE.format(
            username=assigned_to_user['email'].split('@')[0],
            url=assigned_to_user['html_url'],
        )
    else:
        format_dict['assignee_info'] = 'nobody'

    if message['data']['incident'].get('resolved_by_user', None):
        resolved_by_user = message['data']['incident']['resolved_by_user']
        format_dict['resolving_agent_info'] = ASSIGNEE_TEMPLATE.format(
            username=resolved_by_user['email'].split('@')[0],
            url=resolved_by_user['html_url'],
        )

    trigger_message = []
    trigger_summary_data = message['data']['incident']['trigger_summary_data']
    if trigger_summary_data is not None:
        trigger_subject = trigger_summary_data.get('subject', '')
        if trigger_subject:
            trigger_message.append(trigger_subject)

        trigger_description = trigger_summary_data.get('description', '')
        if trigger_description:
            trigger_message.append(trigger_description)

    format_dict['trigger_message'] = u'\n'.join(trigger_message)
    return format_dict

def build_pagerduty_formatdict_v2(message: Dict[str, Any]) -> Dict[str, Any]:
    format_dict = {}
    format_dict['action'] = PAGER_DUTY_EVENT_NAMES_V2[message['event']]

    format_dict['incident_id'] = message['incident']['id']
    format_dict['incident_num'] = message['incident']['incident_number']
    format_dict['incident_url'] = message['incident']['html_url']

    format_dict['service_name'] = message['incident']['service']['name']
    format_dict['service_url'] = message['incident']['service']['html_url']

    assignments = message['incident']['assignments']
    if assignments:
        assignee = assignments[0]['assignee']
        format_dict['assignee_info'] = ASSIGNEE_TEMPLATE.format(
            username=assignee['summary'], url=assignee['html_url'])
    else:
        format_dict['assignee_info'] = 'nobody'

    last_status_change_by = message['incident'].get('last_status_change_by')
    if last_status_change_by is not None:
        format_dict['resolving_agent_info'] = ASSIGNEE_TEMPLATE.format(
            username=last_status_change_by['summary'],
            url=last_status_change_by['html_url'],
        )

    trigger_description = message['incident'].get('description')
    if trigger_description is not None:
        format_dict['trigger_message'] = trigger_description
    return format_dict

def send_formated_pagerduty(request: HttpRequest,
                            user_profile: UserProfile,
                            message_type: str,
                            format_dict: Dict[str, Any]) -> None:
    if message_type in ('incident.trigger', 'incident.unacknowledge'):
        template = INCIDENT_WITH_SERVICE_AND_ASSIGNEE
    elif message_type == 'incident.resolve' and format_dict.get('resolving_agent_info') is not None:
        template = INCIDENT_RESOLVED_WITH_AGENT
    elif message_type == 'incident.resolve' and format_dict.get('resolving_agent_info') is None:
        template = INCIDENT_RESOLVED
    elif message_type == 'incident.assign':
        template = INCIDENT_ASSIGNED
    else:
        template = INCIDENT_WITH_ASSIGNEE

    subject = u'Incident {incident_num}'.format(**format_dict)
    body = template.format(**format_dict)
    check_send_webhook_message(request, user_profile, subject, body)

@api_key_only_webhook_view('PagerDuty')
@has_request_variables
def api_pagerduty_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body'),
) -> HttpResponse:
    for message in payload['messages']:
        message_type = message.get('type')

        # If the message has no "type" key, then this payload came from a
        # Pagerduty Webhook V2.
        if message_type is None:
            break

        if message_type not in PAGER_DUTY_EVENT_NAMES:
            raise UnexpectedWebhookEventType('Pagerduty', message_type)

        format_dict = build_pagerduty_formatdict(message)
        send_formated_pagerduty(request, user_profile, message_type, format_dict)

    for message in payload['messages']:
        event = message.get('event')

        # If the message has no "event" key, then this payload came from a
        # Pagerduty Webhook V1.
        if event is None:
            break

        if event not in PAGER_DUTY_EVENT_NAMES_V2:
            raise UnexpectedWebhookEventType('Pagerduty', event)

        format_dict = build_pagerduty_formatdict_v2(message)
        send_formated_pagerduty(request, user_profile, event, format_dict)

    return json_success()

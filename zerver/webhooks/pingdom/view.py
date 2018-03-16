# Webhooks pfor external integrations.
from typing import Any, Dict, Text

import ujson
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

PINGDOM_SUBJECT_TEMPLATE = '{name} status.'
PINGDOM_MESSAGE_TEMPLATE = ('Service {service_url} changed its {type} status'
                            ' from {previous_state} to {current_state}.')
PINGDOM_MESSAGE_DESCRIPTION_TEMPLATE = 'Description: {description}.'


SUPPORTED_CHECK_TYPES = (
    'HTTP',
    'HTTP_CUSTOM'
    'HTTPS',
    'SMTP',
    'POP3',
    'IMAP',
    'PING',
    'DNS',
    'UDP',
    'PORT_TCP',
)


@api_key_only_webhook_view('Pingdom')
@has_request_variables
def api_pingdom_webhook(request: HttpRequest, user_profile: UserProfile,
                        payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    check_type = get_check_type(payload)

    if check_type in SUPPORTED_CHECK_TYPES:
        subject = get_subject_for_http_request(payload)
        body = get_body_for_http_request(payload)
    else:
        return json_error(_('Unsupported check_type: {check_type}').format(check_type=check_type))

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()


def get_subject_for_http_request(payload: Dict[str, Any]) -> Text:
    return PINGDOM_SUBJECT_TEMPLATE.format(name=payload['check_name'])


def get_body_for_http_request(payload: Dict[str, Any]) -> Text:
    current_state = payload['current_state']
    previous_state = payload['previous_state']

    data = {
        'service_url': payload['check_params']['hostname'],
        'previous_state': previous_state,
        'current_state': current_state,
        'type': get_check_type(payload)
    }
    body = PINGDOM_MESSAGE_TEMPLATE.format(**data)
    if current_state == 'DOWN' and previous_state == 'UP':
        description = PINGDOM_MESSAGE_DESCRIPTION_TEMPLATE.format(description=payload['long_description'])
        body += '\n{description}'.format(description=description)
    return body


def get_check_type(payload: Dict[str, Any]) -> Text:
    return payload['check_type']

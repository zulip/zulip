from typing import Any, Dict

from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse

from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile

import ujson

ZABBIX_SUBJECT_TEMPLATE = '{hostname}'
ZABBIX_MESSAGE_TEMPLATE = '{status} ({severity}) alert on [{hostname}]({link}).\n{trigger}\n{item}'

@api_key_only_webhook_view('Zabbix')
@has_request_variables
def api_zabbix_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    return ZABBIX_SUBJECT_TEMPLATE.format(hostname=payload['hostname'])

def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    hostname = payload['hostname']
    severity = payload['severity']
    status = payload['status']
    item = payload['item']
    trigger = payload['trigger']
    link = payload['link']

    data = {
        "hostname": hostname,
        "severity": severity,
        "status": status,
        "item": item,
        "trigger": trigger,
        "link": link
    }
    return ZABBIX_MESSAGE_TEMPLATE.format(**data)

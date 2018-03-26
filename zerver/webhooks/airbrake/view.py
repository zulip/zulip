# Webhooks for external integrations.
from typing import Any, Dict, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.models import UserProfile

AIRBRAKE_SUBJECT_TEMPLATE = '{project_name}'
AIRBRAKE_MESSAGE_TEMPLATE = '[{error_class}]({error_url}): "{error_message}" occurred.'

@api_key_only_webhook_view('Airbrake')
@has_request_variables
def api_airbrake_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    subject = get_subject(payload)
    body = get_body(payload)
    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_subject(payload: Dict[str, Any]) -> str:
    return AIRBRAKE_SUBJECT_TEMPLATE.format(project_name=payload['error']['project']['name'])

def get_body(payload: Dict[str, Any]) -> str:
    data = {
        'error_url': payload['airbrake_error_url'],
        'error_class': payload['error']['error_class'],
        'error_message': payload['error']['error_message'],
    }
    return AIRBRAKE_MESSAGE_TEMPLATE.format(**data)

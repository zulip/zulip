# Webhooks for external integrations.

from typing import Any, Dict, Text

import ujson
from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

CIRCLECI_SUBJECT_TEMPLATE = u'{repository_name}'
CIRCLECI_MESSAGE_TEMPLATE = u'[Build]({build_url}) triggered by {username} on {branch} branch {status}.'

FAILED_STATUS = 'failed'

@api_key_only_webhook_view('CircleCI')
@has_request_variables
def api_circleci_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    payload = payload['payload']
    subject = get_subject(payload)
    body = get_body(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_subject(payload: Dict[str, Any]) -> Text:
    return CIRCLECI_SUBJECT_TEMPLATE.format(repository_name=payload['reponame'])

def get_body(payload: Dict[str, Any]) -> Text:
    data = {
        'build_url': payload['build_url'],
        'username': payload['username'],
        'branch': payload['branch'],
        'status': get_status(payload)
    }
    return CIRCLECI_MESSAGE_TEMPLATE.format(**data)

def get_status(payload: Dict[str, Any]) -> Text:
    status = payload['status']
    if payload['previous'] and payload['previous']['status'] == FAILED_STATUS and status == FAILED_STATUS:
        return u'is still failing'
    if status == 'success':
        return u'succeeded'
    return status

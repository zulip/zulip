# Webhooks for external integrations.
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Any

from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile, Client

import ujson


CIRCLECI_SUBJECT_TEMPLATE = '{repository_name}'
CIRCLECI_MESSAGE_TEMPLATE = '[Build]({build_url}) triggered by {username} on {branch} branch {status}.'

FAILED_STATUS = 'failed'

@api_key_only_webhook_view('CircleCI')
@has_request_variables
def api_circleci_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                         stream=REQ(default='circleci')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], text_type) -> HttpResponse
    payload = payload['payload']
    subject = get_subject(payload)
    body = get_body(payload)

    check_send_message(user_profile, client, 'stream', [stream], subject, body)
    return json_success()

def get_subject(payload):
    return CIRCLECI_SUBJECT_TEMPLATE.format(repository_name=payload['reponame'])

def get_body(payload):
    data = {
        'build_url': payload['build_url'],
        'username': payload['username'],
        'branch': payload['branch'],
        'status': get_status(payload)
    }
    return CIRCLECI_MESSAGE_TEMPLATE.format(**data)

def get_status(payload):
    status = payload['status']
    if payload['previous']['status'] == FAILED_STATUS and status == FAILED_STATUS:
        return 'is still failing'
    if status == 'success':
        return 'succeeded'
    return status

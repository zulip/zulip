# Webhooks for external integrations.
from __future__ import absolute_import

from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse
from typing import Any

from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile, Client

import ujson


CODESHIP_SUBJECT_TEMPLATE = '{project_name}'
CODESHIP_MESSAGE_TEMPLATE = '[Build]({build_url}) triggered by {committer} on {branch} branch {status}.'

CODESHIP_DEFAULT_STATUS = 'has {status} status'
CODESHIP_STATUS_MAPPER = {
    'testing': 'started',
    'error': 'failed',
    'success': 'succeeded',
}


@api_key_only_webhook_view('Codeship')
@has_request_variables
def api_codeship_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                         stream=REQ(default='codeship')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], str) -> HttpResponse
    try:
        payload = payload['build']
        subject = get_subject_for_http_request(payload)
        body = get_body_for_http_request(payload)
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    check_send_message(user_profile, client, 'stream', [stream], subject, body)
    return json_success()


def get_subject_for_http_request(payload):
    # type: (Dict[str, Any]) -> str
    return CODESHIP_SUBJECT_TEMPLATE.format(project_name=payload['project_name'])


def get_body_for_http_request(payload):
    # type: (Dict[str, Any]) -> str
    return CODESHIP_MESSAGE_TEMPLATE.format(
        build_url=payload['build_url'],
        committer=payload['committer'],
        branch=payload['branch'],
        status=get_status_message(payload)
    )


def get_status_message(payload):
    # type: (Dict[str, Any]) -> str
    build_status = payload['status']
    return CODESHIP_STATUS_MAPPER.get(build_status, CODESHIP_DEFAULT_STATUS.format(status=build_status))

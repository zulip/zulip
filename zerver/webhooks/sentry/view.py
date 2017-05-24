# Webhooks for external integrations.
from __future__ import absolute_import
from django.http import HttpRequest, HttpResponse
from zerver.models import UserProfile
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from typing import Any, Dict

@api_key_only_webhook_view('Sentry')
@has_request_variables
def api_sentry_webhook(request, user_profile,
                       payload=REQ(argument_type='body'),
                       stream=REQ(default='sentry')):
    # type: (HttpRequest, UserProfile, Dict[str, Any], str) -> HttpResponse
    subject = "{}".format(payload.get('project_name'))
    body = "New {} [issue]({}): {}.".format(payload['level'].upper(),
                                            payload.get('url'),
                                            payload.get('message'))
    check_send_message(user_profile, request.client, 'stream', [stream], subject, body)
    return json_success()

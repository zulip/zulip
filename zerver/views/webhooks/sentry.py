# Webhooks for external integrations.
from __future__ import absolute_import
from typing import Any

from django.http import HttpRequest, HttpResponse

from zerver.decorator import (REQ, api_key_only_webhook_view,
                              has_request_variables)
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.models import Client, UserProfile


@api_key_only_webhook_view('Sentry')
@has_request_variables
def api_sentry_webhook(request, user_profile, client,
                       payload=REQ(argument_type='body'),
                       stream=REQ(default='sentry')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], str) -> HttpResponse
    subject = "{}".format(payload.get('project_name'))
    body = "New {} [issue]({}): {}.".format(payload.get('level').upper(),
                                            payload.get('url'),
                                            payload.get('message'))
    check_send_message(user_profile, client, 'stream', [stream], subject, body)
    return json_success()

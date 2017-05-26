# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile
from django.http import HttpRequest, HttpResponse
from typing import Optional

import ujson

@api_key_only_webhook_view('Yo')
@has_request_variables
def api_yo_app_webhook(request, user_profile, email=REQ(default=""),
                       username=REQ(default='Yo Bot'), topic=REQ(default=None),
                       user_ip=REQ(default=None)):
    # type: (HttpRequest, UserProfile, str, str, Optional[str], Optional[str]) -> HttpResponse

    body = ('Yo from %s') % (username,)
    check_send_message(user_profile, request.client, 'private', [email], topic, body)
    return json_success()

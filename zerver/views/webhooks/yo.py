# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

import ujson

@api_key_only_webhook_view
@has_request_variables
def api_yo_app_webhook(request, user_profile, stream=REQ(default='yo App'), api_key=REQ(default=None), username=REQ(default='Yo Bot'), topic=REQ(default='Yo! Notification'), user_ip=REQ(default='None')):

    body = ('Yo from %s') % (username)

    check_send_message(user_profile, get_client('ZulipYoWebhook'), 'stream', [stream], topic, body)
    return json_success()

# Webhooks for external integrations.
from zerver.lib.actions import check_send_stream_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile
from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Text

CHECK_IS_REPLY = "in reply to"

@api_key_only_webhook_view('Flock')
@has_request_variables
def api_flock_webhook(request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[str, Any]=REQ(argument_type='body'),
                      stream: str=REQ(default='test'),
                      topic: str=REQ(default='Flock notifications')) -> HttpResponse:

    if len(payload["text"]) != 0:
        message_body = payload["text"]
    else:
        message_body = payload["notification"]
    body = u"{}".format(message_body)

    check_send_stream_message(user_profile, request.client, stream, topic, body)

    return json_success()

# Webhooks for external integrations.
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import REQ, has_request_variables, webhook_view
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

CHECK_IS_REPLY = "in reply to"

@webhook_view('Flock')
@has_request_variables
def api_flock_webhook(request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    if len(payload["text"]) != 0:
        message_body = payload["text"]
    else:
        message_body = payload["notification"]

    topic = 'Flock notifications'
    body = f"{message_body}"

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

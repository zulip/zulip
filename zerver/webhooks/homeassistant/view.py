from typing import Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

@api_key_only_webhook_view('HomeAssistant')
@has_request_variables
def api_homeassistant_webhook(request: HttpRequest, user_profile: UserProfile,
                              payload: Dict[str, str]=REQ(argument_type='body')) -> HttpResponse:

    # construct the body of the message
    body = payload["message"]

    # set the topic to the topic parameter, if given
    if "topic" in payload:
        topic = payload["topic"]
    else:
        topic = "homeassistant"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    # return json result
    return json_success()

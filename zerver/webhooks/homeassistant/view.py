from typing import Any, Dict, Iterable, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile

@api_key_only_webhook_view('HomeAssistant')
@has_request_variables
def api_homeassistant_webhook(request, user_profile,
                              payload=REQ(argument_type='body'),
                              stream=REQ(default="homeassistant")):
    # type: (HttpRequest, UserProfile, Dict[str, str], Text) -> HttpResponse

    # construct the body of the message
    body = payload["message"]

    # set the topic to the topic parameter, if given
    if "topic" in payload:
        topic = payload["topic"]
    else:
        topic = "homeassistant"

    # send the message
    check_send_stream_message(user_profile, request.client, stream, topic, body)

    # return json result
    return json_success()

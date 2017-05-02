from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

from zerver.models import UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

@api_key_only_webhook_view('HomeAssistant')
@has_request_variables
def api_homeassistant_webhook(request, user_profile,
                              payload=REQ(argument_type='body'),
                              stream=REQ(default="homeassistant")):
    # type: (HttpRequest, UserProfile, Dict[str, str], Text) -> HttpResponse

    # construct the body of the message
    try:
        body = payload["message"]
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    # set the topic to the topic parameter, if given
    if "topic" in payload:
        topic = payload["topic"]
    else:
        topic = "homeassistant"

    # send the message
    check_send_message(user_profile, request.client, 'stream', [stream], topic, body)

    # return json result
    return json_success()

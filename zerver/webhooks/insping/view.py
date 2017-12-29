from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_stream_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, \
    api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

import time


@api_key_only_webhook_view('Insping')
@has_request_variables
def api_insping_webhook(request: HttpRequest, user_profile: UserProfile,
                        payload: Dict[str, Iterable[Dict[str, Any]]] = REQ(
                            argument_type='body'),
                        stream: Text = REQ(default='test'),
                        topic: Text = REQ(default='insping')) -> HttpResponse:

    data = payload['webhook_event_data']
    state_name = data['check_state_name']
    url_tested = data['request_url']
    response_time = data['response_time']
    timestamp = data['request_start_time']

    time_formatted = time.strftime("%c", time.strptime(timestamp,
                                   "%Y-%m-%dT%H:%M:%S.%f+00:00"))

    body = """State changed: {}
URL: {}
Response time: {} ms
Timestamp: {}
""".format(state_name, url_tested, response_time, time_formatted)

    check_send_stream_message(user_profile, request.client,
                              stream, topic, body)

    return json_success()

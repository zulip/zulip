# Webhooks for external integrations.
from typing import Any, Dict, Iterable, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_dict, check_string
from zerver.models import MAX_SUBJECT_LENGTH, UserProfile

@api_key_only_webhook_view('Splunk')
@has_request_variables
def api_splunk_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body'),
                       stream: Text=REQ(default='splunk'),
                       topic: Optional[Text]=REQ(default=None, type=str)) -> HttpResponse:

    # use default values if expected data is not provided
    search_name = payload.get('search_name', 'Missing search_name')
    results_link = payload.get('results_link', 'Missing results_link')
    host = payload.get('result', {}).get('host', 'Missing host')
    source = payload.get('result', {}).get('source', 'Missing source')
    raw = payload.get('result', {}).get('_raw', 'Missing _raw')

    # if no topic provided, use search name but truncate if too long
    if topic is None:
        if len(search_name) >= MAX_SUBJECT_LENGTH:
            msg_topic = "{}...".format(search_name[:(MAX_SUBJECT_LENGTH - 3)])
        else:
            msg_topic = search_name
    else:
        msg_topic = topic

    # construct the message body
    body = "Splunk alert from saved search"
    body_template = ('\n[{search}]({link})\nhost: {host}'
                     '\nsource: {source}\n\nraw: {raw}')
    body += body_template.format(search = search_name, link = results_link,
                                 host = host, source = source, raw = raw)

    # send the message
    check_send_stream_message(user_profile, request.client, stream, msg_topic, body)

    return json_success()

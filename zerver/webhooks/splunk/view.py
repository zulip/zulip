# Webhooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile, MAX_SUBJECT_LENGTH

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

@api_key_only_webhook_view('Splunk')
@has_request_variables
def api_splunk_webhook(request, user_profile,
                       payload=REQ(argument_type='body'), stream=REQ(default='splunk'),
                       topic=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Dict[str, Any], Text, Optional[Text]) -> HttpResponse

    # use default values if expected data is not provided
    search_name = payload.get('search_name', 'Missing search_name')
    results_link = payload.get('results_link', 'Missing results_link')
    host = payload.get('result', {}).get('host', 'Missing host')
    source = payload.get('result', {}).get('source', 'Missing source')
    raw = payload.get('result', {}).get('_raw', 'Missing _raw')

    # if no topic provided, use search name but truncate if too long
    if topic is None:
        if len(search_name) >= MAX_SUBJECT_LENGTH:
            topic = "{}...".format(search_name[:(MAX_SUBJECT_LENGTH - 3)])
        else:
            topic = search_name

    # construct the message body
    body = "Splunk alert from saved search"
    body_template = ('\n[{search}]({link})\nhost: {host}'
                     '\nsource: {source}\n\nraw: {raw}')
    body += body_template.format(search = search_name, link = results_link,
                                 host = host, source = source, raw = raw)

    # send the message
    check_send_message(user_profile, request.client, 'stream', [stream], topic, body)

    return json_success()

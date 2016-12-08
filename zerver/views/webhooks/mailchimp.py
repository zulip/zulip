
#hooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import Client, UserProfile
from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Any
import ujson
import urlparse
MAILCHIMP_SUBJECT_TEMPLATE = '[{fired_at}]{type}|{data[merges][EMAIL]}'
MAILCHIMP_MESSAGE_TEMPLATE = '{data[merges][FNAME]} {data[merges][LNAME]} ({data[merges][EMAIL]}) subscribed at {fired_at}'

@api_key_only_webhook_view('MailChimp')
@has_request_variables
def api_mailchimp_webhook(request, user_profile, client, stream=REQ(default='mailchimp')):
    # type: (HttpRequest, UserProfile, Client, text_type) -> HttpResponse
    try:
        returned = request.body
        returned = urlparse.unquote(returned)
        payload = {}
        breakup = returned.split("&")
        for Break in breakup:
            para = Break.split("=")
            payload[para[0]] = para[1]
        subject = "["+payload['fired_at']+"]|"+payload['type']+"d|"+payload['data[merges][EMAIL]']
        body = payload['data[merges][FNAME]'] + " " + payload['data[merges][LNAME]'] + \
        " (" + payload['data[merges][EMAIL]'] + ") "+payload['type']+"d!"
        check_send_message(user_profile, client, 'stream', [stream], subject, body)
        return json_success()
    except:
        return json_success()
    return json_success()

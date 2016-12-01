# Webhooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import Client, UserProfile
from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Any

MAILCHIMP_SUBJECT_TEMPLATE = '[{fired_at}]{type}|{data[merges][EMAIL]}'
MAILCHIMP_MESSAGE_TEMPLATE = '{data[merges][FNAME]} {data[merges][LNAME]} ({data[merges][EMAIL]}) subscribed at {fired_at}'


@api_key_only_webhook_view('MailChimp')
@has_request_variables
def api_mailchimp_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                            stream=REQ(default='mailchimp')):
    print("mark 1")
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], text_type) -> HttpResponse
    try:
        print("mark 2")
        #print("load: "+payload['event'])
        #event = payload['event']
        #print(event)
        print("a")
        print("b")
        print(payload['data[merges][EMAIL]'])
        print("stop")
        #'[{fired_at}]{type}|{data[merges][EMAIL]}'
        subject = "["+payload['fired_at']+"]|"+payload['type']+"d|"+payload['data[merges][EMAIL]']
        print("===")
        print(subject)
        print("===")
        #'{data[merges][FNAME]} {data[merges][LNAME]} ({data[merges][EMAIL]}) subscribed at {fired_at}'
        body = payload['data[merges][FNAME]'] + " " + payload['data[merges][LNAME]'] + " (" + payload['data[merges][EMAIL]'] + ") "+payload['type']+"d!"
        print("===")
        print(body)
        print("===")
        print("mark 3")
    except KeyError as e:
        return json_error(_("Missing key {} in JSON".format(str(e))))
    check_send_message(user_profile, client, 'stream', [stream],
                       subject, body)
    print("!")
    print(json_success())
    return json_success()
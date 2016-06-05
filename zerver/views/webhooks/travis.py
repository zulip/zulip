# Webhooks for external integrations.
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse

from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile, Client

import ujson


@api_key_only_webhook_view('Travis')
@has_request_variables
def api_travis_webhook(request, user_profile, client,
                       stream=REQ(default='travis'),
                       topic=REQ(default=None),
                       message=REQ('payload', validator=check_dict([
                           ('author_name', check_string),
                           ('status_message', check_string),
                           ('compare_url', check_string),
                       ]))):
    # type: (HttpRequest, UserProfile, Client, str, str, Dict[str, str]) -> HttpResponse
    author = message['author_name']
    message_type = message['status_message']
    changes = message['compare_url']

    good_status = ['Passed', 'Fixed']
    bad_status  = ['Failed', 'Broken', 'Still Failing']
    emoji = ''
    if message_type in good_status:
        emoji = ':thumbsup:'
    elif message_type in bad_status:
        emoji = ':thumbsdown:'
    else:
        emoji = "(No emoji specified for status '%s'.)" % (message_type,)

    build_url = message['build_url']

    template = (
        u'Author: %s\n'
        u'Build status: %s %s\n'
        u'Details: [changes](%s), [build log](%s)')

    body = template % (author, message_type, emoji, changes, build_url)

    check_send_message(user_profile, client, 'stream', [stream], topic, body)
    return json_success()

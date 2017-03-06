# Webhooks for external integrations.
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse

from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict, check_string, check_bool
from zerver.models import UserProfile, Client
from typing import Dict

import ujson

GOOD_STATUSES = ['Passed', 'Fixed']
BAD_STATUSES = ['Failed', 'Broken', 'Still Failing']

MESSAGE_TEMPLATE = (
    u'Author: {}\n'
    u'Build status: {} {}\n'
    u'Details: [changes]({}), [build log]({})'
)

@api_key_only_webhook_view('Travis')
@has_request_variables
def api_travis_webhook(request, user_profile, client,
                       stream=REQ(default='travis'),
                       topic=REQ(default=None),
                       ignore_pull_requests=REQ(validator=check_bool, default=True),
                       message=REQ('payload', validator=check_dict([
                           ('author_name', check_string),
                           ('status_message', check_string),
                           ('compare_url', check_string),
                       ]))):
    # type: (HttpRequest, UserProfile, Client, str, str, str, Dict[str, str]) -> HttpResponse

    message_status = message['status_message']
    if ignore_pull_requests and message['type'] == 'pull_request':
        return json_success()

    if message_status in GOOD_STATUSES:
        emoji = ':thumbsup:'
    elif message_status in BAD_STATUSES:
        emoji = ':thumbsdown:'
    else:
        emoji = "(No emoji specified for status '{}'.)".format(message_status)

    body = MESSAGE_TEMPLATE.format(
        message['author_name'],
        message_status,
        emoji,
        message['compare_url'],
        message['build_url']
    )

    check_send_message(user_profile, client, 'stream', [stream], topic, body)
    return json_success()

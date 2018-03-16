# Webhooks for external integrations.

from typing import Dict

import ujson
from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.validator import check_bool, check_dict, check_string
from zerver.models import UserProfile

GOOD_STATUSES = ['Passed', 'Fixed']
BAD_STATUSES = ['Failed', 'Broken', 'Still Failing']

MESSAGE_TEMPLATE = (
    u'Author: {}\n'
    u'Build status: {} {}\n'
    u'Details: [changes]({}), [build log]({})'
)

@api_key_only_webhook_view('Travis')
@has_request_variables
def api_travis_webhook(request: HttpRequest, user_profile: UserProfile,
                       ignore_pull_requests: bool = REQ(validator=check_bool, default=True),
                       message: Dict[str, str]=REQ('payload', validator=check_dict([
                           ('author_name', check_string),
                           ('status_message', check_string),
                           ('compare_url', check_string),
                       ]))) -> HttpResponse:

    message_status = message['status_message']
    if ignore_pull_requests and message['type'] == 'pull_request':
        return json_success()

    if message_status in GOOD_STATUSES:
        emoji = ':thumbs_up:'
    elif message_status in BAD_STATUSES:
        emoji = ':thumbs_down:'
    else:
        emoji = "(No emoji specified for status '{}'.)".format(message_status)

    body = MESSAGE_TEMPLATE.format(
        message['author_name'],
        message_status,
        emoji,
        message['compare_url'],
        message['build_url']
    )
    topic = 'builds'

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

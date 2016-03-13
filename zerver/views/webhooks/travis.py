# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

import ujson


@api_key_only_webhook_view
@has_request_variables
def api_travis_webhook(request, user_profile, stream=REQ(default='travis'), topic=REQ(default=None)):
    message = ujson.loads(request.POST['payload'])

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

    check_send_message(user_profile, get_client('ZulipTravisWebhook'), 'stream', [stream], topic, body)
    return json_success()

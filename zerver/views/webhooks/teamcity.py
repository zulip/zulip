# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

import ujson


@api_key_only_webhook_view
@has_request_variables
def api_teamcity_webhook(request, user_profile, stream=REQ(default='teamcity')):

    payload = ujson.loads(request.body)
    message = payload['build']

    for property in message['teamcityProperties']:
        if property['name'] == 'env.BUILD_IS_PERSONAL' and property['value'] == 'true':
            # This is a personal build, don't announce it.
            return json_success()

    build_name = message['buildFullName']
    build_url = message['buildStatusUrl']
    changes_url = build_url + '&tab=buildChangesDiv'
    build_number = message['buildNumber']
    build_result = message['buildResult']
    build_result_delta = message['buildResultDelta']
    build_status = message['buildStatus']

    if build_result == 'success':
        if build_result_delta == 'fixed':
            status = 'has been fixed! :thumbsup:'
        else:
            status = 'was successful! :thumbsup:'
    elif build_result == 'failure':
        if build_result_delta == 'broken':
            status = 'is broken with status %s! :thumbsdown:' % (build_status)
        else:
            status = 'is still broken with status %s! :thumbsdown:' % (build_status)
    elif build_result == 'running':
        status = 'has started.'
    else:
        status = '(has no message specified for status %s)' % (build_status)

    template = (
        u'%s build %s %s\n'
        u'Details: [changes](%s), [build log](%s)')

    body = template % (build_name, build_number, status, changes_url, build_url)

    topic = build_name
    check_send_message(user_profile, get_client('ZulipTeamcityWebhook'), 'stream', [stream], topic, body)
    return json_success()

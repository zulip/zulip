# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

@api_key_only_webhook_view('HelloWorld')
@has_request_variables
def api_helloworld_webhook(request, user_profile, client,
        payload=REQ(argument_type='body'), stream=REQ(default='test'),
        topic=REQ(default='Hello World')):

    # construct the body of the message
    body = ('Hello! I am happy to be here! :smile: ')

    # add a wikipedia link if there is one in the payload
    if ('type' in payload and payload['type'] == 'wikipedia'):
        body += '\nThe Wikipedia featured article for today is **[%s](%s)**' % (payload['featured_title'], payload['featured_url'])

    # send the message
    check_send_message(user_profile, client, 'stream', [stream], topic, body)

    return json_success()

from datetime import datetime
from typing import Any, Dict, Text

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

@api_key_only_webhook_view('Honeybadger')
@has_request_variables
def api_honeybadger_webhook(request: HttpRequest, user_profile: UserProfile,
                            payload: Dict[str, Any] = REQ(argument_type='body'),
                            stream: Text = REQ(default='honeybadger')) -> HttpResponse:
    body = '**{}**'.format(payload['message'])

    if payload['event'] == 'check_in_missing':
        reported_at = datetime.strptime(payload['check_in']['reported_at'], "%Y-%m-%dT%H:%M:%S.%fZ") \
            .strftime('%H:%M:%S %Y-%m-%d')
        body += '\n**{}**: [Site]({})'.format(reported_at, payload['check_in']['url'])

        check_send_stream_message(user_profile, request.client, stream, payload['event'], body)

    elif payload['event'] == 'up':
        body += '\n**Site**: [{}]({})'.format(payload['site']['name'], payload['site']['url'])

        check_send_stream_message(user_profile, request.client, stream,
                                  '{}: {}'.format(payload['event'], payload['site']['name']), body)

    elif payload['event'] == 'occurred':
        body += '\n`{}`\n**Site**: [{}]({})'.format(payload['fault']['message'],
                                                    payload['project']['name'],
                                                    payload['fault']['url'])

        check_send_stream_message(user_profile, request.client, stream,
                                  '{}: {}'.format(payload['event'], payload['project']['name']), body)

    return json_success()

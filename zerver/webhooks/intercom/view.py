import datetime
from typing import Any, Dict, Text

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

@api_key_only_webhook_view('Intercom')
@has_request_variables
def api_intercom_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any] = REQ(argument_type='body')) -> HttpResponse:
    topic = payload['topic']
    topic = topic.replace('.', ' ')

    created_at = datetime.datetime.fromtimestamp(int(payload['created_at'])).strftime('%H:%M:%S %Y-%m-%d')
    body = '*{created_at}* **{topic}**: \n'.format(topic=topic, created_at=created_at)

    if payload['data']['item']['type'] == 'user_tag':
        data = payload['data']['item']['user']
        body += ' - User Name: {}\n' \
                ' - User Email: {}\n' \
                ' - User Phone: {}\n'.format(data['name'], data['email'], data['phone'])

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

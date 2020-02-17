from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

templates = {
    'Up': ('{monitorFriendlyName} ({monitorURL}) is back UP ({alertDetails}).' +
           ' It was down for {alertFriendlyDuration}.'),
    'Down': '{monitorFriendlyName} ({monitorURL}) is DOWN ({alertDetails}).'
}

@api_key_only_webhook_view('UptimeRobot')
@has_request_variables
def api_uptimerobot_webhook(request: HttpRequest, user_profile: UserProfile,
                            message: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    template = templates[message['alertTypeFriendlyName']]
    content = template.format(**message)
    topic = message['monitorFriendlyName']
    check_send_webhook_message(request, user_profile, topic, content)
    return json_success()

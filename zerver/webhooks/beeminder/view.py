# Webhooks for external integrations.
from typing import Text, Dict, Any
from django.http import HttpRequest, HttpResponse
from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile
import time

def get_time(payload: Dict[str, Any]) -> Any:
    losedate = payload["goal"]["losedate"]
    time_remaining = (losedate - time.time())/3600
    return time_remaining

@api_key_only_webhook_view("beeminder")
@has_request_variables
def api_beeminder_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    goal_name = payload["goal"]["slug"]
    limsum = payload["goal"]["limsum"]
    pledge = payload["goal"]["pledge"]
    time_remain = get_time(payload)  # time in hours
    # To show user's probable reaction by looking at pledge amount
    if pledge > 0:
        expression = ':worried:'
    else:
        expression = ':relieved:'

    topic = u'beekeeper'
    body = u"You are going to derail from goal **{}** in **{:0.1f} hours**\n \
You need **{}** to avoid derailing\n * Pledge: **{}$** {}"
    body = body.format(goal_name, time_remain, limsum, pledge, expression)
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

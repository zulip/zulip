# Webhooks for external integrations.
import time
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = ("You are going to derail from goal **{goal_name}** in **{time:0.1f} hours**. "
                    "You need **{limsum}** to avoid derailing.\n"
                    "* Pledge: **{pledge}$** {expression}\n")

def get_time(payload: Dict[str, Any]) -> Any:
    losedate = payload["goal"]["losedate"]
    time_remaining = (losedate - time.time())/3600
    return time_remaining

@webhook_view("Beeminder")
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

    topic = 'beekeeper'
    body = MESSAGE_TEMPLATE.format(
        goal_name=goal_name,
        time=time_remain,
        limsum=limsum,
        pledge=pledge,
        expression=expression,
    )
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

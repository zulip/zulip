# Webhooks for external integrations.
from typing import Text, Dict, Any
from django.http import HttpRequest, HttpResponse
from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message, check_send_private_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile, get_user_profile_by_email
import time
current_time = time.time()

def get_user_name(email: str) -> str:
    profile = get_user_profile_by_email(email)
    name = profile.short_name
    return name

def get_time(payload: Dict[str, Any]) -> Any:
    losedate = payload["goal"]["losedate"]
    time_remaining = (losedate - current_time)/3600
    return time_remaining

@api_key_only_webhook_view("beeminder")
@has_request_variables
def api_beeminder_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Any]=REQ(argument_type='body'),
                          stream: Text=REQ(default="beeminder"),
                          email: str=REQ(default='foo@gmail.com'),
                          topic: Text=REQ(default='beekeeper')) -> HttpResponse:

    secret = payload["goal"]["secret"]
    goal_name = payload["goal"]["slug"]
    limsum = payload["goal"]["limsum"]
    pledge = payload["goal"]["pledge"]
    time_remain = get_time(payload)  # time in hours
    # To show user's probable reaction by looking at pledge amount
    if pledge > 0:
        expression = ':worried:'
    else:
        expression = ':relieved:'

    if not secret:
        # In this case notifications will be sent to stream
        name = get_user_name(email)
        body = u"Hello **{}**! I am the Beeminder bot! :octopus:\n You are going to derail \
from goal **{}** in **{:0.1f} hours**\n You need **{}** to avoid derailing\n * Pledge: **{}$** {}"
        body = body.format(name, goal_name, time_remain, limsum, pledge, expression)
        check_send_stream_message(user_profile, request.client, stream, topic, body)
        return json_success()

    else:
        # In this case PM will be sent to user
        p = get_user_profile_by_email(email)
        body = u"I am the Beeminder bot! :octopus:\n You are going to derail from \
goal **{}** in **{:0.1f} hours**\n You need **{}** to avoid derailing\n * Pledge: **{}$**{}"
        body = body.format(goal_name, time_remain, limsum, pledge, expression)
        check_send_private_message(user_profile, request.client, p, body)
        return json_success()

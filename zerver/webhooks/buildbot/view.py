from typing import Dict, Any
from datetime import datetime

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.request import REQ, has_request_variables
from zerver.models import UserProfile
from zerver.lib.response import json_success

@api_key_only_webhook_view('Buildbot')
@has_request_variables
def api_buildbot_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    topic = payload["project"]
    if not topic:
        topic = "general"
    body = get_message(payload)
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

def get_message(payload: Dict[str, Any]) -> str:
    time_at = datetime.fromtimestamp(payload["timestamp"]).strftime("%Y-%h-%d %H:%M:%S")
    if "results" in payload:
        status = ("Success", "Warning", "Failure", "Exception", "Retry", "Cancelled")[payload[
            "results"]]
    if payload["event"] == "new":
        body = "Build #{id} of {name} started at {time}".format(
            id=payload["buildid"], name=payload["buildername"], time=time_at)
    elif payload["event"] == "finished":
        body = "Build #{id} of {name} finished at {time}! Result: {status}".format(id=payload[
            "buildid"], name=payload["buildername"], time=time_at, status=status)
    body += "\n{url}".format(url=payload["url"])
    return body

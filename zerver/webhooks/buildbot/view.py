from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view('Buildbot')
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
    if "results" in payload:
        # See http://docs.buildbot.net/latest/developer/results.html
        results = ("success", "warnings", "failure", "skipped",
                   "exception", "retry", "cancelled")
        status = results[payload["results"]]

    if payload["event"] == "new":
        body = "Build [#{id}]({url}) for **{name}** started.".format(
            id=payload["buildid"],
            name=payload["buildername"],
            url=payload["url"],
        )
    elif payload["event"] == "finished":
        body = "Build [#{id}]({url}) (result: {status}) for **{name}** finished.".format(
            id=payload["buildid"],
            name=payload["buildername"],
            url=payload["url"],
            status=status,
        )

    return body

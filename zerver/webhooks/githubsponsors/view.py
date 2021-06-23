from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("GithubSponsors")
@has_request_variables
def api_githubsponsors_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:

    topic = "Github Sponsors"
    if payload["action"] == "created":
        body = "Github Sponsors has a new sponsor : "
    elif payload["action"] == "pending_tier_change":
        body = "Github Sponsors : sponsorship downgraded by "

    user = payload["sponsorship"]["sponsor"]["login"]

    body += user

    print(body)
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

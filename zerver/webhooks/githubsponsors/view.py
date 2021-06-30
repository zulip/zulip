from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import log_exception_to_webhook_logger, webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, get_http_headers_from_filename
from zerver.models import UserProfile

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GITHUB_EVENT")


class Helper:
    def __init__(
        self,
        payload: Dict[str, Any],
        include_title: bool,
    ) -> None:
        self.payload = payload
        self.include_title = include_title

    def log_unsupported(self, event: str) -> None:
        summary = f"The '{event}' event isn't currently supported by the GitHub webhook"
        log_exception_to_webhook_logger(
            summary=summary,
            unsupported_event=True,
        )


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

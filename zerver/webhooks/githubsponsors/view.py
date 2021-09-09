from typing import Any, Dict, Sequence

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

def create_message_from_payload(payload: Dict[str, Sequence[Dict[str, Any]]]) -> str:
    message_body = "Hello from GitHub Sponsorships!\n**[{sponsorship[sponsor][login]}]({sponsorship[sponsor][html_url]})**"
    action = payload['action']
    if action == 'created':
        message_body += " has decided to sponsor you in the **{sponsorship[tier][name]}** tier!"
    elif action == 'pending_tier_change':
        message_body += " has changed their sponsorship tier from **{changes[tier][from][name]}** to **{sponsorship[tier][name]}**."
        message_body += "\nThese changes will be effective from {effective_date}."
    elif action == 'pending_cancellation':
        message_body += " has decided to stop sponsoring you."
        message_body += "\nThese changes will be effective from {effective_date}."

    return message_body.format(**payload)

@webhook_view("GitHubSponsors")
@has_request_variables
def api_githubsponsors_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Sequence[Dict[str, Any]]] = REQ(argument_type="body"),
) -> HttpResponse:

    # construct the body of the message
    body = create_message_from_payload(payload)

    topic = "GitHub Sponsors"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

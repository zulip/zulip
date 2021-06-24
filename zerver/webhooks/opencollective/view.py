from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MEMBER_NAME_TEMPLATE = "{name}"
AMOUNT_TEMPLATE = "{amount}"


@webhook_view("OpenCollective")
@has_request_variables
def api_opencollective_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:

    name = get_name(payload)
    amount = get_amount(payload)

    # construct the body of the message
    body = ""

    if name == "Incognito":  # Incognito donation
        body = f"An **Incognito** member donated **{amount}**! :tada:"
    else:  # non - Incognito donation
        body = f"@_**{name}** donated **{amount}**! :tada:"

    topic = "New Member"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()


def get_name(payload: Dict[str, Any]) -> str:
    return MEMBER_NAME_TEMPLATE.format(name=payload["data"]["member"]["memberCollective"]["name"])


def get_amount(payload: Dict[str, Any]) -> str:
    return AMOUNT_TEMPLATE.format(amount=payload["data"]["order"]["formattedAmount"])

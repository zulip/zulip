from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MEMBER_NAME_TEMPLATE = "{name}"
AMOUNT_TEMPLATE = "{amount}"


@webhook_view("OpenCollective")
@has_request_variables
def api_opencollective_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    name = get_name(payload)
    amount = get_amount(payload)

    # construct the body of the message
    body = ""

    if name == "Incognito":  # Incognito donation
        body = f"An **Incognito** member donated **{amount}**! :tada:"
    else:  # non-Incognito donation
        body = f"@_**{name}** donated **{amount}**! :tada:"

    topic = "New Member"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)


def get_name(payload: WildValue) -> str:
    return MEMBER_NAME_TEMPLATE.format(
        name=payload["data"]["member"]["memberCollective"]["name"].tame(check_string)
    )


def get_amount(payload: WildValue) -> str:
    return AMOUNT_TEMPLATE.format(
        amount=payload["data"]["order"]["formattedAmount"].tame(check_string)
    )

# Webhooks for external integrations.
from typing import Any, Dict, Sequence

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("HelloWorld")
@has_request_variables
def api_helloworld_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Sequence[Dict[str, Any]]] = REQ(argument_type="body"),
) -> HttpResponse:
    # construct the body of the message
    body = "Hello! I am happy to be here! :smile:"

    # try to add the Wikipedia article of the day
    body_template = (
        "\nThe Wikipedia featured article for today is **[{featured_title}]({featured_url})**"
    )
    body += body_template.format(**payload)

    topic = "Hello World"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)

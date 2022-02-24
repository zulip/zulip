from typing import Any, Dict, Sequence

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

RUNDECK_MESSAGE_TEMPLATE = "**{name}** - {status} - [E{id}]({link})"


@webhook_view("Rundeck")
@has_request_variables
def api_rundeck_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Sequence[Dict[str, Any]]] = REQ(argument_type="body"),
) -> HttpResponse:

    subject = "Rundeck"
    body = get_body(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success(request)


def get_body(payload: Dict[str, Any]) -> str:
    data = {
        "name": payload["execution"]["job"]["name"],
        "status": payload["execution"]["status"].upper(),
        "id": payload["execution"]["id"],
        "link": payload["execution"]["href"],
    }

    # clarify status messages
    if data["status"] == "RUNNING":
        data["status"] = "RUNNING LONG"

    if data["status"] == "SCHEDULED":
        data["status"] = "STARTED"

    return RUNDECK_MESSAGE_TEMPLATE.format(**data)

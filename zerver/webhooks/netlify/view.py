from typing import Any, Dict, Sequence, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    get_http_headers_from_filename,
    validate_extract_webhook_http_header,
)
from zerver.models import UserProfile

ALL_EVENT_TYPES = [
    "deploy_failed",
    "deploy_locked",
    "deploy_unlocked",
    "deploy_building",
    "deploy_created",
]

fixture_to_headers = get_http_headers_from_filename("HTTP_X_NETLIFY_EVENT")


@webhook_view("Netlify", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_netlify_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Sequence[Dict[str, Any]]] = REQ(argument_type="body"),
) -> HttpResponse:

    message_template, event = get_template(request, payload)

    body = message_template.format(
        build_name=payload["name"],
        build_url=payload["url"],
        branch_name=payload["branch"],
        state=payload["state"],
    )

    topic = "{topic}".format(topic=payload["branch"])

    check_send_webhook_message(request, user_profile, topic, body, event)

    return json_success(request)


def get_template(request: HttpRequest, payload: Dict[str, Any]) -> Tuple[str, str]:

    message_template = "The build [{build_name}]({build_url}) on branch {branch_name} "
    event = validate_extract_webhook_http_header(request, "X_NETLIFY_EVENT", "Netlify")

    if event == "deploy_failed":
        message_template += payload["error_message"]
    elif event == "deploy_locked":
        message_template += "is now locked."
    elif event == "deploy_unlocked":
        message_template += "is now unlocked."
    elif event in ALL_EVENT_TYPES:
        message_template += "is now {state}.".format(state=payload["state"])
    else:
        raise UnsupportedWebhookEventType(event)

    return message_template, event

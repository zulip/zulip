from typing import Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
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
@typed_endpoint
def api_netlify_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    message_template, event = get_template(request, payload)

    body = message_template.format(
        build_name=payload["name"].tame(check_string),
        build_url=payload["url"].tame(check_string),
        branch_name=payload["branch"].tame(check_string),
        state=payload["state"].tame(check_string),
    )

    topic = "{topic}".format(topic=payload["branch"].tame(check_string))

    check_send_webhook_message(request, user_profile, topic, body, event)

    return json_success(request)


def get_template(request: HttpRequest, payload: WildValue) -> Tuple[str, str]:
    message_template = "The build [{build_name}]({build_url}) on branch {branch_name} "
    event = validate_extract_webhook_http_header(request, "X-Netlify-Event", "Netlify")

    if event == "deploy_failed":
        message_template += payload["error_message"].tame(check_string)
    elif event == "deploy_locked":
        message_template += "is now locked."
    elif event == "deploy_unlocked":
        message_template += "is now unlocked."
    elif event in ALL_EVENT_TYPES:
        message_template += "is now {state}.".format(state=payload["state"].tame(check_string))
    else:
        raise UnsupportedWebhookEventTypeError(event)

    return message_template, event

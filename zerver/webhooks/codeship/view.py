# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

CODESHIP_TOPIC_TEMPLATE = "{project_name}"
CODESHIP_MESSAGE_TEMPLATE = (
    "[Build]({build_url}) triggered by {committer} on {branch} branch {status}."
)

CODESHIP_DEFAULT_STATUS = "has {status} status"
CODESHIP_STATUS_MAPPER = {
    "testing": "started",
    "error": "failed",
    "success": "succeeded",
}


@webhook_view("Codeship")
@typed_endpoint
def api_codeship_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    payload = payload["build"]
    topic = get_topic_for_http_request(payload)
    body = get_body_for_http_request(payload)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)


def get_topic_for_http_request(payload: WildValue) -> str:
    return CODESHIP_TOPIC_TEMPLATE.format(
        project_name=payload["project_name"].tame(check_string),
    )


def get_body_for_http_request(payload: WildValue) -> str:
    return CODESHIP_MESSAGE_TEMPLATE.format(
        build_url=payload["build_url"].tame(check_string),
        committer=payload["committer"].tame(check_string),
        branch=payload["branch"].tame(check_string),
        status=get_status_message(payload),
    )


def get_status_message(payload: WildValue) -> str:
    build_status = payload["status"].tame(check_string)
    return CODESHIP_STATUS_MAPPER.get(
        build_status, CODESHIP_DEFAULT_STATUS.format(status=build_status)
    )

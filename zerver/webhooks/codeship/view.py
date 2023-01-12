# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
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
@has_request_variables
def api_codeship_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    payload = payload["build"]
    subject = get_subject_for_http_request(payload)
    body = get_body_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success(request)


def get_subject_for_http_request(payload: WildValue) -> str:
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

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

CODEBASE_TOPIC_TEMPLATE = "{repository_name}"
CODEBASE_MESSAGE_TEMPLATE = "{user_name} pushed to {repository_name}"


@webhook_view("Codebase")
@typed_endpoint
def api_codebase_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    topic_name = get_topic_for_http_request(payload)
    body = get_body_for_http_request(payload)

    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)


def get_topic_for_http_request(payload: WildValue) -> str:
    return CODEBASE_TOPIC_TEMPLATE.format(
        repository_name=payload["repository"]["name"].tame(check_string),
    )


def get_body_for_http_request(payload: WildValue) -> str:
    return CODEBASE_MESSAGE_TEMPLATE.format(
        user_name=payload["user"]["name"].tame(check_string),
        repository_name=payload["repository"]["name"].tame(check_string),
    )

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_float,
    check_int,
    check_none_or,
    check_string,
    check_union,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

NOTIFICATION_DETAIL_TEMPLATE = "* **{key}**: {value}\n"


@webhook_view("Pabbly")
@typed_endpoint
def api_pabbly_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    topic = "Pabbly notification"
    body = "New event from your Pabbly workflow! :notifications:\n"

    for key, value in payload.items():
        body_detail = NOTIFICATION_DETAIL_TEMPLATE.format(
            key=key,
            value=str(
                value.tame(
                    check_none_or(check_union([check_int, check_string, check_float, check_bool]))
                )
            ),
        )
        body += body_detail

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)

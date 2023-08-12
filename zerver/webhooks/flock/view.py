# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Flock")
@typed_endpoint
def api_flock_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    text = payload["text"].tame(check_string)
    if len(text) != 0:
        message_body = text
    else:
        message_body = payload["notification"].tame(check_string)

    topic = "Flock notifications"
    body = f"{message_body}"

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

# Vercel delivers the event type in the request body's "type" field rather
# than in a header. See https://vercel.com/docs/webhooks/webhooks-api.
EVENT_TO_STATUS = {
    "deployment.created": "has started",
    "deployment.succeeded": "is ready :check:",
    "deployment.error": "failed :cross_mark:",
    "deployment.canceled": "was canceled",
    "deployment.promoted": "was promoted",
}
ALL_EVENT_TYPES = list(EVENT_TO_STATUS)

MESSAGE_TEMPLATE = "Deployment of [{name}]({url}) to **{target}** {status}."


@webhook_view("Vercel", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_vercel_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event = payload["type"].tame(check_string)
    if event not in EVENT_TO_STATUS:
        raise UnsupportedWebhookEventTypeError(event)

    data = payload["payload"]
    name = data["deployment"]["name"].tame(check_string)
    url = data["links"]["deployment"].tame(check_string)
    # A null target means a preview deployment.
    target = data["target"].tame(check_none_or(check_string)) or "preview"

    body = MESSAGE_TEMPLATE.format(name=name, url=url, target=target, status=EVENT_TO_STATUS[event])

    check_send_webhook_message(request, user_profile, name, body, event)
    return json_success(request)

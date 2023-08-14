# Webhooks for external integrations.
from typing import Optional

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

All_EVENT_TYPES = ["translated", "review"]


@webhook_view("Transifex", notify_bot_owner_on_invalid_json=False, all_event_types=All_EVENT_TYPES)
@typed_endpoint
def api_transifex_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    project: str,
    resource: str,
    language: str,
    translated: Optional[Json[int]] = None,
    reviewed: Optional[Json[int]] = None,
) -> HttpResponse:
    topic = f"{project} in {language}"
    if translated:
        event = "translated"
        body = f"Resource {resource} fully translated."
    elif reviewed:
        event = "review"
        body = f"Resource {resource} fully reviewed."
    else:
        raise UnsupportedWebhookEventTypeError("Unknown Event Type")
    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)

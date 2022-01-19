# Webhooks for external integrations.
from typing import Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_int
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

All_EVENT_TYPES = ["translated", "review"]


@webhook_view("Transifex", notify_bot_owner_on_invalid_json=False, all_event_types=All_EVENT_TYPES)
@has_request_variables
def api_transifex_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    project: str = REQ(),
    resource: str = REQ(),
    language: str = REQ(),
    translated: Optional[int] = REQ(json_validator=check_int, default=None),
    reviewed: Optional[int] = REQ(json_validator=check_int, default=None),
) -> HttpResponse:
    subject = f"{project} in {language}"
    if translated:
        event = "translated"
        body = f"Resource {resource} fully translated."
    elif reviewed:
        event = "review"
        body = f"Resource {resource} fully reviewed."
    else:
        raise UnsupportedWebhookEventType("Unknown Event Type")
    check_send_webhook_message(request, user_profile, subject, body, event)
    return json_success()

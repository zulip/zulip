from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

@webhook_view("Notion")
@typed_endpoint
def api_notion_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    # Default values
    topic = "Notion Notification"
    body = "Received event from Notion"

    # We support a simplified payload that users can construct in Notion Automations
    # { "event": "Page Created", "title": "My Page", "url": "https://..." }

    event_type = payload.get("event", "Update").tame(check_string)
    title = payload.get("title", "Untitled").tame(check_string)
    url = payload.get("url", "").tame(check_string)

    topic = event_type

    if url:
        body = f"**[{title}]({url})**"
    else:
        body = f"**{title}**"

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)

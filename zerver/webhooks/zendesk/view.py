# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def truncate(string: str, length: int) -> str:
    if len(string) > length:
        string = string[: length - 3] + "..."
    return string


@authenticated_rest_api_view(webhook_client_name="Zendesk")
@typed_endpoint
def api_zendesk_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    ticket_title: str,
    ticket_id: str,
    message: str,
) -> HttpResponse:
    """
    Zendesk uses triggers with message templates. This webhook uses the
    ticket_id and ticket_title to create a topic. And passes with zendesk
    user's configured message to zulip.
    """
    topic = truncate(f"#{ticket_id}: {ticket_title}", 60)
    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)

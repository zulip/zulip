# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
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
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    """
    Zendesk uses triggers with message templates. This webhook uses the
    ticket_id and ticket_title to create a topic. And passes with zendesk
    user's configured message to zulip.
    """
    body = ""
    ticket_id = None
    ticket_title = None
    if "ticket_title" and "ticket_id" in payload:
        ticket_title = payload["ticket_title"].tame(check_none_or(check_string))
        ticket_id = payload["ticket_id"].tame(check_none_or(check_string))
    if "message" in payload:
        body = payload["message"].tame(check_string)
    else:
        for key, value in payload.items():
            body += (
                f"* **{key}**: {value.tame(check_none_or(check_string))!s}\n" if value != "" else ""
            )
    if "topic" in payload:
        topic_name = truncate(payload["topic"].tame(check_string), 60)
    elif ticket_title and ticket_id:
        topic_name = truncate(f"#{ticket_id}: {ticket_title}", 60)
    else:
        topic_name = "zendesk"
    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)

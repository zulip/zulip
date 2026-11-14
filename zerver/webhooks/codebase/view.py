from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

TICKET_CREATION_TEMPLATE = (
    "A ticket of **[{ticket_type}]({url})** type and category "
    "**{category}** has been created by **{author}**."
)
TICKET_UPDATE_TEMPLATE = (
    "Ticket with ID **[{ticket_id}]({url})**, category "
    "**{category}** has been updated by **{author}**."
)


def handle_ticket_creation_event(event_payload: WildValue) -> tuple[str, str]:
    topic_name = event_payload["summary"].tame(check_string)
    ticket_type = event_payload["type"]["name"].tame(check_string)
    author = event_payload["assignee"]["name"].tame(check_string)
    category = event_payload["category"].tame(check_string)
    url = event_payload["url"].tame(check_string)

    body = TICKET_CREATION_TEMPLATE.format(
        ticket_type=ticket_type,
        url=url,
        category=category,
        author=author,
    )
    return topic_name, body


def handle_ticket_update_event(event_payload: WildValue) -> tuple[str, str]:
    ticket = event_payload["ticket"]
    topic_name = ticket["summary"].tame(check_string)
    ticket_id = ticket["id"].tame(check_int)
    category = ticket["category"].tame(check_string)
    author = event_payload["user"]["name"].tame(check_string)
    url = ticket["project"]["url"].tame(check_string)

    body = TICKET_UPDATE_TEMPLATE.format(
        ticket_id=ticket_id,
        url=url,
        category=category,
        author=author,
    )
    return topic_name, body


EVENT_FUNCTION_MAPPER = {
    "ticket_creation": handle_ticket_creation_event,
    "ticket_update": handle_ticket_update_event,
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("Codebase", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_codebase_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event_type = payload["type"].tame(check_string)
    event_func = EVENT_FUNCTION_MAPPER.get(event_type)
    if event_func is None:
        raise UnsupportedWebhookEventTypeError(event_type)

    raw_event_payload = payload["payload"].tame(check_string)
    event_payload = to_wild_value("event_payload", raw_event_payload)

    topic_name, body = event_func(event_payload)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

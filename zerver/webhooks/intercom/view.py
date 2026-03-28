from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import return_success_on_head_request, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

COMPANY_ACTION = "{name} was {phrase}."


def get_entity_topic_name(entity_type: str, entity_name: str | None = None) -> str:
    if entity_name is None:
        return entity_type
    return f"{entity_type}: {entity_name}"


def get_contact_display_name(contact: WildValue) -> str:
    name = contact["name"].tame(check_none_or(check_string))
    email = contact["email"].tame(check_none_or(check_string))
    contact_id = contact["id"].tame(check_string)
    return name or email or contact_id


def get_company_display_name(company: WildValue) -> str:
    name = company.get("name").tame(check_none_or(check_string))
    company_id = company.get("company_id").tame(check_none_or(check_string))
    internal_id = company["id"].tame(check_string)
    return name or company_id or internal_id


def get_ping_message(payload: WildValue) -> tuple[str, str]:
    body = get_setup_webhook_message("Intercom")
    topic_name = "Intercom"
    return (topic_name, body)


def get_company_action_message(phrase: str, payload: WildValue) -> tuple[str, str]:
    name = get_company_display_name(payload["data"]["item"])
    return get_entity_topic_name("Company", name), COMPANY_ACTION.format(name=name, phrase=phrase)


def get_company_contact_action_message(
    phrase: str, preposition: str, payload: WildValue
) -> tuple[str, str]:
    item = payload["data"]["item"]
    company_name = get_company_display_name(item["company"])
    contact_name = get_contact_display_name(item["contact"])
    return (
        get_entity_topic_name("Company", company_name),
        f"Contact **{contact_name}** was {phrase} {preposition} this company.",
    )


IGNORED_EVENTS = [
    # Require purchasing an Intercom number.
    *["call"],
    # Might be restricted for trial accounts.
    # Only content_stat.banners was attempted, and it was restricted.
    *["content_stat"],
    # Can only be invoked by SMS from registered US or Canadian numbers.
    *[
        "contact.lead.signed_up",
        "contact.unsubscribed_from_sms",
    ],
    # Unable to invoke these events, likely restricted for trial accounts.
    *[
        "conversation.rating.added",
        "ticket.rating.provided",
        "data_connector.execution.completed",
        "job.completed",
        "messenger.deployment_completed.event.created",
    ],
]


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue], tuple[str, str]]] = {
    "ping": get_ping_message,
    "company.created": partial(get_company_action_message, "created"),
    "company.updated": partial(get_company_action_message, "updated"),
    "company.deleted": partial(get_company_action_message, "deleted"),
    "company.contact.attached": partial(get_company_contact_action_message, "attached", "to"),
    "company.contact.detached": partial(get_company_contact_action_message, "detached", "from"),
}

ALL_EVENT_TYPES = list(EVENT_TO_FUNCTION_MAPPER.keys())


@webhook_view("Intercom", all_event_types=ALL_EVENT_TYPES)
# Intercom sends a HEAD request to validate the webhook URL. In this case, we just assume success.
@return_success_on_head_request
@typed_endpoint
def api_intercom_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event_type = payload["topic"].tame(check_string)
    # event_type is of the form "{event_category}.{event}".
    event_category = event_type.split(".", 1)[0]
    if event_type in IGNORED_EVENTS or event_category in IGNORED_EVENTS:
        return json_success(request)  # nocoverage

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name, body = handler(payload)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

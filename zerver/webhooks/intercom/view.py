from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import return_success_on_head_request, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

ADMIN_ROLE_UPDATED_TEMPLATE = "{name} is {phrase} an admin."

ADMIN_AWAY_MODE_UPDATED_TEMPLATE = "{name} is {away_status}{reason}."

ADMIN_LOGIN_LOGOUT_TEMPLATE = "{name} {phrase}."

COMPANY_ACTION_TEMPLATE = "{name} was {phrase}."

COMPANY_CONTACT_ACTION_TEMPLATE = (
    "**{contact_name}** was {phrase} {preposition} company **{company_name}**."
)


def get_admin_name(payload: WildValue) -> str:
    return payload["data"]["item"]["name"].tame(check_string)


def get_company_display_name(company: WildValue) -> str:
    name = company.get("name").tame(check_none_or(check_string))
    company_id = company.get("company_id").tame(check_none_or(check_string))
    # The company.deleted event only returns the Intercom internal ID,
    # without the name or company_id fields.
    intercom_id = company["id"].tame(check_string)
    return name or company_id or intercom_id


def get_topic_name(event_category: str, payload: WildValue) -> str:
    match event_category:
        case "ping":
            return "Intercom"
        case "admin":
            if payload["topic"].tame(check_string) == "admin.activity_log_event.created":
                return "Admin activity log"
            return f"Admin: {get_admin_name(payload)}"
        case "company":
            item = payload["data"]["item"]
            if payload["topic"].tame(check_string).startswith("company.contact."):
                # Attach/detach events are grouped under the contact's topic,
                # so that a contact moving between companies reads as one
                # story instead of being split across two company topics.
                contact = item["contact"]
                role = contact["role"].tame(check_string).capitalize()
                contact_name = contact["name"].tame(check_string)
                contact_id = contact["id"].tame(check_string)
                return f"{role}: {contact_name} ({contact_id})"
            return f"Company: {get_company_display_name(item)}"
        case _:  # nocoverage
            raise UnsupportedWebhookEventTypeError(payload["topic"].tame(check_string))


def get_ping_message(payload: WildValue) -> str:
    return get_setup_webhook_message("Intercom")


def get_admin_activity_log_event_created_message(payload: WildValue) -> str:
    return payload["data"]["item"]["activity_description"].tame(check_string)


def get_admin_role_updated_message(phrase: str, payload: WildValue) -> str:
    return ADMIN_ROLE_UPDATED_TEMPLATE.format(name=get_admin_name(payload), phrase=phrase)


def get_admin_login_logout_message(phrase: str, payload: WildValue) -> str:
    return ADMIN_LOGIN_LOGOUT_TEMPLATE.format(name=get_admin_name(payload), phrase=phrase)


def get_admin_away_mode_updated_message(payload: WildValue) -> str:
    admin_name = get_admin_name(payload)
    away_mode_enabled = payload["data"]["item"]["away_mode_enabled"].tame(check_bool)

    if away_mode_enabled:
        away_status = "away"
        reason_value = payload["data"]["item"]["away_status_reason"].tame(check_string)

        # Strip trailing period if exists,
        # since reason will be wrapped inside parentheses.
        reason_value = reason_value.removesuffix(".")
        reason = f" ({reason_value})" if reason_value else ""
    else:
        away_status = "now available"
        reason = ""

    return ADMIN_AWAY_MODE_UPDATED_TEMPLATE.format(
        name=admin_name, away_status=away_status, reason=reason
    )


def get_company_action_message(phrase: str, payload: WildValue) -> str:
    company_name = get_company_display_name(payload["data"]["item"])
    return COMPANY_ACTION_TEMPLATE.format(name=company_name, phrase=phrase)


def get_company_contact_action_message(phrase: str, payload: WildValue) -> str:
    item = payload["data"]["item"]
    contact_name = item["contact"]["name"].tame(check_string)
    company_name = get_company_display_name(item["company"])
    preposition = "from" if phrase == "detached" else "to"
    return COMPANY_CONTACT_ACTION_TEMPLATE.format(
        contact_name=contact_name,
        phrase=phrase,
        preposition=preposition,
        company_name=company_name,
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


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue], str]] = {
    "ping": get_ping_message,
    "admin.activity_log_event.created": get_admin_activity_log_event_created_message,
    "admin.away_mode_updated": get_admin_away_mode_updated_message,
    "admin.added_to_workspace": partial(get_admin_role_updated_message, "now"),
    "admin.removed_from_workspace": partial(get_admin_role_updated_message, "no longer"),
    "admin.logged_in": partial(get_admin_login_logout_message, "logged in"),
    "admin.logged_out": partial(get_admin_login_logout_message, "logged out"),
    "company.created": partial(get_company_action_message, "created"),
    "company.updated": partial(get_company_action_message, "updated"),
    "company.deleted": partial(get_company_action_message, "deleted"),
    "company.contact.attached": partial(get_company_contact_action_message, "attached"),
    "company.contact.detached": partial(get_company_contact_action_message, "detached"),
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
    body = handler(payload)
    topic_name = get_topic_name(event_category, payload)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

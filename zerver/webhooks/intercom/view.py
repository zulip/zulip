from html.parser import HTMLParser
from typing import Callable, Dict, List, Tuple

from django.http import HttpRequest, HttpResponse
from typing_extensions import override

from zerver.decorator import return_success_on_head_request, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

COMPANY_CREATED = """
New company **{name}** created:
* **User count**: {user_count}
* **Monthly spending**: {monthly_spend}
""".strip()

CONTACT_EMAIL_ADDED = "New email {email} added to contact."

CONTACT_CREATED = """
New contact created:
* **Name (or pseudonym)**: {name}
* **Email**: {email}
* **Location**: {location_info}
""".strip()

CONTACT_SIGNED_UP = """
Contact signed up:
* **Email**: {email}
* **Location**: {location_info}
""".strip()

CONTACT_TAG_CREATED = "Contact tagged with the `{name}` tag."

CONTACT_TAG_DELETED = "The tag `{name}` was removed from the contact."

CONVERSATION_ADMIN_ASSIGNED = "{name} assigned to conversation."

CONVERSATION_ADMIN_TEMPLATE = "{admin_name} {action} the conversation."

CONVERSATION_ADMIN_REPLY_TEMPLATE = """
{admin_name} {action} the conversation:

``` quote
{content}
```
""".strip()

CONVERSATION_ADMIN_INITIATED_CONVERSATION = """
{admin_name} initiated a conversation:

``` quote
{content}
```
""".strip()

EVENT_CREATED = "New event **{event_name}** created."

USER_CREATED = """
New user created:
* **Name**: {name}
* **Email**: {email}
""".strip()


class MLStripper(HTMLParser):
    def __init__(self) -> None:
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed: List[str] = []

    @override
    def handle_data(self, d: str) -> None:
        self.fed.append(d)

    def get_data(self) -> str:
        return "".join(self.fed)


def strip_tags(html: str) -> str:
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def get_topic_for_contacts(user: WildValue) -> str:
    topic_name = "{type}: {name}".format(
        type=user["type"].tame(check_string).capitalize(),
        name=user.get("name").tame(check_none_or(check_string))
        or user.get("pseudonym").tame(check_none_or(check_string))
        or user.get("email").tame(check_none_or(check_string)),
    )

    return topic_name


def get_company_created_message(payload: WildValue) -> Tuple[str, str]:
    body = COMPANY_CREATED.format(
        name=payload["data"]["item"]["name"].tame(check_string),
        user_count=payload["data"]["item"]["user_count"].tame(check_int),
        monthly_spend=payload["data"]["item"]["monthly_spend"].tame(check_int),
    )
    return ("Companies", body)


def get_contact_added_email_message(payload: WildValue) -> Tuple[str, str]:
    user = payload["data"]["item"]
    body = CONTACT_EMAIL_ADDED.format(email=user["email"].tame(check_string))
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_contact_created_message(payload: WildValue) -> Tuple[str, str]:
    contact = payload["data"]["item"]
    body = CONTACT_CREATED.format(
        name=contact.get("name").tame(check_none_or(check_string))
        or contact.get("pseudonym").tame(check_none_or(check_string)),
        email=contact["email"].tame(check_string),
        location_info="{city_name}, {region_name}, {country_name}".format(
            city_name=contact["location_data"]["city_name"].tame(check_string),
            region_name=contact["location_data"]["region_name"].tame(check_string),
            country_name=contact["location_data"]["country_name"].tame(check_string),
        ),
    )
    topic_name = get_topic_for_contacts(contact)
    return (topic_name, body)


def get_contact_signed_up_message(payload: WildValue) -> Tuple[str, str]:
    contact = payload["data"]["item"]
    body = CONTACT_SIGNED_UP.format(
        email=contact["email"].tame(check_string),
        location_info="{city_name}, {region_name}, {country_name}".format(
            city_name=contact["location_data"]["city_name"].tame(check_string),
            region_name=contact["location_data"]["region_name"].tame(check_string),
            country_name=contact["location_data"]["country_name"].tame(check_string),
        ),
    )
    topic_name = get_topic_for_contacts(contact)
    return (topic_name, body)


def get_contact_tag_created_message(payload: WildValue) -> Tuple[str, str]:
    body = CONTACT_TAG_CREATED.format(
        name=payload["data"]["item"]["tag"]["name"].tame(check_string)
    )
    contact = payload["data"]["item"]["contact"]
    topic_name = get_topic_for_contacts(contact)
    return (topic_name, body)


def get_contact_tag_deleted_message(payload: WildValue) -> Tuple[str, str]:
    body = CONTACT_TAG_DELETED.format(
        name=payload["data"]["item"]["tag"]["name"].tame(check_string)
    )
    contact = payload["data"]["item"]["contact"]
    topic_name = get_topic_for_contacts(contact)
    return (topic_name, body)


def get_conversation_admin_assigned_message(payload: WildValue) -> Tuple[str, str]:
    body = CONVERSATION_ADMIN_ASSIGNED.format(
        name=payload["data"]["item"]["assignee"]["name"].tame(check_string)
    )
    user = payload["data"]["item"]["user"]
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_conversation_admin_message(
    action: str,
    payload: WildValue,
) -> Tuple[str, str]:
    assignee = payload["data"]["item"]["assignee"]
    user = payload["data"]["item"]["user"]
    body = CONVERSATION_ADMIN_TEMPLATE.format(
        admin_name=assignee.get("name").tame(check_none_or(check_string)),
        action=action,
    )
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_conversation_admin_reply_message(
    action: str,
    payload: WildValue,
) -> Tuple[str, str]:
    assignee = payload["data"]["item"]["assignee"]
    user = payload["data"]["item"]["user"]
    note = payload["data"]["item"]["conversation_parts"]["conversation_parts"][0]
    content = strip_tags(note["body"].tame(check_string))
    body = CONVERSATION_ADMIN_REPLY_TEMPLATE.format(
        admin_name=assignee.get("name").tame(check_none_or(check_string)),
        action=action,
        content=content,
    )
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_conversation_admin_single_created_message(payload: WildValue) -> Tuple[str, str]:
    assignee = payload["data"]["item"]["assignee"]
    user = payload["data"]["item"]["user"]
    conversation_body = payload["data"]["item"]["conversation_message"]["body"].tame(check_string)
    content = strip_tags(conversation_body)
    body = CONVERSATION_ADMIN_INITIATED_CONVERSATION.format(
        admin_name=assignee.get("name").tame(check_none_or(check_string)),
        content=content,
    )
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_conversation_user_created_message(payload: WildValue) -> Tuple[str, str]:
    user = payload["data"]["item"]["user"]
    conversation_body = payload["data"]["item"]["conversation_message"]["body"].tame(check_string)
    content = strip_tags(conversation_body)
    body = CONVERSATION_ADMIN_INITIATED_CONVERSATION.format(
        admin_name=user.get("name").tame(check_none_or(check_string)),
        content=content,
    )
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_conversation_user_replied_message(payload: WildValue) -> Tuple[str, str]:
    user = payload["data"]["item"]["user"]
    note = payload["data"]["item"]["conversation_parts"]["conversation_parts"][0]
    content = strip_tags(note["body"].tame(check_string))
    body = CONVERSATION_ADMIN_REPLY_TEMPLATE.format(
        admin_name=user.get("name").tame(check_none_or(check_string)),
        action="replied to",
        content=content,
    )
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_event_created_message(payload: WildValue) -> Tuple[str, str]:
    event = payload["data"]["item"]
    body = EVENT_CREATED.format(event_name=event["event_name"].tame(check_string))
    return ("Events", body)


def get_user_created_message(payload: WildValue) -> Tuple[str, str]:
    user = payload["data"]["item"]
    body = USER_CREATED.format(
        name=user["name"].tame(check_string), email=user["email"].tame(check_string)
    )
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_user_deleted_message(payload: WildValue) -> Tuple[str, str]:
    user = payload["data"]["item"]
    topic_name = get_topic_for_contacts(user)
    return (topic_name, "User deleted.")


def get_user_email_updated_message(payload: WildValue) -> Tuple[str, str]:
    user = payload["data"]["item"]
    body = "User's email was updated to {}.".format(user["email"].tame(check_string))
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


def get_user_tagged_message(
    action: str,
    payload: WildValue,
) -> Tuple[str, str]:
    user = payload["data"]["item"]["user"]
    tag = payload["data"]["item"]["tag"]
    topic_name = get_topic_for_contacts(user)
    body = "The tag `{tag_name}` was {action} the user.".format(
        tag_name=tag["name"].tame(check_string),
        action=action,
    )
    return (topic_name, body)


def get_user_unsubscribed_message(payload: WildValue) -> Tuple[str, str]:
    user = payload["data"]["item"]
    body = "User unsubscribed from emails."
    topic_name = get_topic_for_contacts(user)
    return (topic_name, body)


EVENT_TO_FUNCTION_MAPPER: Dict[str, Callable[[WildValue], Tuple[str, str]]] = {
    "company.created": get_company_created_message,
    "contact.added_email": get_contact_added_email_message,
    "contact.created": get_contact_created_message,
    "contact.signed_up": get_contact_signed_up_message,
    "contact.tag.created": get_contact_tag_created_message,
    "contact.tag.deleted": get_contact_tag_deleted_message,
    "conversation.admin.assigned": get_conversation_admin_assigned_message,
    "conversation.admin.closed": partial(get_conversation_admin_message, "closed"),
    "conversation.admin.opened": partial(get_conversation_admin_message, "opened"),
    "conversation.admin.snoozed": partial(get_conversation_admin_message, "snoozed"),
    "conversation.admin.unsnoozed": partial(get_conversation_admin_message, "unsnoozed"),
    "conversation.admin.replied": partial(get_conversation_admin_reply_message, "replied to"),
    "conversation.admin.noted": partial(get_conversation_admin_reply_message, "added a note to"),
    "conversation.admin.single.created": get_conversation_admin_single_created_message,
    "conversation.user.created": get_conversation_user_created_message,
    "conversation.user.replied": get_conversation_user_replied_message,
    "event.created": get_event_created_message,
    "user.created": get_user_created_message,
    "user.deleted": get_user_deleted_message,
    "user.email.updated": get_user_email_updated_message,
    "user.tag.created": partial(get_user_tagged_message, "added to"),
    "user.tag.deleted": partial(get_user_tagged_message, "removed from"),
    "user.unsubscribed": get_user_unsubscribed_message,
    # Note that we do not have a payload for visitor.signed_up
    # but it should be identical to contact.signed_up
    "visitor.signed_up": get_contact_signed_up_message,
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
    if event_type == "ping":
        return json_success(request)

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name, body = handler(payload)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)

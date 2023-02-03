from typing import Callable, Tuple

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def get_message_data(payload: WildValue) -> Tuple[str, str, str, str]:
    link = "https://app.frontapp.com/open/" + payload["target"]["data"]["id"].tame(check_string)
    outbox = payload["conversation"]["recipient"]["handle"].tame(check_string)
    inbox = payload["source"]["data"][0]["address"].tame(check_string)
    subject = payload["conversation"]["subject"].tame(check_string)
    return link, outbox, inbox, subject


def get_source_name(payload: WildValue) -> str:
    first_name = payload["source"]["data"]["first_name"].tame(check_string)
    last_name = payload["source"]["data"]["last_name"].tame(check_string)
    return f"{first_name} {last_name}"


def get_target_name(payload: WildValue) -> str:
    first_name = payload["target"]["data"]["first_name"].tame(check_string)
    last_name = payload["target"]["data"]["last_name"].tame(check_string)
    return f"{first_name} {last_name}"


def get_inbound_message_body(payload: WildValue) -> str:
    link, outbox, inbox, subject = get_message_data(payload)
    return (
        "[Inbound message]({link}) from **{outbox}** to **{inbox}**:\n"
        "```quote\n*Subject*: {subject}\n```".format(
            link=link, outbox=outbox, inbox=inbox, subject=subject
        )
    )


def get_outbound_message_body(payload: WildValue) -> str:
    link, outbox, inbox, subject = get_message_data(payload)
    return (
        "[Outbound message]({link}) from **{inbox}** to **{outbox}**:\n"
        "```quote\n*Subject*: {subject}\n```".format(
            link=link, inbox=inbox, outbox=outbox, subject=subject
        )
    )


def get_outbound_reply_body(payload: WildValue) -> str:
    link, outbox, inbox, subject = get_message_data(payload)
    return "[Outbound reply]({link}) from **{inbox}** to **{outbox}**.".format(
        link=link, inbox=inbox, outbox=outbox
    )


def get_comment_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    comment = payload["target"]["data"]["body"].tame(check_string)
    return f"**{name}** left a comment:\n```quote\n{comment}\n```"


def get_conversation_assigned_body(payload: WildValue) -> str:
    source_name = get_source_name(payload)
    target_name = get_target_name(payload)

    if source_name == target_name:
        return f"**{source_name}** assigned themselves."

    return "**{source_name}** assigned **{target_name}**.".format(
        source_name=source_name, target_name=target_name
    )


def get_conversation_unassigned_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    return f"Unassigned by **{name}**."


def get_conversation_archived_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    return f"Archived by **{name}**."


def get_conversation_reopened_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    return f"Reopened by **{name}**."


def get_conversation_deleted_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    return f"Deleted by **{name}**."


def get_conversation_restored_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    return f"Restored by **{name}**."


def get_conversation_tagged_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    tag = payload["target"]["data"]["name"].tame(check_string)
    return f"**{name}** added tag **{tag}**."


def get_conversation_untagged_body(payload: WildValue) -> str:
    name = get_source_name(payload)
    tag = payload["target"]["data"]["name"].tame(check_string)
    return f"**{name}** removed tag **{tag}**."


EVENT_FUNCTION_MAPPER = {
    "inbound": get_inbound_message_body,
    "outbound": get_outbound_message_body,
    "out_reply": get_outbound_reply_body,
    "comment": get_comment_body,
    "mention": get_comment_body,
    "assign": get_conversation_assigned_body,
    "unassign": get_conversation_unassigned_body,
    "archive": get_conversation_archived_body,
    "reopen": get_conversation_reopened_body,
    "trash": get_conversation_deleted_body,
    "restore": get_conversation_restored_body,
    "tag": get_conversation_tagged_body,
    "untag": get_conversation_untagged_body,
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


def get_body_based_on_event(event: str) -> Callable[[WildValue], str]:
    return EVENT_FUNCTION_MAPPER[event]


@webhook_view("Front", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_front_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    event = payload["type"].tame(check_string)
    if event not in EVENT_FUNCTION_MAPPER:
        raise JsonableError(_("Unknown webhook request"))

    topic = payload["conversation"]["id"].tame(check_string)
    body = get_body_based_on_event(event)(payload)
    check_send_webhook_message(request, user_profile, topic, body, event)

    return json_success(request)

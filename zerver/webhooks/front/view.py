from typing import Any, Dict, Tuple

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

def get_message_data(payload: Dict[str, Any]) -> Tuple[str, str, str, str]:
    link = "https://app.frontapp.com/open/" + payload['target']['data']['id']
    outbox = payload['conversation']['recipient']['handle']
    inbox = payload['source']['data'][0]['address']
    subject = payload['conversation']['subject']
    return link, outbox, inbox, subject

def get_source_name(payload: Dict[str, Any]) -> str:
    first_name = payload['source']['data']['first_name']
    last_name = payload['source']['data']['last_name']
    return "%s %s" % (first_name, last_name)

def get_target_name(payload: Dict[str, Any]) -> str:
    first_name = payload['target']['data']['first_name']
    last_name = payload['target']['data']['last_name']
    return "%s %s" % (first_name, last_name)

def get_inbound_message_body(payload: Dict[str, Any]) -> str:
    link, outbox, inbox, subject = get_message_data(payload)
    return "[Inbound message]({link}) from **{outbox}** to **{inbox}**.\n" \
           "```quote\n*Subject*: {subject}\n```" \
        .format(link=link, outbox=outbox, inbox=inbox, subject=subject)

def get_outbound_message_body(payload: Dict[str, Any]) -> str:
    link, outbox, inbox, subject = get_message_data(payload)
    return "[Outbound message]({link}) from **{inbox}** to **{outbox}**.\n" \
           "```quote\n*Subject*: {subject}\n```" \
        .format(link=link, inbox=inbox, outbox=outbox, subject=subject)

def get_outbound_reply_body(payload: Dict[str, Any]) -> str:
    link, outbox, inbox, subject = get_message_data(payload)
    return "[Outbound reply]({link}) from **{inbox}** to **{outbox}**." \
        .format(link=link, inbox=inbox, outbox=outbox)

def get_comment_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    comment = payload['target']['data']['body']
    return "**{name}** left a comment:\n```quote\n{comment}\n```" \
        .format(name=name, comment=comment)

def get_conversation_assigned_body(payload: Dict[str, Any]) -> str:
    source_name = get_source_name(payload)
    target_name = get_target_name(payload)

    if source_name == target_name:
        return "**{source_name}** assigned themselves." \
            .format(source_name=source_name)

    return "**{source_name}** assigned **{target_name}**." \
        .format(source_name=source_name, target_name=target_name)

def get_conversation_unassigned_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    return "Unassined by **{name}**.".format(name=name)

def get_conversation_archived_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    return "Archived by **{name}**.".format(name=name)

def get_conversation_reopened_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    return "Reopened by **{name}**.".format(name=name)

def get_conversation_deleted_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    return "Deleted by **{name}**.".format(name=name)

def get_conversation_restored_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    return "Restored by **{name}**.".format(name=name)

def get_conversation_tagged_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    tag = payload['target']['data']['name']
    return "**{name}** added tag **{tag}**.".format(name=name, tag=tag)

def get_conversation_untagged_body(payload: Dict[str, Any]) -> str:
    name = get_source_name(payload)
    tag = payload['target']['data']['name']
    return "**{name}** removed tag **{tag}**.".format(name=name, tag=tag)

EVENT_FUNCTION_MAPPER = {
    'inbound': get_inbound_message_body,
    'outbound': get_outbound_message_body,
    'out_reply': get_outbound_reply_body,
    'comment': get_comment_body,
    'mention': get_comment_body,
    'assign': get_conversation_assigned_body,
    'unassign': get_conversation_unassigned_body,
    'archive': get_conversation_archived_body,
    'reopen': get_conversation_reopened_body,
    'trash': get_conversation_deleted_body,
    'restore': get_conversation_restored_body,
    'tag': get_conversation_tagged_body,
    'untag': get_conversation_untagged_body
}

def get_body_based_on_event(event: str) -> Any:
    return EVENT_FUNCTION_MAPPER[event]

@api_key_only_webhook_view('Front')
@has_request_variables
def api_front_webhook(request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    event = payload['type']
    if event not in EVENT_FUNCTION_MAPPER:
        return json_error(_("Unknown webhook request"))

    topic = payload['conversation']['id']
    body = get_body_based_on_event(event)(payload)
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

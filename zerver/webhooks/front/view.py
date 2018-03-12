from typing import Any, Dict, Optional, Text, Tuple

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

def get_message_data(payload: Dict[Text, Any]) -> Tuple[Text, Text, Text, Text]:
    link = "https://app.frontapp.com/open/" + payload['target']['data']['id']
    outbox = payload['conversation']['recipient']['handle']
    inbox = payload['source']['data'][0]['address']
    subject = payload['conversation']['subject']
    return link, outbox, inbox, subject

def get_source_name(payload: Dict[Text, Any]) -> Text:
    first_name = payload['source']['data']['first_name']
    last_name = payload['source']['data']['last_name']
    return "%s %s" % (first_name, last_name)

def get_target_name(payload: Dict[Text, Any]) -> Text:
    first_name = payload['target']['data']['first_name']
    last_name = payload['target']['data']['last_name']
    return "%s %s" % (first_name, last_name)

@api_key_only_webhook_view('Front')
@has_request_variables
def api_front_webhook(request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[Text, Any]=REQ(argument_type='body')) -> HttpResponse:

    event_type = payload['type']
    conversation_id = payload['conversation']['id']

    # Each topic corresponds to a separate conversation in Front.
    topic = conversation_id

    # Inbound message
    if event_type == 'inbound':
        link, outbox, inbox, subject = get_message_data(payload)
        body = "[Inbound message]({link}) from **{outbox}** to **{inbox}**.\n" \
               "```quote\n*Subject*: {subject}\n```" \
            .format(link=link, outbox=outbox, inbox=inbox, subject=subject)

    # Outbound message
    elif event_type == 'outbound':
        link, outbox, inbox, subject = get_message_data(payload)
        body = "[Outbound message]({link}) from **{inbox}** to **{outbox}**.\n" \
               "```quote\n*Subject*: {subject}\n```" \
            .format(link=link, inbox=inbox, outbox=outbox, subject=subject)

    # Outbound reply
    elif event_type == 'out_reply':
        link, outbox, inbox, subject = get_message_data(payload)
        body = "[Outbound reply]({link}) from **{inbox}** to **{outbox}**." \
            .format(link=link, inbox=inbox, outbox=outbox)

    # Comment or mention
    elif event_type == 'comment' or event_type == 'mention':
        name = get_source_name(payload)
        comment = payload['target']['data']['body']
        body = "**{name}** left a comment:\n```quote\n{comment}\n```" \
            .format(name=name, comment=comment)

    # Conversation assigned
    elif event_type == 'assign':
        source_name = get_source_name(payload)
        target_name = get_target_name(payload)

        if source_name == target_name:
            body = "**{source_name}** assigned themselves." \
                .format(source_name=source_name)
        else:
            body = "**{source_name}** assigned **{target_name}**." \
                .format(source_name=source_name, target_name=target_name)

    # Conversation unassigned
    elif event_type == 'unassign':
        name = get_source_name(payload)
        body = "Unassined by **{name}**.".format(name=name)

    # Conversation archived
    elif event_type == 'archive':
        name = get_source_name(payload)
        body = "Archived by **{name}**.".format(name=name)

    # Conversation reopened
    elif event_type == 'reopen':
        name = get_source_name(payload)
        body = "Reopened by **{name}**.".format(name=name)

    # Conversation deleted
    elif event_type == 'trash':
        name = get_source_name(payload)
        body = "Deleted by **{name}**.".format(name=name)

    # Conversation restored
    elif event_type == 'restore':
        name = get_source_name(payload)
        body = "Restored by **{name}**.".format(name=name)

    # Conversation tagged
    elif event_type == 'tag':
        name = get_source_name(payload)
        tag = payload['target']['data']['name']
        body = "**{name}** added tag **{tag}**.".format(name=name, tag=tag)

    # Conversation untagged
    elif event_type == 'untag':
        name = get_source_name(payload)
        tag = payload['target']['data']['name']
        body = "**{name}** removed tag **{tag}**.".format(name=name, tag=tag)
    else:
        return json_error(_("Unknown webhook request"))

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

from typing import Any, Dict, Optional, Text, Tuple

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.models import UserProfile

def get_message_data(payload: Dict[Text, Any]) -> Optional[Tuple[Text, Text, Text, Text]]:
    try:
        link = "https://app.frontapp.com/open/" + payload['target']['data']['id']
        outbox = payload['conversation']['recipient']['handle']
        inbox = payload['source']['data'][0]['address']
        subject = payload['conversation']['subject']
    except KeyError:
        return None

    return link, outbox, inbox, subject

def get_source_name(payload: Dict[Text, Any]) -> Optional[Text]:
    try:
        first_name = payload['source']['data']['first_name']
        last_name = payload['source']['data']['last_name']
    except KeyError:
        return None

    return "%s %s" % (first_name, last_name)

def get_target_name(payload: Dict[Text, Any]) -> Optional[Text]:
    try:
        first_name = payload['target']['data']['first_name']
        last_name = payload['target']['data']['last_name']
    except KeyError:
        return None

    return "%s %s" % (first_name, last_name)

def get_comment(payload: Dict[Text, Any]) -> Optional[Text]:
    try:
        comment = payload['target']['data']['body']
    except KeyError:
        return None

    return comment

def get_tag(payload: Dict[Text, Any]) -> Optional[Text]:
    try:
        tag = payload['target']['data']['name']
    except KeyError:
        return None

    return tag

@api_key_only_webhook_view('Front')
@has_request_variables
def api_front_webhook(request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[Text, Any]=REQ(argument_type='body'),
                      stream: Text=REQ(default='front'),
                      topic: Optional[Text]=REQ(default='cnv_id')) -> HttpResponse:
    try:
        event_type = payload['type']
        conversation_id = payload['conversation']['id']
    except KeyError:
        return json_error(_("Missing required data"))

    # Each topic corresponds to a separate conversation in Front.
    topic = conversation_id

    # Inbound message
    if event_type == 'inbound':
        message_data = get_message_data(payload)
        if not message_data:
            return json_error(_("Missing required data"))

        link, outbox, inbox, subject = message_data
        body = "[Inbound message]({link}) from **{outbox}** to **{inbox}**.\n" \
               "```quote\n*Subject*: {subject}\n```" \
            .format(link=link, outbox=outbox, inbox=inbox, subject=subject)

    # Outbound message
    elif event_type == 'outbound':
        message_data = get_message_data(payload)
        if not message_data:
            return json_error(_("Missing required data"))

        link, outbox, inbox, subject = message_data
        body = "[Outbound message]({link}) from **{inbox}** to **{outbox}**.\n" \
               "```quote\n*Subject*: {subject}\n```" \
            .format(link=link, inbox=inbox, outbox=outbox, subject=subject)

    # Outbound reply
    elif event_type == 'out_reply':
        message_data = get_message_data(payload)
        if not message_data:
            return json_error(_("Missing required data"))

        link, outbox, inbox, subject = message_data
        body = "[Outbound reply]({link}) from **{inbox}** to **{outbox}**." \
            .format(link=link, inbox=inbox, outbox=outbox)

    # Comment or mention
    elif event_type == 'comment' or event_type == 'mention':
        name, comment = get_source_name(payload), get_comment(payload)
        if not (name and comment):
            return json_error(_("Missing required data"))

        body = "**{name}** left a comment:\n```quote\n{comment}\n```" \
            .format(name=name, comment=comment)

    # Conversation assigned
    elif event_type == 'assign':
        source_name = get_source_name(payload)
        target_name = get_target_name(payload)

        if not (source_name and target_name):
            return json_error(_("Missing required data"))

        if source_name == target_name:
            body = "**{source_name}** assigned themselves." \
                .format(source_name=source_name)
        else:
            body = "**{source_name}** assigned **{target_name}**." \
                .format(source_name=source_name, target_name=target_name)

    # Conversation unassigned
    elif event_type == 'unassign':
        name = get_source_name(payload)
        if not name:
            return json_error(_("Missing required data"))

        body = "Unassined by **{name}**.".format(name=name)

    # Conversation archived
    elif event_type == 'archive':
        name = get_source_name(payload)
        if not name:
            return json_error(_("Missing required data"))

        body = "Archived by **{name}**.".format(name=name)

    # Conversation reopened
    elif event_type == 'reopen':
        name = get_source_name(payload)
        if not name:
            return json_error(_("Missing required data"))

        body = "Reopened by **{name}**.".format(name=name)

    # Conversation deleted
    elif event_type == 'trash':
        name = get_source_name(payload)
        if not name:
            return json_error(_("Missing required data"))

        body = "Deleted by **{name}**.".format(name=name)

    # Conversation restored
    elif event_type == 'restore':
        name = get_source_name(payload)
        if not name:
            return json_error(_("Missing required data"))

        body = "Restored by **{name}**.".format(name=name)

    # Conversation tagged
    elif event_type == 'tag':
        name, tag = get_source_name(payload), get_tag(payload)
        if not (name and tag):
            return json_error(_("Missing required data"))

        body = "**{name}** added tag **{tag}**.".format(name=name, tag=tag)

    # Conversation untagged
    elif event_type == 'untag':
        name, tag = get_source_name(payload), get_tag(payload)
        if not (name and tag):
            return json_error(_("Missing required data"))

        body = "**{name}** removed tag **{tag}**.".format(name=name, tag=tag)
    else:
        return json_error(_("Unknown webhook request"))

    check_send_stream_message(user_profile, request.client, stream, topic, body)

    return json_success()

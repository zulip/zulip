# Webhooks for external integrations.

from zerver.lib.actions import check_send_stream_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import get_client, UserProfile
from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Text


@api_key_only_webhook_view('Front')
@has_request_variables
def api_front_webhook(request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[str, Any]=REQ(argument_type='body'),
                      stream: str=REQ(default='test'),
                      topic: str=REQ(default='cnv_id')) -> HttpResponse:

    catogery = payload["type"]
    message_id = payload["conversation"]["id"]
    state = payload["conversation"]["status"]
    conversation_link = "https://app.frontapp.com/open/{}".format(message_id)

    topic = message_id

    # archive
    if catogery == "archive":
        Username = payload["source"]["data"]["username"]
        body = u"A [conversation]({}) is {} by {}"
        body = body.format(conversation_link, state, Username)

    # assign
    if catogery == "assign":
        tn = payload["target"]["data"]["username"]
        Username = payload["source"]["data"]["username"]
        body = u"A [conversation]({}) is {} to {} by {}"
        body = body.format(conversation_link, state, tn, Username)

    # unassign
    if catogery == "unassign":
        Username = payload["source"]["data"]["username"]
        body = u"A [conversation]({}) is {} by {}"
        body = body.format(conversation_link, state, Username)

    # tag
    if catogery == "tag":
        tt = payload["target"]["data"]["name"]
        Username = payload["source"]["data"]["username"]
        body = u"Tag {} was added by {} to a [conversation]({})"
        body = body.format(tt, Username, conversation_link)

    # untag
    if catogery == "untag":
        tt = payload["target"]["data"]["name"]
        Username = payload["source"]["data"]["username"]
        body = u"Tag {} was removed by {} from a [conversation]({})"
        body = body.format(tt, Username, conversation_link)

    # comment
    if catogery == "comment":
        Username = payload["source"]["data"]["username"]
        tm = payload["target"]["data"]["body"]
        body = u"{} added a comment to a [conversation]({}) :\n> {}"
        body = body.format(Username, conversation_link, tm)

    # outbound reply
    if catogery == "out_reply":
        fn = payload["conversation"]["last_message"]["author"]["username"]
        reply_message = payload["conversation"]["last_message"]["blurb"]
        body = u"{} replied to a [conversation]({}) :\n> {}"
        body = body.format(fn, conversation_link, reply_message)

    # reopen
    if catogery == "reopen":
        Username = payload["source"]["data"]["username"]
        body = u"{} reopened a [conversation]({})"
        body = body.format(Username, conversation_link)

    # mention
    if catogery == "mention":
        Username = payload["source"]["data"]["username"]
        tp = payload["target"]["_meta"]["type"]
        tn = payload["target"]["data"]["author"]["username"]
        tm = payload["target"]["data"]["body"]
        body = u"{} mentioned {} in a {} :\n> {}"
        body = body.format(Username, tn, tp, tm)

    # inbound message
    if catogery == "inbound":
        link = "https://app.frontapp.com/open/" + payload['target']['data']['id']
        outbox = payload['conversation']['recipient']['handle']
        inbox = payload['source']['data'][0]['address']
        subject = payload['conversation']['subject']
        body = u"{} got an [inbound message]({}) from {}.\
\n> * Subject: {}".format(inbox, link, outbox, subject)

    # outbound message
    if catogery == "outbound":
        link = "https://app.frontapp.com/open/" + payload['target']['data']['id']
        outbox = payload['conversation']['recipient']['handle']
        inbox = payload['source']['data'][0]['address']
        subject = payload['conversation']['subject']
        body = u"{} sent an [outbound message]({}) to {}.\
\n> * Subject: {}".format(outbox, link, inbox, subject)

    # delete conversation
    if catogery == "trash":
        first_name = payload['source']['data']['first_name']
        last_name = payload['source']['data']['last_name']
        body = u"A conversation is deleted by {} {}".format(first_name, last_name)

    # restore conversation
    if catogery == "restore":
        first_name = payload['source']['data']['first_name']
        last_name = payload['source']['data']['last_name']
        body = u"A conversation is restored by {} {}".format(first_name, last_name)

    check_send_stream_message(user_profile,
                              request.client,
                              stream,
                              topic,
                              body)
    return json_success()

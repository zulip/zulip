# Webhooks for external integrations.
from __future__ import absolute_import
from typing import Any, Dict, Text

import re

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import (REQ, api_key_only_webhook_view,
                              has_request_variables)
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_error, json_success
from zerver.models import Client, UserProfile


@api_key_only_webhook_view("AppFollow")
@has_request_variables
def api_appfollow_webhook(request, user_profile, client, stream=REQ(default="appfollow"),
                          payload=REQ(argument_type="body")):
    # type: (HttpRequest, UserProfile, Client, Text, Dict[str, Any]) -> HttpResponse
    try:
        message = payload["text"]
    except KeyError:
        return json_error(_("Missing 'text' argument in JSON"))
    app_name = re.search('\A(.+)', message).group(0)

    check_send_message(user_profile, client, "stream", [stream], app_name, convert_markdown(message))
    return json_success()

def convert_markdown(text):
    # type: (Text) -> Text
    # Converts Slack-style markdown to Zulip format
    # Implemented mainly for AppFollow messages
    # Not ready for general use as some edge-cases not handled
    # Convert Bold
    text = re.sub(r'(?:(?<=\s)|(?<=^))\*(.+?\S)\*(?=\s|$)', r'**\1**', text)
    # Convert Italics
    text = re.sub(r'\b_(\s*)(.+?)(\s*)_\b', r'\1*\2*\3', text)
    # Convert Strikethrough
    text = re.sub(r'(?:(?<=\s)|(?<=^))~(.+?\S)~(?=\s|$)', r'~~\1~~', text)

    return text

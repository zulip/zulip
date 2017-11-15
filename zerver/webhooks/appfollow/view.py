# Webhooks for external integrations.
import re
from typing import Any, Dict, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.models import UserProfile

@api_key_only_webhook_view("AppFollow")
@has_request_variables
def api_appfollow_webhook(request, user_profile, stream=REQ(default="appfollow"),
                          payload=REQ(argument_type="body")):
    # type: (HttpRequest, UserProfile, Text, Dict[str, Any]) -> HttpResponse
    message = payload["text"]
    app_name = re.search('\A(.+)', message).group(0)

    check_send_stream_message(user_profile, request.client, stream,
                              app_name, convert_markdown(message))
    return json_success()

def convert_markdown(text: Text) -> Text:
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

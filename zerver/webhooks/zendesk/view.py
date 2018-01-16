# Webhooks for external integrations.
from typing import Text

from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile, get_client

def truncate(string: Text, length: int) -> Text:
    if len(string) > length:
        string = string[:length-3] + '...'
    return string

@authenticated_rest_api_view(is_webhook=True)
@has_request_variables
def api_zendesk_webhook(request, user_profile, ticket_title=REQ(), ticket_id=REQ(),
                        message=REQ(), stream=REQ(default="zendesk")):
                        # type: (HttpRequest, UserProfile, str, str, str, str) -> HttpResponse
    """
    Zendesk uses trigers with message templates. This webhook uses the
    ticket_id and ticket_title to create a subject. And passes with zendesk
    user's configured message to zulip.
    """
    subject = truncate('#%s: %s' % (ticket_id, ticket_title), 60)
    check_send_stream_message(user_profile, get_client('ZulipZenDeskWebhook'),
                              stream, subject, message)
    return json_success()

from __future__ import absolute_import
from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message, create_stream_if_needed
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_int
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile

ZULIP_MESSAGE_TEMPLATE = "**{message_sender}**: `{text}`"
VALID_OPTIONS = {'SHOULD_NOT_BE_MAPPED': '0', 'SHOULD_BE_MAPPED': '1'}

@api_key_only_webhook_view('Slack')
@has_request_variables
def api_slack_webhook(request, user_profile,
                      user_name=REQ(),
                      text=REQ(),
                      channel_name=REQ(),
                      stream=REQ(default='slack'),
                      channels_map_to_topics=REQ(default='1')):
    # type: (HttpRequest, UserProfile, str, str, str, str, str) -> HttpResponse

    if channels_map_to_topics not in list(VALID_OPTIONS.values()):
        return json_error(_('Error: channels_map_to_topics parameter other than 0 or 1'))

    if channels_map_to_topics == VALID_OPTIONS['SHOULD_BE_MAPPED']:
        subject = "channel: {}".format(channel_name)
    else:
        stream = channel_name
        subject = _("Message from Slack")

    content = ZULIP_MESSAGE_TEMPLATE.format(message_sender=user_name, text=text)
    check_send_message(user_profile, request.client, "stream", [stream], subject, content)
    return json_success()

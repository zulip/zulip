from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message, \
    create_stream_if_needed
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_int, check_string
from zerver.models import UserProfile

ZULIP_MESSAGE_TEMPLATE = u"**{message_sender}**: `{text}`"
VALID_OPTIONS = {'SHOULD_NOT_BE_MAPPED': '0', 'SHOULD_BE_MAPPED': '1'}

@api_key_only_webhook_view('Slack')
@has_request_variables
def api_slack_webhook(request: HttpRequest, user_profile: UserProfile,
                      user_name: str=REQ(),
                      text: str=REQ(),
                      channel_name: str=REQ(),
                      stream: str=REQ(default='slack'),
                      channels_map_to_topics: str=REQ(default='1')) -> HttpRequest:

    if channels_map_to_topics not in list(VALID_OPTIONS.values()):
        return json_error(_('Error: channels_map_to_topics parameter other than 0 or 1'))

    if channels_map_to_topics == VALID_OPTIONS['SHOULD_BE_MAPPED']:
        subject = "channel: {}".format(channel_name)
    else:
        stream = channel_name
        subject = _("Message from Slack")

    content = ZULIP_MESSAGE_TEMPLATE.format(message_sender=user_name, text=text)
    check_send_stream_message(user_profile, request.client, stream, subject, content)
    return json_success()

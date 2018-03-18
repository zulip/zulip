from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.validator import check_int, check_string
from zerver.models import UserProfile

ZULIP_MESSAGE_TEMPLATE = u"**{message_sender}**: `{text}`"

@api_key_only_webhook_view('Slack')
@has_request_variables
def api_slack_webhook(request: HttpRequest, user_profile: UserProfile,
                      user_name: str=REQ(),
                      text: str=REQ(),
                      channel_name: str=REQ()) -> HttpRequest:
    subject = "channel: {}".format(channel_name)
    content = ZULIP_MESSAGE_TEMPLATE.format(message_sender=user_name, text=text)
    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()

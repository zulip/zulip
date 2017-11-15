# Webhooks for external integrations.
from typing import Text

from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile, get_client

# Desk.com's integrations all make the user supply a template, where it fills
# in stuff like {{customer.name}} and posts the result as a "data" parameter.
# There's no raw JSON for us to work from. Thus, it makes sense to just write
# a template Zulip message within Desk.com and have the webhook extract that
# from the "data" param and post it, which this does.
@authenticated_rest_api_view(is_webhook=True)
@has_request_variables
def api_deskdotcom_webhook(request, user_profile, data=REQ(),
                           topic=REQ(default="Desk.com notification"),
                           stream=REQ(default="desk.com")):
    # type: (HttpRequest, UserProfile, Text, Text, Text) -> HttpResponse
    check_send_stream_message(user_profile, get_client("ZulipDeskWebhook"),
                              stream, topic, data)
    return json_success()

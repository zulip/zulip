from django.http import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_send import check_send_stream_message
from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

ZULIP_MESSAGE_TEMPLATE = "**{message_sender}**: {text}"
VALID_OPTIONS = {"SHOULD_NOT_BE_MAPPED": "0", "SHOULD_BE_MAPPED": "1"}


@webhook_view("Slack", notify_bot_owner_on_invalid_json=False)
@has_request_variables
def api_slack_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    user_name: str = REQ(),
    text: str = REQ(),
    channel_name: str = REQ(),
    stream: str = REQ(default="slack"),
    channels_map_to_topics: str = REQ(default="1"),
) -> HttpResponse:
    if channels_map_to_topics not in list(VALID_OPTIONS.values()):
        raise JsonableError(_("Error: channels_map_to_topics parameter other than 0 or 1"))

    if channels_map_to_topics == VALID_OPTIONS["SHOULD_BE_MAPPED"]:
        subject = f"channel: {channel_name}"
    else:
        stream = channel_name
        subject = _("Message from Slack")

    content = ZULIP_MESSAGE_TEMPLATE.format(message_sender=user_name, text=text)
    client = RequestNotes.get_notes(request).client
    assert client is not None
    check_send_stream_message(user_profile, client, stream, subject, content)
    return json_success(request)

from django.http import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_send import check_send_stream_message
from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

ZULIP_MESSAGE_TEMPLATE = "**{message_sender}**: {text}"
VALID_OPTIONS = {"SHOULD_NOT_BE_MAPPED": "0", "SHOULD_BE_MAPPED": "1"}


@webhook_view("Slack", notify_bot_owner_on_invalid_json=False)
@typed_endpoint
def api_slack_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_name: str,
    text: str,
    channel_name: str,
    stream: str = "slack",
    channels_map_to_topics: str = "1",
) -> HttpResponse:
    if channels_map_to_topics not in VALID_OPTIONS.values():
        raise JsonableError(_("Error: channels_map_to_topics parameter other than 0 or 1"))

    if channels_map_to_topics == VALID_OPTIONS["SHOULD_BE_MAPPED"]:
        topic = f"channel: {channel_name}"
    else:
        stream = channel_name
        topic = _("Message from Slack")

    content = ZULIP_MESSAGE_TEMPLATE.format(message_sender=user_name, text=text)
    client = RequestNotes.get_notes(request).client
    assert client is not None
    check_send_stream_message(user_profile, client, stream, topic, content)
    return json_success(request)

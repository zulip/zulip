from typing import Optional

from django.http import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
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
    channels_map_to_topics: Optional[str] = None,
) -> HttpResponse:
    content = ZULIP_MESSAGE_TEMPLATE.format(message_sender=user_name, text=text)
    topic_name = "Message from Slack"

    if channels_map_to_topics is None:
        check_send_webhook_message(
            request,
            user_profile,
            topic_name,
            content,
        )
    elif channels_map_to_topics == VALID_OPTIONS["SHOULD_BE_MAPPED"]:
        # If the webhook URL has a user_specified_topic,
        # then this topic-channel mapping will not be used.
        topic_name = f"channel: {channel_name}"
        check_send_webhook_message(
            request,
            user_profile,
            topic_name,
            content,
        )
    elif channels_map_to_topics == VALID_OPTIONS["SHOULD_NOT_BE_MAPPED"]:
        # This channel-channel mapping will be used even if
        # there is a channel specified in the webhook URL.
        check_send_webhook_message(
            request,
            user_profile,
            topic_name,
            content,
            stream=channel_name,
        )
    else:
        raise JsonableError(_("Error: channels_map_to_topics parameter other than 0 or 1"))

    return json_success(request)

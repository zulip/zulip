from typing import Any, Dict, Optional

from django.http import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_slack_challenge_response, json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
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
    payload: JsonBodyPayload[WildValue],
    user_name: Optional[str] = None,
    text: Optional[str] = None,
    channel_name: Optional[str] = None,
    channels_map_to_topics: Optional[str] = None,
) -> HttpResponse:
    content = ZULIP_MESSAGE_TEMPLATE.format(message_sender=user_name, text=text)
    topic_name = "Message from Slack"

    outer_data: Dict[str, Any] = {
        "type": payload.get("type").tame(check_none_or(check_string)),
        "challenge": payload.get("challenge").tame(check_none_or(check_string)),
    }

    # Handle Slacks "challenge" handshake when first registering endpoint
    # to Event API.
    if outer_data["type"] == "url_verification" and outer_data["challenge"]:
        check_send_webhook_message(
            request,
            user_profile,
            "Integration notification",
            "Successfully registered endpoint to Slack!",
        )
        return json_slack_challenge_response(outer_data["challenge"])

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

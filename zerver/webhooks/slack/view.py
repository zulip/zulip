from typing import Any, Dict, Optional

from django.http import HttpRequest
from django.http.response import HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_slack_challenge_response, json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ZULIP_MESSAGE_TEMPLATE = "**{message_sender}**: {text}"
VALID_OPTIONS = {"SHOULD_NOT_BE_MAPPED": "0", "SHOULD_BE_MAPPED": "1"}


def is_bot_message(payload: WildValue) -> bool:
    app_api_id = payload.get("api_app_id").tame(check_none_or(check_string))
    bot_app_id = (
        payload.get("event", {})
        .get("bot_profile", {})
        .get("app_id")
        .tame(check_none_or(check_string))
    )
    return bot_app_id is not None and app_api_id == bot_app_id


def get_message_body(event_data: Dict[str, Any]) -> str:
    # TODO: Adapt Slack text formats such as italic, bold, strike though, etc.

    # TODO: Reformat mentions in messages, currently its <@USER_ID>.

    # TODO: Add support for messages with image files. Basic payload include links

    return ZULIP_MESSAGE_TEMPLATE.format(**event_data)


def get_channel_name_str(payload: WildValue) -> str:
    # TODO: Callback to Slack to get the actual channel name

    return payload.get("event", {}).get("channel").tame(check_string)


def get_sender_name_str(payload: WildValue) -> str:
    # TODO: Callback to Slack to get the actual sender name

    return payload.get("event", {}).get("user").tame(check_string)


@webhook_view("Slack", notify_bot_owner_on_invalid_json=False)
@typed_endpoint
def api_slack_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    channels_map_to_topics: Optional[str] = None,
) -> HttpResponse:
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

    # Prevent any Zulip messages sent through the Slack Bridge from looping
    # back here.
    if is_bot_message(payload):
        return json_success(request)

    event_dict = payload.get("event", {})
    event_data: Dict[str, Any] = {
        "type": event_dict.get("type").tame(check_string),
        "text": event_dict.get("text").tame(check_string),
        "channel": get_channel_name_str(payload),
        "message_sender": get_sender_name_str(payload),
    }

    if event_data["type"] == "message":
        content = get_message_body(event_data)
        topic_name = "Message from Slack"

        if channels_map_to_topics is None:
            check_send_webhook_message(request, user_profile, topic_name, content)
        elif channels_map_to_topics == VALID_OPTIONS["SHOULD_BE_MAPPED"]:
            # If the webhook URL has a user_specified_topic,
            # then this topic-channel mapping will not be used.
            topic_name = f"channel: {event_data['channel']}"
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
                stream=event_data["channel"],
            )
        else:
            # We want to becareful and always respond with HTTP 200 because Slack
            # will retry sending the payload again and again if we fail to respond
            # with 200 ok.

            # TODO: As a follow up might want to send a notification message
            # informing the user about this kind of error in a user-friendly way
            # instead of logging the error or raising Exception.
            pass

    return json_success(request)

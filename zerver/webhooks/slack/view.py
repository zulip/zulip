import re
from typing import Any, Dict, List, Optional

from django.http import HttpRequest
from django.http.response import HttpResponse
from typing_extensions import TypeAlias

from zerver.data_import.slack import check_token_access, get_slack_api_data
from zerver.data_import.slack_message_conversion import (
    SLACK_BOLD_REGEX,
    SLACK_ITALIC_REGEX,
    SLACK_STRIKETHROUGH_REGEX,
    SLACK_USERMENTION_REGEX,
    convert_link_format,
    convert_mailto_format,
    convert_markdown_syntax,
)
from zerver.decorator import webhook_view
from zerver.lib.response import json_slack_challenge_response, json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

FILE_STR = "\n*[{file_name}]({file_link})*"
ZULIP_MESSAGE_TEMPLATE = "**{message_sender}**: {text}"
VALID_OPTIONS = {"SHOULD_NOT_BE_MAPPED": "0", "SHOULD_BE_MAPPED": "1"}

SlackFileListT: TypeAlias = List[Dict[str, str]]
SlackAPIResponseT: TypeAlias = Dict[str, Any]

SLACK_CHANNELMENTION_REGEX = r"(?<=<#)(.*)(?=>)"


def is_bot_message(payload: WildValue) -> bool:
    app_api_id = payload.get("api_app_id").tame(check_none_or(check_string))
    bot_app_id = (
        payload.get("event", {})
        .get("bot_profile", {})
        .get("app_id")
        .tame(check_none_or(check_string))
    )
    return bot_app_id is not None and app_api_id == bot_app_id


def convert_mentions(text: str, app_token: str) -> str:
    tokens = text.split(" ")
    for iterator in range(len(tokens)):
        slack_usermention_match = re.search(SLACK_USERMENTION_REGEX, tokens[iterator], re.VERBOSE)
        slack_channelmention_match = re.search(
            SLACK_CHANNELMENTION_REGEX, tokens[iterator], re.MULTILINE
        )

        if slack_usermention_match:
            # We convert user mentions into a mention-like message to because
            # there are no way of mapping between a users Slack and Zulip account

            slack_id = slack_usermention_match.group(2)
            user_obj = get_slack_user_info(user_id=slack_id, token=app_token)
            tokens[iterator] = "@**" + user_obj["name"] + "**"

        elif slack_channelmention_match:
            # We convert channel mentions to a mention-like messages to avoid
            # mentioning the wrong channel over at Zulip.

            channel_info: List[str] = slack_channelmention_match.group(0).split("|")
            channel_name = channel_info[1]
            tokens[iterator] = f"**#{channel_name}**" if channel_name else "**#[private channel]**"

            # TODO: as a follow up, we could probably discuss and decide on a
            # more proper way to handle messages mentioning channels.

    text = " ".join(tokens)
    return text


def get_slack_user_info(user_id: str, token: str) -> SlackAPIResponseT:
    # TODO: additional improvement would be to cache the response
    user_obj = get_slack_api_data(
        "https://slack.com/api/users.info", get_param="user", token=token, user=user_id
    )
    return user_obj


def get_slack_channel_info(channel_id: str, token: str) -> SlackAPIResponseT:
    # TODO: additional improvement would be to cache the response
    channel_obj = get_slack_api_data(
        "https://slack.com/api/conversations.info",
        get_param="channel",
        token=token,
        channel=channel_id,
    )
    return channel_obj


def convert_to_zulip_markdown(text: str, slack_app_token: str) -> str:
    # TODO: As a follow up, we could potentially adapt and use
    # the actual convert_to_zulip_markdown().

    text = convert_markdown_syntax(text, SLACK_BOLD_REGEX, "**")
    text = convert_markdown_syntax(text, SLACK_STRIKETHROUGH_REGEX, "~~")
    text = convert_markdown_syntax(text, SLACK_ITALIC_REGEX, "*")

    # Map Slack's mention all: '<!everyone>' to '@**all** '
    # Map Slack's mention all: '<!channel>' to '@**all** '
    # Map Slack's mention all: '<!here>' to '@**all** '
    # No regex for this as it can be present anywhere in the sentence
    text = text.replace("<!everyone>", "@**all**")
    text = text.replace("<!channel>", "@**all**")
    text = text.replace("<!here>", "@**all**")

    text = convert_mentions(text, slack_app_token)

    text, _ = convert_link_format(text)
    text, _ = convert_mailto_format(text)

    return text


def get_message_body(event_data: Dict[str, Any]) -> str:
    body = ZULIP_MESSAGE_TEMPLATE
    for file_obj in event_data["file_obj_list"]:
        body += FILE_STR.format(**file_obj)

    return body.format(**event_data)


def get_channel_name_str(payload: WildValue, token: str) -> str:
    channel_id = payload.get("event", {}).get("channel").tame(check_string)
    channel_obj = get_slack_channel_info(channel_id, token)

    return channel_obj["name"]


def get_sender_name_str(payload: WildValue, token: str) -> str:
    user_id = payload.get("event", {}).get("user").tame(check_string)
    user_obj = get_slack_user_info(user_id, token)

    return user_obj["name"]


def convert_file_dict(file_dict: WildValue) -> SlackFileListT:
    file_obj_list = [
        {
            "file_link": file_obj.get("permalink").tame(check_string),
            "file_name": file_obj.get("title").tame(check_string),
        }
        for file_obj in file_dict
    ]
    return file_obj_list


@webhook_view("Slack", notify_bot_owner_on_invalid_json=False)
@typed_endpoint
def api_slack_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    slack_app_token: str,
    channels_map_to_topics: Optional[str] = None,
) -> HttpResponse:
    topic_name = "Message from Slack"

    outer_data: Dict[str, Any] = {
        "type": payload.get("type").tame(check_none_or(check_string)),
        "challenge": payload.get("challenge").tame(check_none_or(check_string)),
    }

    # Block retries from Slack.
    if "X-Slack-Retry-Num" in request.headers:
        return json_success(request)

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

    check_token_access(slack_app_token)

    event_dict = payload.get("event", {})
    file_dict = event_dict.get("files")
    raw_text = event_dict.get("text", "").tame(check_string)

    event_data: Dict[str, Any] = {
        "type": event_dict.get("type").tame(check_string),
        "text": convert_to_zulip_markdown(raw_text, slack_app_token),
        "channel": get_channel_name_str(payload, slack_app_token),
        "message_sender": get_sender_name_str(payload, slack_app_token),
        "file_obj_list": convert_file_dict(file_dict) if file_dict else [],
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

            pass

            # TODO: As a follow up might want to send a notification message
            # informing the user about this kind of error in a user-friendly way
            # instead of logging the error or raising Exception.

    return json_success(request)

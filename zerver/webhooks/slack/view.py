import re
from typing import Any, TypeAlias

from django.http import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _

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
from zerver.lib.exceptions import JsonableError, UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

FILE_STR = "\n*[{file_name}]({file_link})*"
ZULIP_MESSAGE_TEMPLATE = "**{message_sender}**: {text}"
VALID_OPTIONS = {"SHOULD_NOT_BE_MAPPED": "0", "SHOULD_BE_MAPPED": "1"}

SlackFileListT: TypeAlias = list[dict[str, str]]

SLACK_CHANNELMENTION_REGEX = r"(?<=<#)(.*)(?=>)"


def is_zulip_slack_bridge_bot_message(payload: WildValue) -> bool:
    app_api_id = payload.get("api_app_id").tame(check_none_or(check_string))
    bot_app_id = (
        payload.get("event", {})
        .get("bot_profile", {})
        .get("app_id")
        .tame(check_none_or(check_string))
    )
    return bot_app_id is not None and app_api_id == bot_app_id


def convert_mentions(text: str) -> str:
    tokens = text.split(" ")
    for iterator in range(len(tokens)):
        slack_usermention_match = re.search(SLACK_USERMENTION_REGEX, tokens[iterator], re.VERBOSE)
        slack_channelmention_match = re.search(
            SLACK_CHANNELMENTION_REGEX, tokens[iterator], re.MULTILINE
        )

        if slack_usermention_match:
            # TODO: Callback to Slack API
            pass

        elif slack_channelmention_match:
            # Convert Slack channel mentions to a mention-like syntax so that
            # a mention isn't triggered for a Zulip channel with the same name.
            channel_info: list[str] = slack_channelmention_match.group(0).split("|")
            channel_name = channel_info[1]
            tokens[iterator] = f"**#{channel_name}**" if channel_name else "**#[private channel]**"

    text = " ".join(tokens)
    return text


def convert_to_zulip_markdown(text: str) -> str:
    # This is a modified version of `convert_to_zulip_markdown` in
    # `slack_message_conversion.py`, which cannot be used directly
    # due to differences in the Slack import data and Slack webhook
    # payloads.
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

    text = convert_mentions(text)

    text, _ = convert_link_format(text)
    text, _ = convert_mailto_format(text)

    return text


def get_message_body(event_data: dict[str, Any]) -> str:
    # TODO: Reformat mentions in messages, currently its <@USER_ID>.

    body = ZULIP_MESSAGE_TEMPLATE.format(**event_data)
    for file_obj in event_data["file_obj_list"]:
        body += FILE_STR.format(**file_obj)

    return body


def get_channel_name_str(payload: WildValue) -> str:
    # TODO: Callback to Slack to get the actual channel name

    return payload.get("event", {}).get("channel").tame(check_string)


def get_sender_name_str(payload: WildValue) -> str:
    # TODO: Callback to Slack to get the actual sender name

    return payload.get("event", {}).get("user").tame(check_string)


def is_challenge_handshake(payload: WildValue) -> bool:
    return payload.get("type").tame(check_string) == "url_verification"


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
    channels_map_to_topics: str | None = None,
) -> HttpResponse:
    topic_name = "Message from Slack"

    # Handle initial URL verification handshake for Slack Events API.
    if is_challenge_handshake(payload):
        challenge = payload.get("challenge").tame(check_string)
        check_send_webhook_message(
            request,
            user_profile,
            "Integration events",
            "Successfully verified webhook URL with Slack!",
        )
        return json_success(request=request, data={"challenge": challenge})

    # Prevent any Zulip messages sent through the Slack Bridge from looping
    # back here.
    if is_zulip_slack_bridge_bot_message(payload):
        return json_success(request)

    event_dict = payload.get("event", {})
    event_type = event_dict.get("type").tame(check_string)
    if event_type == "message":
        file_dict = event_dict.get("files")
        raw_text = event_dict.get("text", "").tame(check_string)

        event_data: dict[str, Any] = {
            "text": convert_to_zulip_markdown(raw_text),
            "channel": get_channel_name_str(payload) if channels_map_to_topics else None,
            "message_sender": get_sender_name_str(payload),
            "file_obj_list": convert_file_dict(file_dict) if file_dict else [],
        }
        content = get_message_body(event_data)

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
            raise JsonableError(_("Error: channels_map_to_topics parameter other than 0 or 1"))
    else:
        raise UnsupportedWebhookEventTypeError(event_type)

    return json_success(request)

import re
from typing import Any, TypeAlias

from django.http import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_send import send_rate_limited_pm_notification_to_bot_owner
from zerver.data_import.slack import check_token_access, get_slack_api_data
from zerver.data_import.slack_message_conversion import (
    SLACK_USERMENTION_REGEX,
    convert_slack_formatting,
    convert_slack_workspace_mentions,
    replace_links,
)
from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError, UnsupportedWebhookEventTypeError
from zerver.lib.request import RequestVariableMissingError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

FILE_LINK_TEMPLATE = "\n*[{file_name}]({file_link})*"
ZULIP_MESSAGE_TEMPLATE = "**{sender}**: {text}"
VALID_OPTIONS = {"SHOULD_NOT_BE_MAPPED": "0", "SHOULD_BE_MAPPED": "1"}

SlackFileListT: TypeAlias = list[dict[str, str]]
SlackAPIResponseT: TypeAlias = dict[str, Any]

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


def get_slack_channel_name(channel_id: str, token: str) -> str:
    slack_channel_data = get_slack_api_data(
        "https://slack.com/api/conversations.info",
        get_param="channel",
        # Sleeping is not permitted from webhook code.
        raise_if_rate_limited=True,
        token=token,
        channel=channel_id,
    )
    return slack_channel_data["name"]


def get_slack_sender_name(user_id: str, token: str) -> str:
    slack_user_data = get_slack_api_data(
        "https://slack.com/api/users.info",
        get_param="user",
        # Sleeping is not permitted from webhook code.
        raise_if_rate_limited=True,
        token=token,
        user=user_id,
    )
    return slack_user_data["name"]


def convert_slack_user_and_channel_mentions(text: str, app_token: str) -> str:
    tokens = text.split(" ")
    for iterator in range(len(tokens)):
        slack_usermention_match = re.search(SLACK_USERMENTION_REGEX, tokens[iterator], re.VERBOSE)
        slack_channelmention_match = re.search(
            SLACK_CHANNELMENTION_REGEX, tokens[iterator], re.MULTILINE
        )
        if slack_usermention_match:
            # Convert Slack user mentions to a mention-like syntax since there
            # is no way to map Slack and Zulip users.
            slack_id = slack_usermention_match.group(2)
            user_name = get_slack_sender_name(user_id=slack_id, token=app_token)
            tokens[iterator] = "@**" + user_name + "**"
        elif slack_channelmention_match:
            # Convert Slack channel mentions to a mention-like syntax so that
            # a mention isn't triggered for a Zulip channel with the same name.
            channel_info: list[str] = slack_channelmention_match.group(0).split("|")
            channel_name = channel_info[1]
            tokens[iterator] = (
                f"**#{channel_name}**" if channel_name else "**#[private Slack channel]**"
            )
    text = " ".join(tokens)
    return text


# This is a modified version of `convert_to_zulip_markdown` in
# `slack_message_conversion.py`, which cannot be used directly
# due to differences in the Slack import data and Slack webhook
# payloads.
def convert_to_zulip_markdown(text: str, slack_app_token: str) -> str:
    text = convert_slack_formatting(text)
    text = convert_slack_workspace_mentions(text)
    text = convert_slack_user_and_channel_mentions(text, slack_app_token)
    return text


def convert_raw_file_data(file_dict: WildValue) -> SlackFileListT:
    files = [
        {
            "file_link": file.get("permalink").tame(check_string),
            "file_name": file.get("title").tame(check_string),
        }
        for file in file_dict
    ]
    return files


def get_message_body(text: str, sender: str, files: SlackFileListT) -> str:
    body = ZULIP_MESSAGE_TEMPLATE.format(sender=sender, text=text)
    for file in files:
        body += FILE_LINK_TEMPLATE.format(**file)
    return body


def is_challenge_handshake(payload: WildValue) -> bool:
    return payload.get("type").tame(check_string) == "url_verification"


def handle_slack_webhook_message(
    request: HttpRequest,
    user_profile: UserProfile,
    content: str,
    channel: str | None,
    channels_map_to_topics: str | None,
) -> None:
    topic_name = "Message from Slack"
    if channels_map_to_topics is None:
        check_send_webhook_message(request, user_profile, topic_name, content)
    elif channels_map_to_topics == VALID_OPTIONS["SHOULD_BE_MAPPED"]:
        topic_name = f"channel: {channel}"
        check_send_webhook_message(request, user_profile, topic_name, content)
    elif channels_map_to_topics == VALID_OPTIONS["SHOULD_NOT_BE_MAPPED"]:
        check_send_webhook_message(
            request,
            user_profile,
            topic_name,
            content,
            stream=channel,
        )
    else:
        raise JsonableError(_("Error: channels_map_to_topics parameter other than 0 or 1"))


def is_retry_call_from_slack(request: HttpRequest) -> bool:
    return "X-Slack-Retry-Num" in request.headers


SLACK_INTEGRATION_TOKEN_SCOPES = {
    "channels:read",
    "channels:history",
    "users:read",
    "emoji:read",
    "team:read",
    "users:read.email",
}

INVALID_SLACK_TOKEN_MESSAGE = """
Hi there! It looks like you're trying to set up a Slack webhook
integration. There seems to be an issue with the Slack app token
you've included in the URL (if any). Please check the error message
below to see if you're missing anything:

Error: {error_message}

Feel free to reach out to the [Zulip development community](https://chat.zulip.org/#narrow/channel/127-integrations)
if you need further help!
"""


@webhook_view("Slack", notify_bot_owner_on_invalid_json=False)
@typed_endpoint
def api_slack_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    slack_app_token: str = "",
    channels_map_to_topics: str | None = None,
) -> HttpResponse:
    if request.content_type != "application/json":
        # Handle Slack's legacy Outgoing Webhook Service payload.
        expected_legacy_variable = ["user_name", "text", "channel_name"]
        legacy_payload = {}
        for variable in expected_legacy_variable:
            if variable in request.POST:
                legacy_payload[variable] = request.POST[variable]
            elif variable in request.GET:  # nocoverage
                legacy_payload[variable] = request.GET[variable]
            else:
                raise RequestVariableMissingError(variable)

        text = convert_slack_formatting(legacy_payload["text"])
        text = replace_links(text)
        text = get_message_body(text, legacy_payload["user_name"], [])
        handle_slack_webhook_message(
            request,
            user_profile,
            text,
            legacy_payload["channel_name"],
            channels_map_to_topics,
        )
        return json_success(request)

    try:
        val = request.body.decode(request.encoding or "utf-8")
    except UnicodeDecodeError:  # nocoverage
        raise JsonableError(_("Malformed payload"))
    payload = to_wild_value("payload", val)

    # Handle initial URL verification handshake for Slack Events API.
    if is_challenge_handshake(payload):
        challenge = payload.get("challenge").tame(check_string)
        try:
            if slack_app_token == "":
                raise ValueError("slack_app_token is missing.")
            check_token_access(slack_app_token, SLACK_INTEGRATION_TOKEN_SCOPES)
        except (ValueError, Exception) as e:
            send_rate_limited_pm_notification_to_bot_owner(
                user_profile,
                user_profile.realm,
                INVALID_SLACK_TOKEN_MESSAGE.format(error_message=e),
            )
            # Return json success here as to not trigger retry calls
            # from Slack.
            return json_success(request)
        check_send_webhook_message(
            request,
            user_profile,
            "Integration events",
            get_setup_webhook_message("Slack"),
        )
        return json_success(request=request, data={"challenge": challenge})

    # A Slack fail condition occurs when we don't respond with HTTP 200
    # within 3 seconds after Slack calls our endpoint. If this happens,
    # Slack will retry sending the same payload. This is often triggered
    # because of we have to do two callbacks for each call. To avoid
    # sending the same message multiple times, we block subsequent retry
    # calls from Slack.
    if is_retry_call_from_slack(request):
        return json_success(request)

    # Prevent any Zulip messages sent through the Slack Bridge from looping
    # back here.
    if is_zulip_slack_bridge_bot_message(payload):
        return json_success(request)

    event_dict = payload.get("event", {})
    event_type = event_dict.get("type").tame(check_string)

    if event_type != "message":
        raise UnsupportedWebhookEventTypeError(event_type)

    raw_files = event_dict.get("files")
    files = convert_raw_file_data(raw_files) if raw_files else []
    raw_text = event_dict.get("text", "").tame(check_string)
    text = convert_to_zulip_markdown(raw_text, slack_app_token)
    user_id = event_dict.get("user").tame(check_none_or(check_string))
    if user_id is None:
        # This is likely a Slack integration bot message. The sender of these
        # messages doesn't have a user profile and would require additional
        # formatting to handle. Refer to the Slack Incoming Webhook integration
        # for how to add support for this type of payload.
        raise UnsupportedWebhookEventTypeError(
            "integration bot message"
            if event_dict["subtype"].tame(check_string) == "bot_message"
            else "unknown Slack event"
        )
    sender = get_slack_sender_name(user_id, slack_app_token)
    content = get_message_body(text, sender, files)
    channel_id = event_dict.get("channel").tame(check_string)
    channel = (
        get_slack_channel_name(channel_id, slack_app_token) if channels_map_to_topics else None
    )

    handle_slack_webhook_message(request, user_profile, content, channel, channels_map_to_topics)
    return json_success(request)

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import connection, transaction
from django.utils.translation import gettext as _
from pydantic import BaseModel, Field

from zerver.actions.message_flags import do_mark_stream_messages_as_read, do_update_message_flags
from zerver.actions.message_send import check_send_message
from zerver.actions.reactions import check_add_reaction
from zerver.lib.exceptions import JsonableError
from zerver.lib.mcp.auth import MCP_CLIENT_NAME
from zerver.lib.message import messages_for_ids
from zerver.lib.narrow import NarrowParameter, fetch_messages, parse_anchor_value
from zerver.lib.streams import access_stream_by_name, do_get_streams
from zerver.lib.topic import TOPIC_NAME, get_topic_history_for_stream
from zerver.lib.users import get_users_for_api
from zerver.models import UserMessage, UserProfile
from zerver.models.clients import get_client

# Cap on how many messages/users a single tool call returns, to keep
# responses token-efficient for the calling agent.
MAX_MESSAGE_RESULTS = 50
MAX_USER_RESULTS = 200
# Caps on list inputs, to bound the work a single tool call can request.
MAX_DM_RECIPIENTS = 100
MAX_MARK_READ_IDS = 1000


# === Tool argument schemas ===
#
# Each tool validates its arguments with a pydantic model, whose JSON Schema
# is what we advertise in tools/list.  Descriptions are written for an agent
# audience.


class SearchMessagesArguments(BaseModel):
    query: str = Field(description="Full-text search string to match in message content.")
    channel: str | None = Field(
        default=None, description="Optional channel (stream) name to restrict the search to."
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=MAX_MESSAGE_RESULTS,
        description="Maximum number of most-recent matching messages to return.",
    )


class GetMessagesArguments(BaseModel):
    channel: str = Field(description="Channel (stream) name to read messages from.")
    topic: str | None = Field(default=None, description="Optional topic within the channel.")
    limit: int = Field(
        default=30,
        ge=1,
        le=MAX_MESSAGE_RESULTS,
        description="Maximum number of most-recent messages to return.",
    )


class ListChannelsArguments(BaseModel):
    pass


class ListTopicsArguments(BaseModel):
    channel: str = Field(description="Channel (stream) name to list recent topics for.")


class GetUsersArguments(BaseModel):
    query: str | None = Field(
        default=None,
        description="Optional case-insensitive substring matched against user names and emails.",
    )
    limit: int = Field(
        default=50, ge=1, le=MAX_USER_RESULTS, description="Maximum number of users to return."
    )


class SendMessageArguments(BaseModel):
    channel: str | None = Field(
        default=None,
        description="Channel (stream) name to send to. Provide either channel (with topic) or"
        " direct_message_recipients.",
    )
    topic: str | None = Field(
        default=None, description="Topic for the channel message. Required when channel is set."
    )
    direct_message_recipients: list[int] | None = Field(
        default=None,
        max_length=MAX_DM_RECIPIENTS,
        description="Recipient user IDs (as returned by get_users) for a direct message.",
    )
    content: str = Field(description="Message content, in Zulip-flavored Markdown.")


class AddReactionArguments(BaseModel):
    message_id: int = Field(description="ID of the message to react to.")
    emoji_name: str = Field(description="Name of the emoji, e.g. 'thumbs_up'.")


class MarkReadArguments(BaseModel):
    channel: str | None = Field(
        default=None,
        description="Channel (stream) name to mark read; combine with topic for a single topic.",
    )
    topic: str | None = Field(default=None, description="Topic within the channel to mark read.")
    message_ids: list[int] | None = Field(
        default=None,
        max_length=MAX_MARK_READ_IDS,
        description="Specific message IDs to mark read, instead of a channel/topic.",
    )


# === Tool handlers ===


def _compact_message(message: dict[str, Any]) -> dict[str, Any]:
    # Project Zulip's wide message dict down to the high-signal fields an
    # agent needs, keeping responses token-efficient.
    recipient = message["display_recipient"]
    compact: dict[str, Any] = {
        "id": message["id"],
        "sender": message["sender_full_name"],
        "timestamp": message["timestamp"],
        "content": message["content"],
    }
    if isinstance(recipient, str):
        compact["channel"] = recipient
        compact["topic"] = message[TOPIC_NAME]
    else:
        compact["direct_message_recipients"] = [user["full_name"] for user in recipient]
    return compact


def _fetch_messages_for_narrow(
    user_profile: UserProfile, narrow: list[NarrowParameter], limit: int
) -> list[dict[str, Any]]:
    realm = user_profile.realm
    # Mirror message_fetch's repeatable-read transaction so the two-step fetch
    # (ids, then message dicts) sees a consistent snapshot; otherwise a message
    # deleted between the steps would raise, or edits could leak inconsistently.
    with transaction.atomic(durable=True):
        if not settings.TEST_SUITE:  # nocoverage
            cursor = connection.cursor()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

        query_info = fetch_messages(
            narrow=narrow,
            user_profile=user_profile,
            realm=realm,
            is_web_public_query=False,
            anchor_info=parse_anchor_value("newest", False),
            include_anchor=True,
            num_before=limit,
            num_after=0,
        )

        result_message_ids: list[int] = []
        user_message_flags: dict[int, list[str]] = {}
        if query_info.include_history:
            result_message_ids = [row[0] for row in query_info.rows]
            um_rows = UserMessage.objects.filter(
                user_profile=user_profile, message_id__in=result_message_ids
            )
            user_message_flags = {um.message_id: um.flags_list() for um in um_rows}
            for message_id in result_message_ids:
                user_message_flags.setdefault(message_id, ["read", "historical"])
        else:
            for row in query_info.rows:
                message_id = row[0]
                user_message_flags[message_id] = UserMessage.flags_list_for_flags(row[1])
                result_message_ids.append(message_id)

        message_list = messages_for_ids(
            message_ids=result_message_ids,
            user_message_flags=user_message_flags,
            search_fields={},
            apply_markdown=False,
            client_gravatar=False,
            allow_empty_topic_name=True,
            message_edit_history_visibility_policy=realm.message_edit_history_visibility_policy,
            user_profile=user_profile,
            realm=realm,
        )
    return [_compact_message(message) for message in message_list]


def _handle_search_messages(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = SearchMessagesArguments.model_validate(arguments)
    narrow = []
    if args.channel is not None:
        narrow.append(NarrowParameter(operator="channel", operand=args.channel))
    narrow.append(NarrowParameter(operator="search", operand=args.query))
    return {"messages": _fetch_messages_for_narrow(user_profile, narrow, args.limit)}


def _handle_get_messages(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = GetMessagesArguments.model_validate(arguments)
    narrow = [NarrowParameter(operator="channel", operand=args.channel)]
    if args.topic is not None:
        narrow.append(NarrowParameter(operator="topic", operand=args.topic))
    return {"messages": _fetch_messages_for_narrow(user_profile, narrow, args.limit)}


def _handle_list_channels(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    ListChannelsArguments.model_validate(arguments)
    streams = do_get_streams(user_profile, include_public=True, include_subscribed=True)
    return {
        "channels": [
            {
                "id": stream["stream_id"],
                "name": stream["name"],
                "description": stream["description"],
            }
            for stream in streams
        ]
    }


def _handle_list_topics(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = ListTopicsArguments.model_validate(arguments)
    stream, _sub = access_stream_by_name(user_profile, args.channel)
    assert stream.recipient_id is not None
    topics = get_topic_history_for_stream(
        user_profile=user_profile,
        recipient_id=stream.recipient_id,
        public_history=stream.is_history_public_to_subscribers(),
        allow_empty_topic_name=True,
    )
    return {
        "topics": [{"name": topic["name"], "max_message_id": topic["max_id"]} for topic in topics]
    }


def _handle_get_users(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = GetUsersArguments.model_validate(arguments)
    users = get_users_for_api(
        realm=user_profile.realm,
        acting_user=user_profile,
        client_gravatar=False,
        user_avatar_url_field_optional=True,
        include_custom_profile_fields=False,
    )
    needle = args.query.lower() if args.query is not None else None
    matched = [
        user
        for user in users.values()
        if needle is None
        or needle in user["full_name"].lower()
        or needle in user.get("email", "").lower()
    ]
    # Sort by name so the limit returns a stable, predictable subset.
    matched.sort(key=lambda user: user["full_name"].lower())
    return {
        "users": [
            {
                "user_id": user["user_id"],
                "full_name": user["full_name"],
                "email": user.get("email", ""),
            }
            for user in matched[: args.limit]
        ]
    }


def _handle_send_message(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = SendMessageArguments.model_validate(arguments)
    if (args.channel is not None) == bool(args.direct_message_recipients):
        raise JsonableError(
            _("Provide exactly one of channel (with topic) or direct_message_recipients.")
        )
    client = get_client(MCP_CLIENT_NAME)
    if args.channel is not None:
        if args.topic is None:
            raise JsonableError(_("Topic is required when sending to a channel."))
        result = check_send_message(
            user_profile, client, "stream", [args.channel], args.topic, args.content
        )
    else:
        assert args.direct_message_recipients is not None
        result = check_send_message(
            user_profile, client, "private", args.direct_message_recipients, None, args.content
        )
    return {"message_id": result.message_id}


def _handle_add_reaction(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = AddReactionArguments.model_validate(arguments)
    # check_add_reaction takes a row lock via access_message, so it must run
    # inside a transaction; this is the outermost one for the request.
    with transaction.atomic(durable=True):
        check_add_reaction(user_profile, args.message_id, args.emoji_name, None, None)
    return {"message_id": args.message_id, "emoji_name": args.emoji_name}


def _handle_mark_read(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = MarkReadArguments.model_validate(arguments)
    if (args.message_ids is not None) == (args.channel is not None):
        raise JsonableError(_("Provide exactly one of message_ids or a channel to mark as read."))
    if args.message_ids is not None:
        # do_update_message_flags manages its own (durable) transaction.
        count, _ignored = do_update_message_flags(user_profile, "add", "read", args.message_ids)
        return {"messages_marked_read": count}
    assert args.channel is not None
    stream, _sub = access_stream_by_name(user_profile, args.channel)
    assert stream.recipient_id is not None
    # do_mark_stream_messages_as_read manages its own (durable) transaction.
    count = do_mark_stream_messages_as_read(user_profile, stream.recipient_id, args.topic)
    return {"messages_marked_read": count}


# === Tool registry ===


@dataclass
class MCPTool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[UserProfile, dict[str, Any]], dict[str, Any]]
    # Whether the tool only reads state; surfaced to clients as readOnlyHint.
    read_only: bool

    def to_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.arguments_model.model_json_schema(),
            "annotations": {"readOnlyHint": self.read_only},
        }


MCP_TOOLS: list[MCPTool] = [
    MCPTool(
        "search_messages",
        "Search recent messages by full-text query, optionally within a channel.",
        SearchMessagesArguments,
        _handle_search_messages,
        read_only=True,
    ),
    MCPTool(
        "get_messages",
        "Get the most recent messages in a channel, optionally filtered to a topic.",
        GetMessagesArguments,
        _handle_get_messages,
        read_only=True,
    ),
    MCPTool(
        "list_channels",
        "List channels (streams) the user can access.",
        ListChannelsArguments,
        _handle_list_channels,
        read_only=True,
    ),
    MCPTool(
        "list_topics",
        "List recent topics in a channel.",
        ListTopicsArguments,
        _handle_list_topics,
        read_only=True,
    ),
    MCPTool(
        "get_users",
        "List users in the organization, optionally filtered by a name or email substring.",
        GetUsersArguments,
        _handle_get_users,
        read_only=True,
    ),
    MCPTool(
        "send_message",
        "Send a message to a channel topic or as a direct message.",
        SendMessageArguments,
        _handle_send_message,
        read_only=False,
    ),
    MCPTool(
        "add_reaction",
        "Add an emoji reaction to a message.",
        AddReactionArguments,
        _handle_add_reaction,
        read_only=False,
    ),
    MCPTool(
        "mark_read",
        "Mark messages as read, by channel/topic or by specific message IDs.",
        MarkReadArguments,
        _handle_mark_read,
        read_only=False,
    ),
]

MCP_TOOLS_BY_NAME: dict[str, MCPTool] = {tool.name: tool for tool in MCP_TOOLS}


def get_mcp_tool_definitions() -> list[dict[str, Any]]:
    return [tool.to_definition() for tool in MCP_TOOLS]

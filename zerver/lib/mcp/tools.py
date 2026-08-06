from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils.translation import gettext as _
from pydantic import BaseModel, ConfigDict, Field

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import messages_for_ids
from zerver.lib.narrow import (
    AnchorInfo,
    NarrowParameter,
    clean_narrow_for_message_fetch,
    fetch_messages,
    parse_anchor_value,
)
from zerver.lib.streams import access_stream_by_name, do_get_streams
from zerver.lib.topic import TOPIC_NAME, get_topic_history_for_stream
from zerver.lib.users import check_user_can_access_all_users, get_accessible_user_ids
from zerver.models import UserMessage, UserProfile
from zerver.models.linkifiers import linkifiers_for_realm
from zerver.views.message_fetch import MAX_MESSAGES_PER_FETCH

MCP_CLIENT_NAME = "ZulipMCP"

# Matches the web app's batch size for a narrowed view, and stays well
# under the output limits MCP clients impose on a single tool result.
DEFAULT_NUM_BEFORE = 100


class NarrowTerm(NarrowParameter):
    # Unlike the REST API, MCP tool arguments reject unknown keys, so
    # that a misspelled field in a narrow term fails loudly.
    model_config = ConfigDict(extra="forbid")


class GetMessagesArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrow: list[NarrowTerm] = Field(
        default=[],
        description='Filters combined with AND, in Zulip\'s narrow format: {"operator":'
        ' ..., "operand": ..., "negated": ...}. The operators are documented at'
        " https://zulip.com/api/get-messages#parameter-narrow and"
        " https://zulip.com/help/search-for-messages. An empty narrow returns the"
        " newest messages from the user's combined feed.",
    )
    anchor: int | Literal["newest", "oldest", "first_unread"] = Field(
        default="newest",
        description='Message ID to read around, or "newest", "oldest", or'
        ' "first_unread" (the user\'s first unread message in this narrow).',
    )
    include_anchor: bool = Field(
        default=True,
        description="Whether to include the anchor message itself. Set false when paging"
        " from a message you already have, so it is not returned twice.",
    )
    num_before: int = Field(
        default=DEFAULT_NUM_BEFORE,
        ge=0,
        description="How many messages to return from before the anchor.",
    )
    num_after: int = Field(
        default=0, ge=0, description="How many messages to return from after the anchor."
    )


class ListChannelsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListLinkifiersArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListTopicsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = Field(description="Channel name to list recent topics for.")


class GetUsersArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(
        default=None,
        description="Case-insensitive substring matched against user names and email addresses.",
    )
    # Like GET /users, which returns all users, this has no upper bound.
    limit: int = Field(default=50, ge=1, description="Maximum number of users to return.")


def _compact_user(user_id: int, full_name: str) -> dict[str, Any]:
    """Full names are not unique in Zulip, so a person is identified by user
    ID, which is also what narrows and message recipients are specified with.
    """
    return {"user_id": user_id, "full_name": full_name}


def _compact_message(message: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "id": message["id"],
        "sender": _compact_user(message["sender_id"], message["sender_full_name"]),
        "timestamp": message["timestamp"],
        "content": message["content"],
    }
    if message["type"] == "stream":
        compact["channel"] = message["display_recipient"]
        compact["topic"] = message[TOPIC_NAME]
    else:
        compact["direct_message_with"] = [
            _compact_user(recipient["id"], recipient["full_name"])
            for recipient in sorted(message["display_recipient"], key=lambda r: r["id"])
        ]
    return compact


def _fetch_messages(
    user_profile: UserProfile,
    narrow: list[NarrowParameter] | None,
    anchor_info: AnchorInfo,
    include_anchor: bool,
    num_before: int,
    num_after: int,
) -> dict[str, Any]:
    realm = user_profile.realm
    with transaction.atomic(durable=True):
        # Mirror GET /messages: repeatable-read isolation keeps the search
        # and the fetch of the matched messages consistent with each other.
        # See zerver/views/message_fetch.py for why tests must skip this.
        if not settings.TEST_SUITE:  # nocoverage
            cursor = connection.cursor()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

        query_info = fetch_messages(
            narrow=narrow,
            user_profile=user_profile,
            realm=realm,
            is_web_public_query=False,
            anchor_info=anchor_info,
            include_anchor=include_anchor,
            num_before=num_before,
            num_after=num_after,
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
                if message_id not in user_message_flags:
                    user_message_flags[message_id] = ["read", "historical"]
        else:
            for row in query_info.rows:
                message_id = row[0]
                user_message_flags[message_id] = UserMessage.flags_list_for_flags(row[1])
                result_message_ids.append(message_id)

        messages = messages_for_ids(
            message_ids=result_message_ids,
            user_message_flags=user_message_flags,
            search_fields={},
            apply_markdown=False,
            client_gravatar=True,
            allow_empty_topic_name=False,
            message_edit_history_visibility_policy=realm.message_edit_history_visibility_policy,
            user_profile=user_profile,
            realm=realm,
        )

    return {
        "messages": [_compact_message(message) for message in messages],
        "anchor": query_info.anchor,
        "found_anchor": query_info.found_anchor,
        "found_oldest": query_info.found_oldest,
        "found_newest": query_info.found_newest,
        "history_limited": query_info.history_limited,
    }


def _handle_get_messages(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = GetMessagesArguments.model_validate(arguments)
    # These two range limits mirror GET /messages; see get_messages_backend.
    if args.num_before + args.num_after > MAX_MESSAGES_PER_FETCH:
        raise JsonableError(
            _("Too many messages requested (maximum {max_messages}).").format(
                max_messages=MAX_MESSAGES_PER_FETCH,
            )
        )
    if args.num_before > 0 and args.num_after > 0 and not args.include_anchor:
        raise JsonableError(_("The anchor can only be excluded at an end of the range"))

    narrow = clean_narrow_for_message_fetch([*args.narrow], user_profile.realm, user_profile)
    return _fetch_messages(
        user_profile,
        narrow,
        # parse_anchor_value takes the anchor in the string form that
        # arrives over the REST API.
        parse_anchor_value(str(args.anchor), use_first_unread_anchor=False),
        args.include_anchor,
        args.num_before,
        args.num_after,
    )


def _handle_list_channels(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    ListChannelsArguments.model_validate(arguments)
    streams = do_get_streams(user_profile)
    return {
        "channels": [
            {
                "channel_id": stream["stream_id"],
                "name": stream["name"],
                "description": stream["description"],
                "is_private": stream["invite_only"],
                "is_web_public": stream["is_web_public"],
            }
            for stream in streams
        ]
    }


def _handle_list_topics(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = ListTopicsArguments.model_validate(arguments)
    (stream, _sub) = access_stream_by_name(user_profile, args.channel)
    assert stream.recipient_id is not None
    history = get_topic_history_for_stream(
        user_profile=user_profile,
        recipient_id=stream.recipient_id,
        public_history=stream.is_history_public_to_subscribers(),
        allow_empty_topic_name=False,
    )
    return {
        "topics": [{"name": topic["name"], "max_message_id": topic["max_id"]} for topic in history]
    }


def _handle_list_linkifiers(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    ListLinkifiersArguments.model_validate(arguments)
    return {
        "linkifiers": [
            {
                "pattern": linkifier["pattern"],
                "url_template": linkifier["url_template"],
            }
            for linkifier in linkifiers_for_realm(user_profile.realm_id)
        ]
    }


def _handle_get_users(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = GetUsersArguments.model_validate(arguments)
    user_query = UserProfile.objects.filter(realm=user_profile.realm, is_active=True)
    if not check_user_can_access_all_users(user_profile):
        # Bots stay visible to everyone, matching GET /users.
        accessible_ids = get_accessible_user_ids(user_profile.realm, user_profile)
        user_query = user_query.filter(Q(id__in=accessible_ids) | Q(is_bot=True))
    if args.query is not None:
        # Match only the email column, which is the address the user is
        # allowed to see under the realm's email visibility policy, never
        # delivery_email.
        user_query = user_query.filter(
            Q(full_name__icontains=args.query) | Q(email__icontains=args.query)
        )
    users = user_query.order_by("full_name", "id")[: args.limit]
    return {
        "users": [
            {
                "user_id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "is_bot": user.is_bot,
            }
            for user in users
        ]
    }


@dataclass
class MCPTool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[UserProfile, dict[str, Any]], dict[str, Any]]
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
        name="get_messages",
        description="Fetch messages matching a Zulip narrow -- the same filter language as"
        " the web app's search bar and the GET /messages API, including full-text search"
        " via the search operator. Returns a range around an anchor, so you can pull"
        " context around a specific message or page through a conversation.",
        arguments_model=GetMessagesArguments,
        handler=_handle_get_messages,
        read_only=True,
    ),
    MCPTool(
        name="list_channels",
        description="List the channels the user can see, with their descriptions.",
        arguments_model=ListChannelsArguments,
        handler=_handle_list_channels,
        read_only=True,
    ),
    MCPTool(
        name="list_topics",
        description="List recent topics in a channel, newest first.",
        arguments_model=ListTopicsArguments,
        handler=_handle_list_topics,
        read_only=True,
    ),
    MCPTool(
        name="list_linkifiers",
        description="List the organization's linkifiers, which turn patterns in message"
        " text into links. Message content is returned as Markdown, so use this to work"
        " out what a bare pattern like an issue number refers to.",
        arguments_model=ListLinkifiersArguments,
        handler=_handle_list_linkifiers,
        read_only=True,
    ),
    MCPTool(
        name="get_users",
        description="List users in the organization, optionally filtered by name or email.",
        arguments_model=GetUsersArguments,
        handler=_handle_get_users,
        read_only=True,
    ),
]

MCP_TOOLS_BY_NAME: dict[str, MCPTool] = {tool.name: tool for tool in MCP_TOOLS}


def get_mcp_tool_definitions() -> list[dict[str, Any]]:
    return [tool.to_definition() for tool in MCP_TOOLS]

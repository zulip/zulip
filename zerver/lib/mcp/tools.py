from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from django.db.models import Q
from django.utils.translation import gettext as _
from pydantic import BaseModel, ConfigDict, Field

from zerver.lib.exceptions import JsonableError
from zerver.lib.narrow import (
    NarrowParameter,
    fetch_plain_text_messages_for_narrow,
    parse_anchor_value,
)
from zerver.lib.streams import access_stream_by_name, do_get_streams
from zerver.lib.topic import TOPIC_NAME, get_topic_history_for_stream
from zerver.lib.users import (
    check_user_can_access_all_users,
    get_accessible_user_ids,
    get_users_for_api,
)
from zerver.models import UserProfile
from zerver.models.linkifiers import linkifiers_for_realm
from zerver.views.message_fetch import MAX_MESSAGES_PER_FETCH

MCP_CLIENT_NAME = "ZulipMCP"

# Matches the web app's batch size for a narrowed view. Message content
# has no length bound, so a caller reading long messages needs fewer.
DEFAULT_NUM_BEFORE = 100

# A channel or topic listing is small per entry but unbounded in a large
# organization: chat.zulip.org has channels with thousands of topics, and
# returning them all is far past what an MCP client accepts in one tool
# result. Callers that want more can raise the limit deliberately, using
# the total each result reports.
DEFAULT_LIST_LIMIT = 100


class NarrowTerm(NarrowParameter):
    # Unlike the REST API, we reject unknown keys, so that a misspelled
    # field in a narrow term fails loudly.
    model_config = ConfigDict(extra="forbid")


class GetMessagesArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrow: list[NarrowTerm] = Field(
        # Not default_factory, which would drop the default from the JSON
        # schema served as inputSchema. Pydantic copies it per instance.
        default=[],
        description='Filters combined with AND, in Zulip\'s narrow format: {"operator":'
        ' ..., "operand": ..., "negated": ...}. The operators are documented at'
        " https://zulip.com/api/get-messages#parameter-narrow and"
        " https://zulip.com/help/search-for-messages. An empty narrow returns the"
        " newest messages from the user's combined feed.",
    )
    anchor: int | Literal["newest", "oldest", "first_unread", "date"] = Field(
        default="newest",
        description='Message ID to read around, or "newest", "oldest",'
        ' "first_unread" (the user\'s first unread message in this narrow), or'
        ' "date" to read around anchor_date. To read forward from "oldest",'
        ' "first_unread", or a date, set num_after; num_before alone returns'
        " the messages preceding the anchor.",
    )
    anchor_date: str | None = Field(
        default=None,
        description='Where to start reading when anchor is "date": an ISO 8601 date'
        ' ("2025-04-18") or datetime ("2025-04-18T12:34:56Z"). A date alone means'
        " midnight, and a time without a zone is UTC. The anchor is the first"
        ' message at or after it. Ignored unless anchor is "date".',
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

    query: str | None = Field(
        default=None,
        description="Case-insensitive substring matched against channel names and descriptions.",
    )
    limit: int = Field(
        default=DEFAULT_LIST_LIMIT,
        ge=1,
        description="Maximum number of channels to return. The result reports how many"
        " matched in total and whether the returned list is complete, so raise this to"
        " fetch the rest, or filter with query when the total is large.",
    )


class ListLinkifiersArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListTopicsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = Field(description="Channel name to list recent topics for.")
    limit: int = Field(
        default=DEFAULT_LIST_LIMIT,
        ge=1,
        description="Maximum number of topics to return, newest first. The result reports"
        " how many the channel has in total and whether the returned list is complete, so"
        " raise this to fetch the rest.",
    )


class GetUsersArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(
        default=None,
        description="Case-insensitive substring matched against user names and email addresses.",
    )
    # Like GET /users, which returns all users, this has no upper bound.
    limit: int = Field(
        default=50,
        ge=1,
        description="Maximum number of users to return. The result reports how many"
        " matched in total and whether the returned list is complete, so raise this to"
        " fetch the rest, or filter with query when the total is large.",
    )


def _compact_user(user_id: int, full_name: str) -> dict[str, Any]:
    """Full names are not unique in Zulip, so results identify a person by
    user ID, which is also what narrows and message recipients take.
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

    messages, query_info = fetch_plain_text_messages_for_narrow(
        user_profile,
        [*args.narrow],
        # parse_anchor_value takes the string form the REST API receives.
        anchor_info=parse_anchor_value(
            str(args.anchor), use_first_unread_anchor=False, anchor_date=args.anchor_date
        ),
        include_anchor=args.include_anchor,
        num_before=args.num_before,
        num_after=args.num_after,
    )
    return {
        "messages": [_compact_message(message) for message in messages],
        "anchor": query_info.anchor,
        "found_anchor": query_info.found_anchor,
        "found_oldest": query_info.found_oldest,
        "found_newest": query_info.found_newest,
        "history_limited": query_info.history_limited,
    }


def _handle_list_channels(user_profile: UserProfile, arguments: dict[str, Any]) -> dict[str, Any]:
    args = ListChannelsArguments.model_validate(arguments)
    streams = do_get_streams(user_profile)
    if args.query is not None:
        query = args.query.casefold()
        streams = [
            stream
            for stream in streams
            if query in stream["name"].casefold() or query in stream["description"].casefold()
        ]
    return {
        "channels": [
            {
                "channel_id": stream["stream_id"],
                "name": stream["name"],
                "description": stream["description"],
                "is_private": stream["invite_only"],
                "is_web_public": stream["is_web_public"],
            }
            for stream in streams[: args.limit]
        ],
        "total_count": len(streams),
        "found_all": len(streams) <= args.limit,
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
        "topics": [
            {"name": topic["name"], "max_message_id": topic["max_id"]}
            for topic in history[: args.limit]
        ],
        "total_count": len(history),
        "found_all": len(history) <= args.limit,
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
    realm = user_profile.realm
    user_query = UserProfile.objects.filter(realm=realm, is_active=True)
    if not check_user_can_access_all_users(user_profile):
        # get_users_for_api below applies this same policy, and is what
        # decides who is returned. Repeating it here is what makes the
        # limit count users the caller can actually see, rather than
        # spending it on users that would then be dropped. Bots stay
        # visible to everyone, matching GET /users.
        accessible_ids = get_accessible_user_ids(realm, user_profile)
        user_query = user_query.filter(Q(id__in=accessible_ids) | Q(is_bot=True))
    if args.query is not None:
        # email is the address visible under the realm's email address
        # visibility policy; delivery_email is never searched.
        user_query = user_query.filter(
            Q(full_name__icontains=args.query) | Q(email__icontains=args.query)
        )
    # The IDs are counted in Python rather than limited in SQL so that the
    # result can report how many users matched. An agent that sees only a
    # truncated list reads it as the whole organization and concludes
    # someone is not in it; one that is told the total can choose between
    # raising the limit and narrowing the query.
    matching_user_ids = list(user_query.order_by("full_name", "id").values_list("id", flat=True))
    user_ids = matching_user_ids[: args.limit]
    # Going through get_users_for_api keeps this tool on the same code
    # path as GET /users, so that it cannot expose a user, or a field of
    # a user, that the REST API would withhold. Custom profile fields
    # are not requested, both because none are returned and to skip
    # fetching their values.
    rows = get_users_for_api(
        realm,
        user_profile,
        user_ids=user_ids,
        client_gravatar=True,
        user_avatar_url_field_optional=True,
        include_custom_profile_fields=False,
    )
    return {
        "users": [
            {
                "user_id": row["user_id"],
                "full_name": row["full_name"],
                "email": row["email"],
                "is_bot": row["is_bot"],
            }
            # rows is keyed by user ID, so iterating user_ids is what
            # preserves the query's ordering. get_users_for_api applies a
            # superset of the filter above, so it should return every ID
            # passed to it; omitting rather than raising keeps a
            # disagreement from becoming a 500.
            for user_id in user_ids
            if (row := rows.get(user_id)) is not None
        ],
        "total_count": len(matching_user_ids),
        "found_all": len(matching_user_ids) <= args.limit,
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
        description="List the channels the user can see, with their descriptions,"
        " optionally filtered by name or description. Reports how many matched in"
        " total and whether the returned list is complete.",
        arguments_model=ListChannelsArguments,
        handler=_handle_list_channels,
        read_only=True,
    ),
    MCPTool(
        name="list_topics",
        description="List recent topics in a channel, newest first. Reports how many"
        " topics the channel has in total and whether the returned list is complete.",
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
        description="List users in the organization, optionally filtered by name or"
        " email. Reports how many matched in total and whether the returned list is"
        " complete.",
        arguments_model=GetUsersArguments,
        handler=_handle_get_users,
        read_only=True,
    ),
]

MCP_TOOLS_BY_NAME: dict[str, MCPTool] = {tool.name: tool for tool in MCP_TOOLS}


def get_mcp_tool_definitions() -> list[dict[str, Any]]:
    return [tool.to_definition() for tool in MCP_TOOLS]

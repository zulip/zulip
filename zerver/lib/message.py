import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    Union,
)

from django.conf import settings
from django.db import connection
from django.db.models import Exists, Max, OuterRef, QuerySet, Sum
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django_stubs_ext import ValuesQuerySet
from psycopg2.sql import SQL

from analytics.lib.counts import COUNT_STATS
from analytics.models import RealmCount
from zerver.lib.cache import generic_bulk_cached_fetch, to_dict_cache_key_id
from zerver.lib.display_recipient import get_display_recipient_by_id
from zerver.lib.exceptions import JsonableError, MissingAuthenticationError
from zerver.lib.markdown import MessageRenderingResult
from zerver.lib.mention import MentionData
from zerver.lib.message_cache import MessageDict, extract_message_dict, stringify_message_dict
from zerver.lib.partial import partial
from zerver.lib.request import RequestVariableConversionError
from zerver.lib.stream_subscription import (
    get_stream_subscriptions_for_user,
    get_subscribed_stream_recipient_ids_for_user,
    num_subscribers_for_stream_id,
)
from zerver.lib.streams import can_access_stream_history, get_web_public_streams_queryset
from zerver.lib.topic import MESSAGE__TOPIC, TOPIC_NAME, messages_for_topic
from zerver.lib.types import UserDisplayRecipient
from zerver.lib.user_groups import is_user_in_group
from zerver.lib.user_topics import build_get_topic_visibility_policy, get_topic_visibility_policy
from zerver.lib.users import get_inaccessible_user_ids
from zerver.models import (
    Message,
    NamedUserGroup,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
    UserTopic,
)
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.groups import SystemGroups
from zerver.models.messages import get_usermessage_by_message_id
from zerver.models.users import is_cross_realm_bot_email


class MessageDetailsDict(TypedDict, total=False):
    type: str
    mentioned: bool
    user_ids: List[int]
    stream_id: int
    topic: str
    unmuted_stream_msg: bool


class RawUnreadStreamDict(TypedDict):
    stream_id: int
    topic: str


class RawUnreadDirectMessageDict(TypedDict):
    other_user_id: int


class RawUnreadHuddleDict(TypedDict):
    user_ids_string: str


class RawUnreadMessagesResult(TypedDict):
    pm_dict: Dict[int, RawUnreadDirectMessageDict]
    stream_dict: Dict[int, RawUnreadStreamDict]
    huddle_dict: Dict[int, RawUnreadHuddleDict]
    mentions: Set[int]
    muted_stream_ids: Set[int]
    unmuted_stream_msgs: Set[int]
    old_unreads_missing: bool


class UnreadStreamInfo(TypedDict):
    stream_id: int
    topic: str
    unread_message_ids: List[int]


class UnreadDirectMessageInfo(TypedDict):
    other_user_id: int
    # Deprecated and misleading synonym for other_user_id
    sender_id: int
    unread_message_ids: List[int]


class UnreadHuddleInfo(TypedDict):
    user_ids_string: str
    unread_message_ids: List[int]


class UnreadMessagesResult(TypedDict):
    pms: List[UnreadDirectMessageInfo]
    streams: List[UnreadStreamInfo]
    huddles: List[UnreadHuddleInfo]
    mentions: List[int]
    count: int
    old_unreads_missing: bool


@dataclass
class SendMessageRequest:
    message: Message
    rendering_result: MessageRenderingResult
    stream: Optional[Stream]
    sender_muted_stream: Optional[bool]
    local_id: Optional[str]
    sender_queue_id: Optional[str]
    realm: Realm
    mention_data: MentionData
    mentioned_user_groups_map: Dict[int, int]
    active_user_ids: Set[int]
    online_push_user_ids: Set[int]
    dm_mention_push_disabled_user_ids: Set[int]
    dm_mention_email_disabled_user_ids: Set[int]
    stream_push_user_ids: Set[int]
    stream_email_user_ids: Set[int]
    # IDs of users who have followed the topic the message is being sent to,
    # and have the followed topic push notifications setting ON.
    followed_topic_push_user_ids: Set[int]
    # IDs of users who have followed the topic the message is being sent to,
    # and have the followed topic email notifications setting ON.
    followed_topic_email_user_ids: Set[int]
    muted_sender_user_ids: Set[int]
    um_eligible_user_ids: Set[int]
    long_term_idle_user_ids: Set[int]
    default_bot_user_ids: Set[int]
    service_bot_tuples: List[Tuple[int, int]]
    all_bot_user_ids: Set[int]
    # IDs of topic participants who should be notified of topic wildcard mention.
    # The 'user_allows_notifications_in_StreamTopic' with 'wildcard_mentions_notify'
    # setting ON should return True.
    # A user_id can exist in either or both of the 'topic_wildcard_mention_user_ids'
    # and 'topic_wildcard_mention_in_followed_topic_user_ids' sets.
    topic_wildcard_mention_user_ids: Set[int]
    # IDs of users subscribed to the stream who should be notified of
    # stream wildcard mention.
    # The 'user_allows_notifications_in_StreamTopic' with 'wildcard_mentions_notify'
    # setting ON should return True.
    # A user_id can exist in either or both of the 'stream_wildcard_mention_user_ids'
    # and 'stream_wildcard_mention_in_followed_topic_user_ids' sets.
    stream_wildcard_mention_user_ids: Set[int]
    # IDs of topic participants who have followed the topic the message
    # (having topic wildcard) is being sent to, and have the
    # 'followed_topic_wildcard_mentions_notify' setting ON.
    topic_wildcard_mention_in_followed_topic_user_ids: Set[int]
    # IDs of users who have followed the topic the message
    # (having stream wildcard) is being sent to, and have the
    # 'followed_topic_wildcard_mentions_notify' setting ON.
    stream_wildcard_mention_in_followed_topic_user_ids: Set[int]
    # A topic participant is anyone who either sent or reacted to messages in the topic.
    topic_participant_user_ids: Set[int]
    links_for_embed: Set[str]
    widget_content: Optional[Dict[str, Any]]
    submessages: List[Dict[str, Any]] = field(default_factory=list)
    deliver_at: Optional[datetime] = None
    delivery_type: Optional[str] = None
    limit_unread_user_ids: Optional[Set[int]] = None
    service_queue_events: Optional[Dict[str, List[Dict[str, Any]]]] = None
    disable_external_notifications: bool = False
    automatic_new_visibility_policy: Optional[int] = None
    recipients_for_user_creation_events: Optional[Dict[UserProfile, Set[int]]] = None


# We won't try to fetch more unread message IDs from the database than
# this limit.  The limit is super high, in large part because it means
# client-side code mostly doesn't need to think about the case that a
# user has more older unread messages that were cut off.
MAX_UNREAD_MESSAGES = 50000


def truncate_content(content: str, max_length: int, truncation_message: str) -> str:
    if len(content) > max_length:
        content = content[: max_length - len(truncation_message)] + truncation_message
    return content


def normalize_body(body: str) -> str:
    body = body.rstrip().lstrip("\n")
    if len(body) == 0:
        raise JsonableError(_("Message must not be empty"))
    if "\x00" in body:
        raise JsonableError(_("Message must not contain null bytes"))
    return truncate_content(body, settings.MAX_MESSAGE_LENGTH, "\n[message truncated]")


def truncate_topic(topic_name: str) -> str:
    return truncate_content(topic_name, MAX_TOPIC_NAME_LENGTH, "...")


def messages_for_ids(
    message_ids: List[int],
    user_message_flags: Dict[int, List[str]],
    search_fields: Dict[int, Dict[str, str]],
    apply_markdown: bool,
    client_gravatar: bool,
    allow_edit_history: bool,
    user_profile: Optional[UserProfile],
    realm: Realm,
) -> List[Dict[str, Any]]:
    id_fetcher = lambda row: row["id"]

    message_dicts = generic_bulk_cached_fetch(
        to_dict_cache_key_id,
        MessageDict.ids_to_dict,
        message_ids,
        id_fetcher=id_fetcher,
        cache_transformer=lambda obj: obj,
        extractor=extract_message_dict,
        setter=stringify_message_dict,
    )

    message_list: List[Dict[str, Any]] = []

    sender_ids = [message_dicts[message_id]["sender_id"] for message_id in message_ids]
    inaccessible_sender_ids = get_inaccessible_user_ids(sender_ids, user_profile)

    for message_id in message_ids:
        msg_dict = message_dicts[message_id]
        flags = user_message_flags[message_id]
        # TODO/compatibility: The `wildcard_mentioned` flag was deprecated in favor of
        # the `stream_wildcard_mentioned` and `topic_wildcard_mentioned` flags.  The
        # `wildcard_mentioned` flag exists for backwards-compatibility with older
        # clients.  Remove this when we no longer support legacy clients that have not
        # been updated to access `stream_wildcard_mentioned`.
        if "stream_wildcard_mentioned" in flags or "topic_wildcard_mentioned" in flags:
            flags.append("wildcard_mentioned")
        msg_dict.update(flags=flags)
        if message_id in search_fields:
            msg_dict.update(search_fields[message_id])
        # Make sure that we never send message edit history to clients
        # in realms with allow_edit_history disabled.
        if "edit_history" in msg_dict and not allow_edit_history:
            del msg_dict["edit_history"]
        msg_dict["can_access_sender"] = msg_dict["sender_id"] not in inaccessible_sender_ids
        message_list.append(msg_dict)

    MessageDict.post_process_dicts(message_list, apply_markdown, client_gravatar, realm)

    return message_list


def access_message(
    user_profile: UserProfile,
    message_id: int,
    lock_message: bool = False,
) -> Message:
    """You can access a message by ID in our APIs that either:
    (1) You received or have previously accessed via starring
        (aka have a UserMessage row for).
    (2) Was sent to a public stream in your realm.

    We produce consistent, boring error messages to avoid leaking any
    information from a security perspective.

    The lock_message parameter should be passed by callers that are
    planning to modify the Message object. This will use the SQL
    `SELECT FOR UPDATE` feature to ensure that other processes cannot
    delete the message during the current transaction, which is
    important to prevent rare race conditions. Callers must only
    pass lock_message when inside a @transaction.atomic block.
    """
    try:
        base_query = Message.objects.select_related(*Message.DEFAULT_SELECT_RELATED)
        if lock_message:
            # We want to lock only the `Message` row, and not the related fields
            # because the `Message` row only has a possibility of races.
            base_query = base_query.select_for_update(of=("self",))
        message = base_query.get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError(_("Invalid message(s)"))

    has_user_message = lambda: UserMessage.objects.filter(
        user_profile=user_profile, message_id=message_id
    ).exists()

    if has_message_access(user_profile, message, has_user_message=has_user_message):
        return message
    raise JsonableError(_("Invalid message(s)"))


def access_message_and_usermessage(
    user_profile: UserProfile,
    message_id: int,
    lock_message: bool = False,
) -> Tuple[Message, Optional[UserMessage]]:
    """As access_message, but also returns the usermessage, if any."""
    try:
        base_query = Message.objects.select_related(*Message.DEFAULT_SELECT_RELATED)
        if lock_message:
            # We want to lock only the `Message` row, and not the related fields
            # because the `Message` row only has a possibility of races.
            base_query = base_query.select_for_update(of=("self",))
        message = base_query.get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError(_("Invalid message(s)"))

    user_message = get_usermessage_by_message_id(user_profile, message_id)
    has_user_message = lambda: user_message is not None

    if has_message_access(user_profile, message, has_user_message=has_user_message):
        return (message, user_message)
    raise JsonableError(_("Invalid message(s)"))


def access_web_public_message(
    realm: Realm,
    message_id: int,
) -> Message:
    """Access control method for unauthenticated requests interacting
    with a message in web-public streams.
    """

    # We throw a MissingAuthenticationError for all errors in this
    # code path, to avoid potentially leaking information on whether a
    # message with the provided ID exists on the server if the client
    # shouldn't have access to it.
    if not realm.web_public_streams_enabled():
        raise MissingAuthenticationError

    try:
        message = Message.objects.select_related(*Message.DEFAULT_SELECT_RELATED).get(id=message_id)
    except Message.DoesNotExist:
        raise MissingAuthenticationError

    if not message.is_stream_message():
        raise MissingAuthenticationError

    queryset = get_web_public_streams_queryset(realm)
    try:
        stream = queryset.get(id=message.recipient.type_id)
    except Stream.DoesNotExist:
        raise MissingAuthenticationError

    # These should all have been enforced by the code in
    # get_web_public_streams_queryset
    assert stream.is_web_public
    assert not stream.deactivated
    assert not stream.invite_only
    assert stream.history_public_to_subscribers

    # Now that we've confirmed this message was sent to the target
    # web-public stream, we can return it as having been successfully
    # accessed.
    return message


def has_message_access(
    user_profile: UserProfile,
    message: Message,
    *,
    has_user_message: Callable[[], bool],
    stream: Optional[Stream] = None,
    is_subscribed: Optional[bool] = None,
) -> bool:
    """
    Returns whether a user has access to a given message.

    * The user_message parameter must be provided if the user has a UserMessage
      row for the target message.
    * The optional stream parameter is validated; is_subscribed is not.
    """

    if message.recipient.type != Recipient.STREAM:
        # You can only access direct messages you received
        return has_user_message()

    if stream is None:
        stream = Stream.objects.get(id=message.recipient.type_id)
    else:
        assert stream.recipient_id == message.recipient_id

    if stream.realm_id != user_profile.realm_id:
        # You can't access public stream messages in other realms
        return False

    def is_subscribed_helper() -> bool:
        if is_subscribed is not None:
            return is_subscribed

        return Subscription.objects.filter(
            user_profile=user_profile, active=True, recipient=message.recipient
        ).exists()

    if stream.is_public() and user_profile.can_access_public_streams():
        return True

    if not stream.is_history_public_to_subscribers():
        # Unless history is public to subscribers, you need to both:
        # (1) Have directly received the message.
        # AND
        # (2) Be subscribed to the stream.
        return has_user_message() and is_subscribed_helper()

    # is_history_public_to_subscribers, so check if you're subscribed
    return is_subscribed_helper()


def bulk_access_messages(
    user_profile: UserProfile,
    messages: Collection[Message] | QuerySet[Message],
    *,
    stream: Optional[Stream] = None,
) -> List[Message]:
    """This function does the full has_message_access check for each
    message.  If stream is provided, it is used to avoid unnecessary
    database queries, and will use exactly 2 bulk queries instead.

    Throws AssertionError if stream is passed and any of the messages
    were not sent to that stream.

    """
    filtered_messages = []

    user_message_set = set(
        get_messages_with_usermessage_rows_for_user(
            user_profile.id, [message.id for message in messages]
        )
    )

    if stream is None:
        streams = {
            stream.recipient_id: stream
            for stream in Stream.objects.filter(
                id__in={
                    message.recipient.type_id
                    for message in messages
                    if message.recipient.type == Recipient.STREAM
                }
            )
        }

    subscribed_recipient_ids = set(get_subscribed_stream_recipient_ids_for_user(user_profile))

    for message in messages:
        is_subscribed = message.recipient_id in subscribed_recipient_ids
        if has_message_access(
            user_profile,
            message,
            has_user_message=partial(lambda m: m.id in user_message_set, message),
            stream=streams.get(message.recipient_id) if stream is None else stream,
            is_subscribed=is_subscribed,
        ):
            filtered_messages.append(message)
    return filtered_messages


def bulk_access_stream_messages_query(
    user_profile: UserProfile, messages: QuerySet[Message], stream: Stream
) -> QuerySet[Message]:
    """This function mirrors bulk_access_messages, above, but applies the
    limits to a QuerySet and returns a new QuerySet which only
    contains messages in the given stream which the user can access.
    Note that this only works with streams.  It may return an empty
    QuerySet if the user has access to no messages (for instance, for
    a private stream which the user is not subscribed to).

    """

    messages = messages.filter(realm_id=user_profile.realm_id, recipient_id=stream.recipient_id)

    if stream.is_public() and user_profile.can_access_public_streams():
        return messages

    if not Subscription.objects.filter(
        user_profile=user_profile, active=True, recipient=stream.recipient
    ).exists():
        return Message.objects.none()
    if not stream.is_history_public_to_subscribers():
        messages = messages.annotate(
            has_usermessage=Exists(
                UserMessage.objects.filter(
                    user_profile_id=user_profile.id, message_id=OuterRef("id")
                )
            )
        ).filter(has_usermessage=1)
    return messages


def get_messages_with_usermessage_rows_for_user(
    user_profile_id: int, message_ids: Sequence[int]
) -> ValuesQuerySet[UserMessage, int]:
    """
    Returns a subset of `message_ids` containing only messages the
    user has a UserMessage for.  Makes O(1) database queries.
    Note that this is not sufficient for access verification for
    stream messages.

    See `access_message`, `bulk_access_messages` for proper message access
    checks that follow our security model.
    """
    return UserMessage.objects.filter(
        user_profile_id=user_profile_id,
        message_id__in=message_ids,
    ).values_list("message_id", flat=True)


def huddle_users(recipient_id: int) -> str:
    display_recipient: List[UserDisplayRecipient] = get_display_recipient_by_id(
        recipient_id,
        Recipient.DIRECT_MESSAGE_GROUP,
        None,
    )

    user_ids: List[int] = [obj["id"] for obj in display_recipient]
    user_ids = sorted(user_ids)
    return ",".join(str(uid) for uid in user_ids)


def get_inactive_recipient_ids(user_profile: UserProfile) -> List[int]:
    rows = (
        get_stream_subscriptions_for_user(user_profile)
        .filter(
            active=False,
        )
        .values(
            "recipient_id",
        )
    )
    inactive_recipient_ids = [row["recipient_id"] for row in rows]
    return inactive_recipient_ids


def get_muted_stream_ids(user_profile: UserProfile) -> Set[int]:
    rows = (
        get_stream_subscriptions_for_user(user_profile)
        .filter(
            active=True,
            is_muted=True,
        )
        .values(
            "recipient__type_id",
        )
    )
    muted_stream_ids = {row["recipient__type_id"] for row in rows}
    return muted_stream_ids


def get_starred_message_ids(user_profile: UserProfile) -> List[int]:
    return list(
        UserMessage.objects.filter(
            user_profile=user_profile,
        )
        .extra(
            where=[UserMessage.where_starred()],
        )
        .order_by(
            "message_id",
        )
        .values_list("message_id", flat=True)[0:10000]
    )


def get_raw_unread_data(
    user_profile: UserProfile, message_ids: Optional[List[int]] = None
) -> RawUnreadMessagesResult:
    excluded_recipient_ids = get_inactive_recipient_ids(user_profile)

    user_msgs = (
        UserMessage.objects.filter(
            user_profile=user_profile,
        )
        .exclude(
            message__recipient_id__in=excluded_recipient_ids,
        )
        .values(
            "message_id",
            "message__sender_id",
            MESSAGE__TOPIC,
            "message__recipient_id",
            "message__recipient__type",
            "message__recipient__type_id",
            "flags",
        )
        .order_by("-message_id")
    )

    if message_ids is not None:
        # When users are marking just a few messages as unread, we just need
        # those ids, and we know they're unread.
        user_msgs = user_msgs.filter(message_id__in=message_ids)
    else:
        # At page load we need all unread messages.
        user_msgs = user_msgs.extra(
            where=[UserMessage.where_unread()],
        )

    # Limit unread messages for performance reasons.
    user_msgs = list(user_msgs[:MAX_UNREAD_MESSAGES])

    rows = list(reversed(user_msgs))
    return extract_unread_data_from_um_rows(rows, user_profile)


def extract_unread_data_from_um_rows(
    rows: List[Dict[str, Any]], user_profile: Optional[UserProfile]
) -> RawUnreadMessagesResult:
    pm_dict: Dict[int, RawUnreadDirectMessageDict] = {}
    stream_dict: Dict[int, RawUnreadStreamDict] = {}
    muted_stream_ids: Set[int] = set()
    unmuted_stream_msgs: Set[int] = set()
    huddle_dict: Dict[int, RawUnreadHuddleDict] = {}
    mentions: Set[int] = set()
    total_unreads = 0

    raw_unread_messages: RawUnreadMessagesResult = dict(
        pm_dict=pm_dict,
        stream_dict=stream_dict,
        muted_stream_ids=muted_stream_ids,
        unmuted_stream_msgs=unmuted_stream_msgs,
        huddle_dict=huddle_dict,
        mentions=mentions,
        old_unreads_missing=False,
    )

    if user_profile is None:
        return raw_unread_messages

    muted_stream_ids = get_muted_stream_ids(user_profile)
    raw_unread_messages["muted_stream_ids"] = muted_stream_ids

    get_topic_visibility_policy = build_get_topic_visibility_policy(user_profile)

    def is_row_muted(stream_id: int, recipient_id: int, topic_name: str) -> bool:
        stream_muted = stream_id in muted_stream_ids
        visibility_policy = get_topic_visibility_policy(recipient_id, topic_name)

        if stream_muted and visibility_policy in [
            UserTopic.VisibilityPolicy.UNMUTED,
            UserTopic.VisibilityPolicy.FOLLOWED,
        ]:
            return False

        if stream_muted:
            return True

        # muted topic in unmuted stream
        if visibility_policy == UserTopic.VisibilityPolicy.MUTED:
            return True

        # Messages sent by muted users are never unread, so we don't
        # need any logic related to muted users here.

        return False

    huddle_cache: Dict[int, str] = {}

    def get_huddle_users(recipient_id: int) -> str:
        if recipient_id in huddle_cache:
            return huddle_cache[recipient_id]

        user_ids_string = huddle_users(recipient_id)
        huddle_cache[recipient_id] = user_ids_string
        return user_ids_string

    for row in rows:
        total_unreads += 1
        message_id = row["message_id"]
        msg_type = row["message__recipient__type"]
        recipient_id = row["message__recipient_id"]
        sender_id = row["message__sender_id"]

        if msg_type == Recipient.STREAM:
            stream_id = row["message__recipient__type_id"]
            topic_name = row[MESSAGE__TOPIC]
            stream_dict[message_id] = dict(
                stream_id=stream_id,
                topic=topic_name,
            )
            if not is_row_muted(stream_id, recipient_id, topic_name):
                unmuted_stream_msgs.add(message_id)

        elif msg_type == Recipient.PERSONAL:
            if sender_id == user_profile.id:
                other_user_id = row["message__recipient__type_id"]
            else:
                other_user_id = sender_id

            pm_dict[message_id] = dict(
                other_user_id=other_user_id,
            )

        elif msg_type == Recipient.DIRECT_MESSAGE_GROUP:
            user_ids_string = get_huddle_users(recipient_id)
            huddle_dict[message_id] = dict(
                user_ids_string=user_ids_string,
            )

        # TODO: Add support for alert words here as well.
        is_mentioned = (row["flags"] & UserMessage.flags.mentioned) != 0
        is_stream_wildcard_mentioned = (
            row["flags"] & UserMessage.flags.stream_wildcard_mentioned
        ) != 0
        is_topic_wildcard_mentioned = (
            row["flags"] & UserMessage.flags.topic_wildcard_mentioned
        ) != 0
        if is_mentioned:
            mentions.add(message_id)
        if is_stream_wildcard_mentioned or is_topic_wildcard_mentioned:
            if msg_type == Recipient.STREAM:
                stream_id = row["message__recipient__type_id"]
                topic_name = row[MESSAGE__TOPIC]
                if not is_row_muted(stream_id, recipient_id, topic_name):
                    mentions.add(message_id)
            else:  # nocoverage # TODO: Test wildcard mentions in direct messages.
                mentions.add(message_id)

    # Record whether the user had more than MAX_UNREAD_MESSAGES total
    # unreads -- that's a state where Zulip's behavior will start to
    # be erroneous, and clients should display a warning.
    raw_unread_messages["old_unreads_missing"] = total_unreads == MAX_UNREAD_MESSAGES

    return raw_unread_messages


def aggregate_streams(*, input_dict: Dict[int, RawUnreadStreamDict]) -> List[UnreadStreamInfo]:
    lookup_dict: Dict[Tuple[int, str], UnreadStreamInfo] = {}
    for message_id, attribute_dict in input_dict.items():
        stream_id = attribute_dict["stream_id"]
        topic_name = attribute_dict["topic"]
        lookup_key = (stream_id, topic_name)
        if lookup_key not in lookup_dict:
            obj = UnreadStreamInfo(
                stream_id=stream_id,
                topic=topic_name,
                unread_message_ids=[],
            )
            lookup_dict[lookup_key] = obj

        bucket = lookup_dict[lookup_key]
        bucket["unread_message_ids"].append(message_id)

    for dct in lookup_dict.values():
        dct["unread_message_ids"].sort()

    sorted_keys = sorted(lookup_dict.keys())

    return [lookup_dict[k] for k in sorted_keys]


def aggregate_pms(
    *, input_dict: Dict[int, RawUnreadDirectMessageDict]
) -> List[UnreadDirectMessageInfo]:
    lookup_dict: Dict[int, UnreadDirectMessageInfo] = {}
    for message_id, attribute_dict in input_dict.items():
        other_user_id = attribute_dict["other_user_id"]
        if other_user_id not in lookup_dict:
            # The `sender_id` field here is only supported for
            # legacy mobile clients. Its actual semantics are the same
            # as `other_user_id`.
            obj = UnreadDirectMessageInfo(
                other_user_id=other_user_id,
                sender_id=other_user_id,
                unread_message_ids=[],
            )
            lookup_dict[other_user_id] = obj

        bucket = lookup_dict[other_user_id]
        bucket["unread_message_ids"].append(message_id)

    for dct in lookup_dict.values():
        dct["unread_message_ids"].sort()

    sorted_keys = sorted(lookup_dict.keys())

    return [lookup_dict[k] for k in sorted_keys]


def aggregate_huddles(*, input_dict: Dict[int, RawUnreadHuddleDict]) -> List[UnreadHuddleInfo]:
    lookup_dict: Dict[str, UnreadHuddleInfo] = {}
    for message_id, attribute_dict in input_dict.items():
        user_ids_string = attribute_dict["user_ids_string"]
        if user_ids_string not in lookup_dict:
            obj = UnreadHuddleInfo(
                user_ids_string=user_ids_string,
                unread_message_ids=[],
            )
            lookup_dict[user_ids_string] = obj

        bucket = lookup_dict[user_ids_string]
        bucket["unread_message_ids"].append(message_id)

    for dct in lookup_dict.values():
        dct["unread_message_ids"].sort()

    sorted_keys = sorted(lookup_dict.keys())

    return [lookup_dict[k] for k in sorted_keys]


def aggregate_unread_data(raw_data: RawUnreadMessagesResult) -> UnreadMessagesResult:
    pm_dict = raw_data["pm_dict"]
    stream_dict = raw_data["stream_dict"]
    unmuted_stream_msgs = raw_data["unmuted_stream_msgs"]
    huddle_dict = raw_data["huddle_dict"]
    mentions = list(raw_data["mentions"])

    count = len(pm_dict) + len(unmuted_stream_msgs) + len(huddle_dict)

    pm_objects = aggregate_pms(input_dict=pm_dict)
    stream_objects = aggregate_streams(input_dict=stream_dict)
    huddle_objects = aggregate_huddles(input_dict=huddle_dict)

    result: UnreadMessagesResult = dict(
        pms=pm_objects,
        streams=stream_objects,
        huddles=huddle_objects,
        mentions=mentions,
        count=count,
        old_unreads_missing=raw_data["old_unreads_missing"],
    )

    return result


def apply_unread_message_event(
    user_profile: UserProfile,
    state: RawUnreadMessagesResult,
    message: Dict[str, Any],
    flags: List[str],
) -> None:
    message_id = message["id"]
    if message["type"] == "stream":
        recipient_type = "stream"
    elif message["type"] == "private":
        others = [recip for recip in message["display_recipient"] if recip["id"] != user_profile.id]
        if len(others) <= 1:
            recipient_type = "private"
        else:
            recipient_type = "huddle"
    else:
        raise AssertionError("Invalid message type {}".format(message["type"]))

    if recipient_type == "stream":
        stream_id = message["stream_id"]
        topic_name = message[TOPIC_NAME]
        state["stream_dict"][message_id] = RawUnreadStreamDict(
            stream_id=stream_id,
            topic=topic_name,
        )

        stream_muted = stream_id in state["muted_stream_ids"]
        visibility_policy = get_topic_visibility_policy(user_profile, stream_id, topic_name)
        # A stream message is unmuted if it belongs to:
        # * a not muted topic in a normal stream
        # * an unmuted or followed topic in a muted stream
        if (not stream_muted and visibility_policy != UserTopic.VisibilityPolicy.MUTED) or (
            stream_muted
            and visibility_policy
            in [UserTopic.VisibilityPolicy.UNMUTED, UserTopic.VisibilityPolicy.FOLLOWED]
        ):
            state["unmuted_stream_msgs"].add(message_id)

    elif recipient_type == "private":
        if len(others) == 1:
            other_user_id = others[0]["id"]
        else:
            other_user_id = user_profile.id

        state["pm_dict"][message_id] = RawUnreadDirectMessageDict(
            other_user_id=other_user_id,
        )

    else:
        display_recipient = message["display_recipient"]
        user_ids = [obj["id"] for obj in display_recipient]
        user_ids = sorted(user_ids)
        user_ids_string = ",".join(str(uid) for uid in user_ids)

        state["huddle_dict"][message_id] = RawUnreadHuddleDict(
            user_ids_string=user_ids_string,
        )

    if "mentioned" in flags:
        state["mentions"].add(message_id)
    if (
        "stream_wildcard_mentioned" in flags or "topic_wildcard_mentioned" in flags
    ) and message_id in state["unmuted_stream_msgs"]:
        state["mentions"].add(message_id)


def remove_message_id_from_unread_mgs(state: RawUnreadMessagesResult, message_id: int) -> None:
    # The opposite of apply_unread_message_event; removes a read or
    # deleted message from a raw_unread_msgs data structure.
    state["pm_dict"].pop(message_id, None)
    state["stream_dict"].pop(message_id, None)
    state["huddle_dict"].pop(message_id, None)
    state["unmuted_stream_msgs"].discard(message_id)
    state["mentions"].discard(message_id)


def format_unread_message_details(
    my_user_id: int,
    raw_unread_data: RawUnreadMessagesResult,
) -> Dict[str, MessageDetailsDict]:
    unread_data = {}

    for message_id, private_message_details in raw_unread_data["pm_dict"].items():
        other_user_id = private_message_details["other_user_id"]
        if other_user_id == my_user_id:
            user_ids = []
        else:
            user_ids = [other_user_id]

        # Note that user_ids excludes ourself, even for the case we send messages
        # to ourself.
        message_details = MessageDetailsDict(
            type="private",
            user_ids=user_ids,
        )
        if message_id in raw_unread_data["mentions"]:
            message_details["mentioned"] = True
        unread_data[str(message_id)] = message_details

    for message_id, stream_message_details in raw_unread_data["stream_dict"].items():
        unmuted_stream_msg = message_id in raw_unread_data["unmuted_stream_msgs"]

        message_details = MessageDetailsDict(
            type="stream",
            stream_id=stream_message_details["stream_id"],
            topic=stream_message_details["topic"],
            # Clients don't need this detail, but we need it internally for apply_events.
            unmuted_stream_msg=unmuted_stream_msg,
        )
        if message_id in raw_unread_data["mentions"]:
            message_details["mentioned"] = True
        unread_data[str(message_id)] = message_details

    for message_id, huddle_message_details in raw_unread_data["huddle_dict"].items():
        # The client wants a list of user_ids in the conversation, excluding ourself,
        # that is sorted in numerical order.
        user_ids = sorted(
            user_id
            for s in huddle_message_details["user_ids_string"].split(",")
            if (user_id := int(s)) != my_user_id
        )
        message_details = MessageDetailsDict(
            type="private",
            user_ids=user_ids,
        )
        if message_id in raw_unread_data["mentions"]:
            message_details["mentioned"] = True
        unread_data[str(message_id)] = message_details

    return unread_data


def add_message_to_unread_msgs(
    my_user_id: int,
    state: RawUnreadMessagesResult,
    message_id: int,
    message_details: MessageDetailsDict,
) -> None:
    if message_details.get("mentioned"):
        state["mentions"].add(message_id)

    if message_details["type"] == "private":
        user_ids: List[int] = message_details["user_ids"]
        user_ids = [user_id for user_id in user_ids if user_id != my_user_id]
        if user_ids == []:
            state["pm_dict"][message_id] = RawUnreadDirectMessageDict(
                other_user_id=my_user_id,
            )
        elif len(user_ids) == 1:
            state["pm_dict"][message_id] = RawUnreadDirectMessageDict(
                other_user_id=user_ids[0],
            )
        else:
            user_ids.append(my_user_id)
            user_ids_string = ",".join(str(user_id) for user_id in sorted(user_ids))
            state["huddle_dict"][message_id] = RawUnreadHuddleDict(
                user_ids_string=user_ids_string,
            )
    elif message_details["type"] == "stream":
        state["stream_dict"][message_id] = RawUnreadStreamDict(
            stream_id=message_details["stream_id"],
            topic=message_details["topic"],
        )
        if message_details["unmuted_stream_msg"]:
            state["unmuted_stream_msgs"].add(message_id)


def estimate_recent_messages(realm: Realm, hours: int) -> int:
    stat = COUNT_STATS["messages_sent:is_bot:hour"]
    d = timezone_now() - timedelta(hours=hours)
    return (
        RealmCount.objects.filter(property=stat.property, end_time__gt=d, realm=realm).aggregate(
            Sum("value")
        )["value__sum"]
        or 0
    )


def get_first_visible_message_id(realm: Realm) -> int:
    return realm.first_visible_message_id


def maybe_update_first_visible_message_id(realm: Realm, lookback_hours: int) -> None:
    recent_messages_count = estimate_recent_messages(realm, lookback_hours)
    if realm.message_visibility_limit is not None and recent_messages_count > 0:
        update_first_visible_message_id(realm)


def update_first_visible_message_id(realm: Realm) -> None:
    if realm.message_visibility_limit is None:
        realm.first_visible_message_id = 0
    else:
        try:
            first_visible_message_id = (
                # Uses index: zerver_message_realm_id
                Message.objects.filter(realm=realm)
                .values("id")
                .order_by("-id")[realm.message_visibility_limit - 1]["id"]
            )
        except IndexError:
            first_visible_message_id = 0
        realm.first_visible_message_id = first_visible_message_id
    realm.save(update_fields=["first_visible_message_id"])


def get_last_message_id() -> int:
    # We generally use this function to populate RealmAuditLog, and
    # the max id here is actually system-wide, not per-realm.  I
    # assume there's some advantage in not filtering by realm.
    last_id = Message.objects.aggregate(Max("id"))["id__max"]
    if last_id is None:
        # During initial realm creation, there might be 0 messages in
        # the database; in that case, the `aggregate` query returns
        # None.  Since we want an int for "beginning of time", use -1.
        last_id = -1
    return last_id


def get_recent_conversations_recipient_id(
    user_profile: UserProfile, recipient_id: int, sender_id: int
) -> int:
    """Helper for doing lookups of the recipient_id that
    get_recent_private_conversations would have used to record that
    message in its data structure.
    """
    my_recipient_id = user_profile.recipient_id
    if recipient_id == my_recipient_id:
        return UserProfile.objects.values_list("recipient_id", flat=True).get(id=sender_id)
    return recipient_id


def get_recent_private_conversations(user_profile: UserProfile) -> Dict[int, Dict[str, Any]]:
    """This function uses some carefully optimized SQL queries, designed
    to use the UserMessage index on private_messages.  It is
    somewhat complicated by the fact that for 1:1 direct
    messages, we store the message against a recipient_id of whichever
    user was the recipient, and thus for 1:1 direct messages sent
    directly to us, we need to look up the other user from the
    sender_id on those messages.  You'll see that pattern repeated
    both here and also in zerver/lib/events.py.

    It may be possible to write this query directly in Django, however
    it is made much easier by using CTEs, which Django does not
    natively support.

    We return a dictionary structure for convenient modification
    below; this structure is converted into its final form by
    post_process.

    """
    RECENT_CONVERSATIONS_LIMIT = 1000

    recipient_map = {}
    my_recipient_id = user_profile.recipient_id

    query = SQL(
        """
        WITH personals AS (
            SELECT   um.message_id AS message_id
            FROM     zerver_usermessage um
            WHERE    um.user_profile_id = %(user_profile_id)s
            AND      um.flags & 2048 <> 0
            ORDER BY message_id DESC limit %(conversation_limit)s
        ),
        message AS (
            SELECT message_id,
                   CASE
                          WHEN m.recipient_id = %(my_recipient_id)s
                          THEN m.sender_id
                          ELSE NULL
                   END AS sender_id,
                   CASE
                          WHEN m.recipient_id <> %(my_recipient_id)s
                          THEN m.recipient_id
                          ELSE NULL
                   END AS outgoing_recipient_id
            FROM   personals
            JOIN   zerver_message m
            ON     personals.message_id = m.id
        ),
        unified AS (
            SELECT    message_id,
                      COALESCE(zerver_userprofile.recipient_id, outgoing_recipient_id) AS other_recipient_id
            FROM      message
            LEFT JOIN zerver_userprofile
            ON        zerver_userprofile.id = sender_id
        )
        SELECT   other_recipient_id,
                 MAX(message_id)
        FROM     unified
        GROUP BY other_recipient_id
    """
    )

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            {
                "user_profile_id": user_profile.id,
                "conversation_limit": RECENT_CONVERSATIONS_LIMIT,
                "my_recipient_id": my_recipient_id,
            },
        )
        rows = cursor.fetchall()

    # The resulting rows will be (recipient_id, max_message_id)
    # objects for all parties we've had recent (group?) private
    # message conversations with, including direct messages with
    # yourself (those will generate an empty list of user_ids).
    for recipient_id, max_message_id in rows:
        recipient_map[recipient_id] = dict(
            max_message_id=max_message_id,
            user_ids=[],
        )

    # Now we need to map all the recipient_id objects to lists of user IDs
    for recipient_id, user_profile_id in (
        Subscription.objects.filter(recipient_id__in=recipient_map.keys())
        .exclude(user_profile_id=user_profile.id)
        .values_list("recipient_id", "user_profile_id")
    ):
        recipient_map[recipient_id]["user_ids"].append(user_profile_id)

    # Sort to prevent test flakes and client bugs.
    for rec in recipient_map.values():
        rec["user_ids"].sort()

    return recipient_map


def wildcard_mention_policy_authorizes_user(sender: UserProfile, realm: Realm) -> bool:
    """Helper function for 'topic_wildcard_mention_allowed' and
    'stream_wildcard_mention_allowed' to check if the sender is allowed to use
    wildcard mentions based on the 'wildcard_mention_policy' setting of that realm.
    This check is used only if the participants count in the topic or the subscribers
    count in the stream is greater than 'Realm.WILDCARD_MENTION_THRESHOLD'.
    """
    if realm.wildcard_mention_policy == Realm.WILDCARD_MENTION_POLICY_NOBODY:
        return False

    if realm.wildcard_mention_policy == Realm.WILDCARD_MENTION_POLICY_EVERYONE:
        return True

    if realm.wildcard_mention_policy == Realm.WILDCARD_MENTION_POLICY_ADMINS:
        return sender.is_realm_admin

    if realm.wildcard_mention_policy == Realm.WILDCARD_MENTION_POLICY_MODERATORS:
        return sender.is_realm_admin or sender.is_moderator

    if realm.wildcard_mention_policy == Realm.WILDCARD_MENTION_POLICY_FULL_MEMBERS:
        return sender.is_realm_admin or (not sender.is_provisional_member and not sender.is_guest)

    if realm.wildcard_mention_policy == Realm.WILDCARD_MENTION_POLICY_MEMBERS:
        return not sender.is_guest

    raise AssertionError("Invalid wildcard mention policy")


def topic_wildcard_mention_allowed(
    sender: UserProfile, topic_participant_count: int, realm: Realm
) -> bool:
    if topic_participant_count <= Realm.WILDCARD_MENTION_THRESHOLD:
        return True
    return wildcard_mention_policy_authorizes_user(sender, realm)


def stream_wildcard_mention_allowed(sender: UserProfile, stream: Stream, realm: Realm) -> bool:
    # If there are fewer than Realm.WILDCARD_MENTION_THRESHOLD, we
    # allow sending.  In the future, we may want to make this behavior
    # a default, and also just allow explicitly setting whether this
    # applies to a stream as an override.
    if num_subscribers_for_stream_id(stream.id) <= Realm.WILDCARD_MENTION_THRESHOLD:
        return True
    return wildcard_mention_policy_authorizes_user(sender, realm)


def check_user_group_mention_allowed(sender: UserProfile, user_group_ids: List[int]) -> None:
    user_groups = NamedUserGroup.objects.filter(id__in=user_group_ids).select_related(
        "can_mention_group", "can_mention_group__named_user_group"
    )
    sender_is_system_bot = is_cross_realm_bot_email(sender.delivery_email)

    for group in user_groups:
        can_mention_group = group.can_mention_group
        can_mention_group_name = can_mention_group.named_user_group.name
        if sender_is_system_bot:
            if can_mention_group_name == SystemGroups.EVERYONE:
                continue
            raise JsonableError(
                _(
                    "You are not allowed to mention user group '{user_group_name}'. You must be a member of '{can_mention_group_name}' to mention this group."
                ).format(user_group_name=group.name, can_mention_group_name=can_mention_group_name)
            )

        if not is_user_in_group(can_mention_group, sender, direct_member_only=False):
            raise JsonableError(
                _(
                    "You are not allowed to mention user group '{user_group_name}'. You must be a member of '{can_mention_group_name}' to mention this group."
                ).format(user_group_name=group.name, can_mention_group_name=can_mention_group_name)
            )


def parse_message_time_limit_setting(
    value: Union[int, str],
    special_values_map: Mapping[str, Optional[int]],
    *,
    setting_name: str,
) -> Optional[int]:
    if isinstance(value, str) and value in special_values_map:
        return special_values_map[value]
    if isinstance(value, str) or value <= 0:
        raise RequestVariableConversionError(setting_name, value)
    assert isinstance(value, int)
    return value


def visibility_policy_for_participation(
    sender: UserProfile,
    is_stream_muted: Optional[bool],
) -> Optional[int]:
    """
    This function determines the visibility policy to set when a user
    participates in a topic, depending on the 'automatically_follow_topics_policy'
    and 'automatically_unmute_topics_in_muted_streams_policy' settings.
    """
    if (
        sender.automatically_follow_topics_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION
    ):
        return UserTopic.VisibilityPolicy.FOLLOWED

    if (
        is_stream_muted
        and sender.automatically_unmute_topics_in_muted_streams_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION
    ):
        return UserTopic.VisibilityPolicy.UNMUTED

    return None


def visibility_policy_for_send(
    sender: UserProfile,
    is_stream_muted: Optional[bool],
) -> Optional[int]:
    if (
        sender.automatically_follow_topics_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND
    ):
        return UserTopic.VisibilityPolicy.FOLLOWED

    if (
        is_stream_muted
        and sender.automatically_unmute_topics_in_muted_streams_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND
    ):
        return UserTopic.VisibilityPolicy.UNMUTED

    return None


def visibility_policy_for_send_message(
    sender: UserProfile,
    message: Message,
    stream: Stream,
    is_stream_muted: Optional[bool],
    current_visibility_policy: int,
) -> Optional[int]:
    """
    This function determines the visibility policy to set when a message
    is sent to a topic, depending on the 'automatically_follow_topics_policy'
    and 'automatically_unmute_topics_in_muted_streams_policy' settings.

    It returns None when the policies can't make it more visible than the
    current visibility policy.
    """
    # We prioritize 'FOLLOW' over 'UNMUTE' in muted streams.
    # We need to carefully handle the following two cases:
    #
    # 1. When an action qualifies for multiple values. Example:
    #    - starting a topic is INITIATION, PARTICIPATION as well as SEND
    #    - sending a non-first message is PARTICIPATION as well as SEND
    # action | 'automatically_follow_topics_policy' | 'automatically_unmute_topics_in_muted_streams_policy' | visibility_policy
    #  start |    ON_PARTICIPATION / ON_SEND        |                   ON_INITIATION                       |     FOLLOWED
    #  send  |    ON_SEND / ON_PARTICIPATION        |              ON_PARTICIPATION / ON_SEND               |     FOLLOWED
    #
    # 2. When both the policies have the same values.
    # action | 'automatically_follow_topics_policy' | 'automatically_unmute_topics_in_muted_streams_policy' | visibility_policy
    #  start |         ON_INITIATION                |                   ON_INITIATION                       |     FOLLOWED
    #  partc |       ON_PARTICIPATION               |                 ON_PARTICIPATION                      |     FOLLOWED
    #  send  |           ON_SEND                    |                     ON_SEND                           |     FOLLOWED
    visibility_policy = None

    if current_visibility_policy == UserTopic.VisibilityPolicy.FOLLOWED:
        return visibility_policy

    visibility_policy_participation = visibility_policy_for_participation(sender, is_stream_muted)
    visibility_policy_send = visibility_policy_for_send(sender, is_stream_muted)

    if UserTopic.VisibilityPolicy.FOLLOWED in (
        visibility_policy_participation,
        visibility_policy_send,
    ):
        return UserTopic.VisibilityPolicy.FOLLOWED

    if UserTopic.VisibilityPolicy.UNMUTED in (
        visibility_policy_participation,
        visibility_policy_send,
    ):
        visibility_policy = UserTopic.VisibilityPolicy.UNMUTED

    # If a topic has a visibility policy set, it can't be the case
    # of initiation. We return early, thus saving a DB query.
    if current_visibility_policy != UserTopic.VisibilityPolicy.INHERIT:
        if visibility_policy and current_visibility_policy == visibility_policy:
            return None
        return visibility_policy

    # Now we need to check if the user initiated the topic.
    old_accessible_messages_in_topic: Union[QuerySet[Message], QuerySet[UserMessage]]
    if can_access_stream_history(sender, stream):
        old_accessible_messages_in_topic = messages_for_topic(
            realm_id=sender.realm_id,
            stream_recipient_id=message.recipient_id,
            topic_name=message.topic_name(),
        ).exclude(id=message.id)
    else:
        # We use the user's own message access to avoid leaking information in
        # private streams with protected history.
        old_accessible_messages_in_topic = UserMessage.objects.filter(
            user_profile=sender,
            message__recipient_id=message.recipient_id,
            message__subject__iexact=message.topic_name(),
        ).exclude(message_id=message.id)

    if (
        sender.automatically_follow_topics_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION
        and not old_accessible_messages_in_topic.exists()
    ):
        return UserTopic.VisibilityPolicy.FOLLOWED

    if (
        is_stream_muted
        and sender.automatically_unmute_topics_in_muted_streams_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION
        and not old_accessible_messages_in_topic.exists()
    ):
        visibility_policy = UserTopic.VisibilityPolicy.UNMUTED

    return visibility_policy


def should_change_visibility_policy(
    new_visibility_policy: int,
    sender: UserProfile,
    stream_id: int,
    topic_name: str,
) -> bool:
    try:
        user_topic = UserTopic.objects.get(
            user_profile=sender, stream_id=stream_id, topic_name__iexact=topic_name
        )
    except UserTopic.DoesNotExist:
        return True
    current_visibility_policy = user_topic.visibility_policy

    if new_visibility_policy == current_visibility_policy:
        return False

    # The intent of these "automatically follow or unmute" policies is that they
    # can only increase the user's visibility policy for the topic. If a topic is
    # already FOLLOWED, we don't change the state to UNMUTED due to these policies.
    if current_visibility_policy == UserTopic.VisibilityPolicy.FOLLOWED:
        return False

    return True


def set_visibility_policy_possible(user_profile: UserProfile, message: Message) -> bool:
    """If the user can set a visibility policy."""
    if not message.is_stream_message():
        return False

    if user_profile.is_bot:
        return False

    if user_profile.realm != message.get_realm():
        return False

    return True


def remove_single_newlines(content: str) -> str:
    content = content.strip("\n")
    return re.sub(r"(?<!\n)\n(?![\n0-9*-])", " ", content)

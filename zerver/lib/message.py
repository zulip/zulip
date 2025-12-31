import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, TypedDict

from django.conf import settings
from django.db import connection
from django.db.models import Exists, F, Max, OuterRef, QuerySet, Sum
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django_cte import CTE, with_cte
from psycopg2.sql import SQL

from analytics.lib.counts import COUNT_STATS
from analytics.models import RealmCount
from zerver.lib.cache import generic_bulk_cached_fetch, to_dict_cache_key_id
from zerver.lib.display_recipient import get_display_recipient, get_display_recipient_by_id
from zerver.lib.exceptions import JsonableError, MissingAuthenticationError
from zerver.lib.markdown import MessageRenderingResult
from zerver.lib.mention import MentionData, sender_can_mention_group
from zerver.lib.message_cache import MessageDict, extract_message_dict, stringify_message_dict
from zerver.lib.partial import partial
from zerver.lib.request import RequestVariableConversionError
from zerver.lib.stream_subscription import (
    get_active_subscriptions_for_stream_id,
    get_stream_subscriptions_for_user,
    get_subscribed_stream_recipient_ids_for_user,
    num_subscribers_for_stream_id,
)
from zerver.lib.streams import (
    can_access_stream_history,
    get_web_public_streams_queryset,
    is_user_in_groups_granting_content_access,
)
from zerver.lib.topic import (
    MESSAGE__TOPIC,
    RESOLVED_TOPIC_PREFIX,
    TOPIC_NAME,
    maybe_rename_general_chat_to_empty_topic,
    messages_for_topic,
)
from zerver.lib.types import FormattedEditHistoryEvent, UserDisplayRecipient
from zerver.lib.user_groups import UserGroupMembershipDetails, get_recursive_membership_groups
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
from zerver.models.messages import get_usermessage_by_message_id
from zerver.models.realms import MessageEditHistoryVisibilityPolicyEnum
from zerver.models.recipients import DirectMessageGroup


class MessageDetailsDict(TypedDict, total=False):
    type: str
    mentioned: bool
    user_ids: list[int]
    stream_id: int
    topic: str
    unmuted_stream_msg: bool


class RawUnreadStreamDict(TypedDict):
    stream_id: int
    topic: str


class RawUnreadDirectMessageDict(TypedDict):
    other_user_id: int


class RawUnreadDirectMessageGroupDict(TypedDict):
    user_ids_string: str


class RawUnreadMessagesResult(TypedDict):
    pm_dict: dict[int, RawUnreadDirectMessageDict]
    stream_dict: dict[int, RawUnreadStreamDict]
    huddle_dict: dict[int, RawUnreadDirectMessageGroupDict]
    mentions: set[int]
    muted_stream_ids: set[int]
    unmuted_stream_msgs: set[int]
    old_unreads_missing: bool


class UnreadStreamInfo(TypedDict):
    stream_id: int
    topic: str
    unread_message_ids: list[int]


class UnreadDirectMessageInfo(TypedDict):
    other_user_id: int
    # Deprecated and misleading synonym for other_user_id
    sender_id: int
    unread_message_ids: list[int]


class UnreadDirectMessageGroupInfo(TypedDict):
    user_ids_string: str
    unread_message_ids: list[int]


class UnreadMessagesResult(TypedDict):
    pms: list[UnreadDirectMessageInfo]
    streams: list[UnreadStreamInfo]
    huddles: list[UnreadDirectMessageGroupInfo]
    mentions: list[int]
    count: int
    old_unreads_missing: bool


@dataclass
class SendMessageRequest:
    message: Message
    rendering_result: MessageRenderingResult
    stream: Stream | None
    sender_muted_stream: bool | None
    local_id: str | None
    sender_queue_id: str | None
    realm: Realm
    mention_data: MentionData
    mentioned_user_groups_map: dict[int, int]
    active_user_ids: set[int]
    online_push_user_ids: set[int]
    dm_mention_push_disabled_user_ids: set[int]
    dm_mention_email_disabled_user_ids: set[int]
    stream_push_user_ids: set[int]
    stream_email_user_ids: set[int]
    # IDs of users who have followed the topic the message is being sent to,
    # and have the followed topic push notifications setting ON.
    followed_topic_push_user_ids: set[int]
    # IDs of users who have followed the topic the message is being sent to,
    # and have the followed topic email notifications setting ON.
    followed_topic_email_user_ids: set[int]
    muted_sender_user_ids: set[int]
    um_eligible_user_ids: set[int]
    long_term_idle_user_ids: set[int]
    default_bot_user_ids: set[int]
    service_bot_tuples: list[tuple[int, int]]
    all_bot_user_ids: set[int]
    push_device_registered_user_ids: set[int]
    # IDs of topic participants who should be notified of topic wildcard mention.
    # The 'user_allows_notifications_in_StreamTopic' with 'wildcard_mentions_notify'
    # setting ON should return True.
    # A user_id can exist in either or both of the 'topic_wildcard_mention_user_ids'
    # and 'topic_wildcard_mention_in_followed_topic_user_ids' sets.
    topic_wildcard_mention_user_ids: set[int]
    # IDs of users subscribed to the stream who should be notified of
    # stream wildcard mention.
    # The 'user_allows_notifications_in_StreamTopic' with 'wildcard_mentions_notify'
    # setting ON should return True.
    # A user_id can exist in either or both of the 'stream_wildcard_mention_user_ids'
    # and 'stream_wildcard_mention_in_followed_topic_user_ids' sets.
    stream_wildcard_mention_user_ids: set[int]
    # IDs of topic participants who have followed the topic the message
    # (having topic wildcard) is being sent to, and have the
    # 'followed_topic_wildcard_mentions_notify' setting ON.
    topic_wildcard_mention_in_followed_topic_user_ids: set[int]
    # IDs of users who have followed the topic the message
    # (having stream wildcard) is being sent to, and have the
    # 'followed_topic_wildcard_mentions_notify' setting ON.
    stream_wildcard_mention_in_followed_topic_user_ids: set[int]
    # A topic participant is anyone who either sent or reacted to messages in the topic.
    topic_participant_user_ids: set[int]
    links_for_embed: set[str]
    widget_content: dict[str, Any] | None
    submessages: list[dict[str, Any]] = field(default_factory=list)
    deliver_at: datetime | None = None
    delivery_type: str | None = None
    limit_unread_user_ids: set[int] | None = None
    service_queue_events: dict[str, list[dict[str, Any]]] | None = None
    disable_external_notifications: bool = False
    automatic_new_visibility_policy: int | None = None
    recipients_for_user_creation_events: dict[UserProfile, set[int]] | None = None
    reminder_target_message_id: int | None = None
    reminder_note: str | None = None
    message_url: str | None = None
    message_link: str | None = None


@dataclass
class OnlyMessageFields:
    select_related: list[str]
    fields: list[str]


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


def normalize_body_for_import(body: str) -> str:
    if "\x00" in body:
        body = re.sub(r"\x00", "", body)
    return truncate_content(body, settings.MAX_MESSAGE_LENGTH, "\n[message truncated]")


TOPIC_TRUNCATION_MESSAGE = "..."


def truncate_topic(topic_name: str) -> str:
    return truncate_content(topic_name, MAX_TOPIC_NAME_LENGTH, TOPIC_TRUNCATION_MESSAGE)


def visible_edit_history_for_message(
    message_edit_history_visibility_policy: int,
    edit_history: list[FormattedEditHistoryEvent],
) -> list[FormattedEditHistoryEvent]:
    # Makes sure that we send message edit history to clients
    # in realms as per `message_edit_history_visibility_policy`.
    if message_edit_history_visibility_policy == MessageEditHistoryVisibilityPolicyEnum.all.value:
        return edit_history

    visible_edit_history: list[FormattedEditHistoryEvent] = []
    for edit_history_event in edit_history:
        if "prev_content" in edit_history_event:
            if "prev_topic" in edit_history_event:
                del edit_history_event["prev_content"]
                del edit_history_event["prev_rendered_content"]
                del edit_history_event["content_html_diff"]
            else:
                continue
        visible_edit_history.append(edit_history_event)

    return visible_edit_history


# This is similar to what we do in build_message_edit_request in
# zerver/actions/message_edit.py, but since we don't have the
# pre-truncation topic name in the message edit history object,
# the logic for the topic resolved case is different here.
def topic_resolve_toggled(topic: str, prev_topic: str) -> bool:
    resolved_prefix_len = len(RESOLVED_TOPIC_PREFIX)
    truncation_len = len(TOPIC_TRUNCATION_MESSAGE)
    # Topic unresolved
    if prev_topic.startswith(RESOLVED_TOPIC_PREFIX) and not topic.startswith(RESOLVED_TOPIC_PREFIX):
        return prev_topic[resolved_prefix_len:] == topic

    # Topic resolved
    if topic.startswith(RESOLVED_TOPIC_PREFIX) and not prev_topic.startswith(RESOLVED_TOPIC_PREFIX):
        if len(prev_topic) <= MAX_TOPIC_NAME_LENGTH - resolved_prefix_len:
            # When the topic was resolved, it was not truncated,
            # so we remove the resolved prefix and compare.
            return topic[resolved_prefix_len:] == prev_topic
        if topic.endswith(TOPIC_TRUNCATION_MESSAGE):
            # When the topic was resolved, it was likely truncated,
            # so we confirm the previous topic starts with the topic
            # without the resolved prefix and truncation message.
            topic_without_resolved_prefix_and_truncation_message = topic[
                resolved_prefix_len:-truncation_len
            ]
            return prev_topic.startswith(topic_without_resolved_prefix_and_truncation_message)

    return False


def messages_for_ids(
    message_ids: list[int],
    user_message_flags: dict[int, list[str]],
    search_fields: dict[int, dict[str, str]],
    apply_markdown: bool,
    client_gravatar: bool,
    allow_empty_topic_name: bool,
    message_edit_history_visibility_policy: int,
    user_profile: UserProfile | None,
    realm: Realm,
) -> list[dict[str, Any]]:
    id_fetcher = lambda row: row["id"]

    message_dicts = generic_bulk_cached_fetch(
        to_dict_cache_key_id,
        MessageDict.ids_to_dict,
        message_ids,
        id_fetcher=id_fetcher,
        cache_transformer=lambda obj: obj,
        extractor=extract_message_dict,
        setter=stringify_message_dict,
        pickled_tupled=False,
    )

    message_list: list[dict[str, Any]] = []

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
        if "edit_history" in msg_dict:
            # In addition to computing last_moved_timestamp, we recompute
            # last_edit_timestamp, because the logic powering the database
            # field updates it on moves as well, and we'd like to show the
            # correct value for messages that had only been moved.
            last_moved_timestamp = 0
            last_edit_timestamp = 0
            for item in msg_dict["edit_history"]:
                if "prev_stream" in item:
                    last_moved_timestamp = max(last_moved_timestamp, item["timestamp"])
                elif "prev_topic" in item and not topic_resolve_toggled(
                    item["topic"], item["prev_topic"]
                ):
                    last_moved_timestamp = max(last_moved_timestamp, item["timestamp"])
                if "prev_content" in item:
                    last_edit_timestamp = max(last_edit_timestamp, item["timestamp"])
            if last_moved_timestamp != 0:
                msg_dict["last_moved_timestamp"] = last_moved_timestamp
            if last_edit_timestamp != 0:
                msg_dict["last_edit_timestamp"] = last_edit_timestamp
            else:
                # Remove it if it was already present.
                msg_dict.pop("last_edit_timestamp", None)

            if (
                message_edit_history_visibility_policy
                == MessageEditHistoryVisibilityPolicyEnum.none.value
            ):
                del msg_dict["edit_history"]
            else:
                visible_edit_history = visible_edit_history_for_message(
                    message_edit_history_visibility_policy, msg_dict["edit_history"]
                )
                msg_dict["edit_history"] = visible_edit_history

        msg_dict["can_access_sender"] = msg_dict["sender_id"] not in inaccessible_sender_ids
        message_list.append(msg_dict)

    MessageDict.post_process_dicts(
        message_list,
        apply_markdown=apply_markdown,
        client_gravatar=client_gravatar,
        allow_empty_topic_name=allow_empty_topic_name,
        realm=realm,
        user_recipient_id=None if user_profile is None else user_profile.recipient_id,
    )

    return message_list


def access_message(
    user_profile: UserProfile,
    message_id: int,
    lock_message: bool = False,
    *,
    is_modifying_message: bool,
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

    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    if has_message_access(
        user_profile,
        message,
        has_user_message=has_user_message,
        user_group_membership_details=user_group_membership_details,
        is_modifying_message=is_modifying_message,
    ):
        return message
    raise JsonableError(_("Invalid message(s)"))


def access_message_and_usermessage(
    user_profile: UserProfile,
    message_id: int,
    lock_message: bool = False,
    *,
    is_modifying_message: bool,
    # Fetches only specified fields from Message and related models.
    # Use for performance-critical paths.
    only_message_fields: OnlyMessageFields | None = None,
) -> tuple[Message, UserMessage | None]:
    """As access_message, but also returns the usermessage, if any."""
    try:
        if only_message_fields is None:
            base_query = Message.objects.select_related(*Message.DEFAULT_SELECT_RELATED)
        else:
            base_query = Message.objects.select_related(*only_message_fields.select_related).only(
                *only_message_fields.fields
            )
        if lock_message:
            # We want to lock only the `Message` row, and not the related fields
            # because the `Message` row only has a possibility of races.
            base_query = base_query.select_for_update(of=("self",))
        message = base_query.get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError(_("Invalid message(s)"))

    user_message = get_usermessage_by_message_id(user_profile, message_id)
    has_user_message = lambda: user_message is not None

    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    if has_message_access(
        user_profile,
        message,
        has_user_message=has_user_message,
        user_group_membership_details=user_group_membership_details,
        is_modifying_message=is_modifying_message,
    ):
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

    if not message.is_channel_message:
        raise MissingAuthenticationError

    queryset = get_web_public_streams_queryset(realm)
    try:
        stream = queryset.get(id=message.recipient.type_id)
    except Stream.DoesNotExist:
        raise MissingAuthenticationError

    # These should all have been enforced by the code in
    # get_web_public_streams_queryset
    assert stream.is_web_public
    assert not stream.invite_only
    assert stream.history_public_to_subscribers

    # Now that we've confirmed this message was sent to the target
    # web-public stream, we can return it as having been successfully
    # accessed.
    return message


def has_channel_content_access_helper(
    stream: Stream,
    user_profile: UserProfile,
    user_group_membership_details: UserGroupMembershipDetails,
    *,
    is_subscribed: bool | None,
) -> bool:
    """
    Checks whether a user has content access to a channel specifically
    via being subscribed or group membership.

    Does not consider the implicit permissions associated with web-public
    or public channels; callers are responsible for that.

    This logic is mirrored in zerver.lib.narrow.get_base_query_for_search.
    """
    if is_subscribed is None:
        assert stream.recipient_id is not None
        is_user_subscribed = Subscription.objects.filter(
            user_profile=user_profile, active=True, recipient_id=stream.recipient_id
        ).exists()
    else:
        is_user_subscribed = is_subscribed

    if is_user_subscribed:
        return True

    if user_profile.is_guest:
        # All existing groups granting content access have allow_everyone_group=False.
        #
        # TODO: is_user_in_groups_granting_content_access needs to
        # accept at least `is_guest`, and maybe just the user, when we
        # have groups granting content access with
        # allow_everyone_group=True.
        return False

    if user_group_membership_details.user_recursive_group_ids is None:
        user_group_membership_details.user_recursive_group_ids = set(
            get_recursive_membership_groups(user_profile).values_list("id", flat=True)
        )

    return is_user_in_groups_granting_content_access(
        stream, user_group_membership_details.user_recursive_group_ids
    )


def has_message_access(
    user_profile: UserProfile,
    message: Message,
    *,
    has_user_message: Callable[[], bool],
    stream: Stream | None = None,
    is_subscribed: bool | None = None,
    user_group_membership_details: UserGroupMembershipDetails,
    is_modifying_message: bool,
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

    if is_modifying_message and stream.deactivated:
        # You can't access messages in deactivated streams
        return False

    if stream.is_public() and user_profile.can_access_public_streams():
        return True

    if not stream.is_history_public_to_subscribers():
        # Unless history is public to subscribers, you need to both:
        # (1) Have directly received the message.
        # AND
        # (2) Be subscribed to the stream.
        return has_user_message() and has_channel_content_access_helper(
            stream, user_profile, user_group_membership_details, is_subscribed=is_subscribed
        )

    # is_history_public_to_subscribers, so check if you're subscribed
    return has_channel_content_access_helper(
        stream, user_profile, user_group_membership_details, is_subscribed=is_subscribed
    )


def event_recipient_ids_for_action_on_messages(
    messages: list[Message],
    *,
    channel: Stream | None = None,
    exclude_long_term_idle_users: bool = True,
) -> set[int]:
    """Returns IDs of users who should receive events when an action
    (delete, react, etc) is performed on given set of messages, which
    are expected to all be in a single conversation.

    This function aligns with the 'has_message_access' above to ensure
    that events reach only those users who have access to the messages.

    Notably, for performance reasons, we do not send live-update
    events to everyone who could potentially have a cached copy of a
    message because they fetched messages in a public channel to which
    they are not subscribed. Such events are limited to those messages
    where the user has a UserMessage row (including `historical` rows).
    """
    assert len(messages) > 0
    message_ids = [message.id for message in messages]

    def get_user_ids_having_usermessage_row_for_messages(message_ids: list[int]) -> set[int]:
        """Returns the IDs of users who actually received the messages."""
        usermessages = UserMessage.objects.filter(message_id__in=message_ids)
        if exclude_long_term_idle_users:
            usermessages = usermessages.exclude(user_profile__long_term_idle=True)
        return set(usermessages.values_list("user_profile_id", flat=True))

    sample_message = messages[0]
    if not sample_message.is_channel_message:
        # For DM, event is sent to users who actually received the message.
        return get_user_ids_having_usermessage_row_for_messages(message_ids)

    channel_id = sample_message.recipient.type_id
    if channel is None:
        channel = Stream.objects.get(id=channel_id)

    subscriptions = get_active_subscriptions_for_stream_id(
        channel_id, include_deactivated_users=False
    )
    if exclude_long_term_idle_users:
        subscriptions = subscriptions.exclude(user_profile__long_term_idle=True)
    subscriber_ids = set(subscriptions.values_list("user_profile_id", flat=True))

    if not channel.is_history_public_to_subscribers():
        # For protected history, only users who are subscribed and
        # received the original message are notified.
        assert not channel.is_public()
        user_ids_with_usermessage_row = get_user_ids_having_usermessage_row_for_messages(
            message_ids
        )
        return user_ids_with_usermessage_row & subscriber_ids

    if not channel.is_public():
        # For private channel with shared history, the set of
        # users with access is exactly the subscribers.
        return subscriber_ids

    # The remaining case is public channels with public history. Events are sent to:
    # 1. Current channel subscribers
    # 2. Unsubscribed users having usermessage row & channel access.
    #    * Users who never subscribed but starred or reacted on messages
    #      (usermessages with historical flag exists for such cases).
    #    * Users who were initially subscribed and later unsubscribed
    #      (usermessages exist for messages they received while subscribed).
    usermessage_rows = UserMessage.objects.filter(message_id__in=message_ids).exclude(
        # Excluding guests here implements can_access_public_channels.
        user_profile__role=UserProfile.ROLE_GUEST
    )
    if exclude_long_term_idle_users:
        usermessage_rows = usermessage_rows.exclude(user_profile__long_term_idle=True)
    user_ids_with_usermessage_row_and_channel_access = set(
        usermessage_rows.values_list("user_profile_id", flat=True)
    )
    return user_ids_with_usermessage_row_and_channel_access | subscriber_ids


def bulk_access_messages(
    user_profile: UserProfile,
    messages: Collection[Message] | QuerySet[Message],
    *,
    stream: Stream | None = None,
    is_modifying_message: bool,
) -> list[Message]:
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

    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    for message in messages:
        is_subscribed = message.recipient_id in subscribed_recipient_ids
        if has_message_access(
            user_profile,
            message,
            has_user_message=partial(lambda m: m.id in user_message_set, message),
            stream=streams.get(message.recipient_id) if stream is None else stream,
            is_subscribed=is_subscribed,
            user_group_membership_details=user_group_membership_details,
            is_modifying_message=False,
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

    This logic is mirrored in zerver.lib.narrow.get_base_query_for_search.
    """

    assert stream.recipient_id is not None
    messages = messages.filter(realm_id=user_profile.realm_id, recipient_id=stream.recipient_id)

    if stream.is_public() and user_profile.can_access_public_streams():
        return messages

    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    has_content_access = has_channel_content_access_helper(
        stream, user_profile, user_group_membership_details, is_subscribed=None
    )

    if not has_content_access:
        return Message.objects.none()
    if not stream.is_history_public_to_subscribers():
        messages = messages.alias(
            has_usermessage=Exists(
                UserMessage.objects.filter(
                    user_profile_id=user_profile.id, message_id=OuterRef("id")
                )
            )
        ).filter(has_usermessage=True)
    return messages


def get_messages_with_usermessage_rows_for_user(
    user_profile_id: int, message_ids: Sequence[int]
) -> QuerySet[UserMessage, int]:
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


def direct_message_group_users(recipient_id: int) -> str:
    display_recipient: list[UserDisplayRecipient] = get_display_recipient_by_id(
        recipient_id,
        Recipient.DIRECT_MESSAGE_GROUP,
        None,
    )

    user_ids: list[int] = [obj["id"] for obj in display_recipient]
    user_ids = sorted(user_ids)
    return ",".join(str(uid) for uid in user_ids)


def get_inactive_recipient_ids(user_profile: UserProfile) -> list[int]:
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


def get_muted_stream_ids(user_profile: UserProfile) -> set[int]:
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


def get_starred_message_ids(user_profile: UserProfile) -> list[int]:
    return list(
        UserMessage.objects.filter(
            user_profile=user_profile,
        )
        .extra(  # noqa: S610
            where=[UserMessage.where_starred()],
        )
        .order_by(
            "message_id",
        )
        .values_list("message_id", flat=True)[0:10000]
    )


def get_raw_unread_data(
    user_profile: UserProfile, message_ids: list[int] | None = None
) -> RawUnreadMessagesResult:
    excluded_recipient_ids = get_inactive_recipient_ids(user_profile)
    first_visible_message_id = get_first_visible_message_id(user_profile.realm)
    user_msgs = (
        UserMessage.objects.filter(
            user_profile=user_profile,
            message_id__gte=first_visible_message_id,
        )
        .exclude(
            message__recipient_id__in=excluded_recipient_ids,
        )
        .annotate(
            recipient_id=F("message__recipient_id"),
            sender_id=F("message__sender_id"),
            topic=F(MESSAGE__TOPIC),
        )
        .values(
            "message_id",
            "sender_id",
            "topic",
            "flags",
            "recipient_id",
        )
        # Descending order, so truncation keeps the latest unreads.
        .order_by("-message_id")
    )

    if message_ids is not None:
        # When users are marking just a few messages as unread, we just need
        # those ids, and we know they're unread.
        user_msgs = user_msgs.filter(message_id__in=message_ids)
    else:
        # At page load we need all unread messages.
        user_msgs = user_msgs.extra(  # noqa: S610
            where=[UserMessage.where_unread()],
        )

    with connection.cursor() as cursor:
        try:
            # Force-disable (parallel) bitmap heap scans.  The
            # parallel nature of this means that the LIMIT cannot be
            # pushed down into the walk of the index, and it also
            # requires an additional outer sort -- which is all
            # unnecessary, as the zerver_usermessage_unread_message_id
            # index is properly ordered already.  This is all due to
            # statistics mis-estimations, since partial indexes do not
            # have their own statistics.
            cursor.execute("SET enable_bitmapscan TO off")

            # Limit unread messages for performance reasons.  We do this
            # inside a CTE, such that the join to Recipients, below, can't be
            # implied to remove rows, and thus allows a Nested Loop join,
            # potentially memoized to reduce the number of Recipient lookups.
            cte = CTE(user_msgs[:MAX_UNREAD_MESSAGES])

            user_msgs = (
                with_cte(cte, select=cte.join(Recipient, id=cte.col.recipient_id))
                .annotate(
                    message_id=cte.col.message_id,
                    sender_id=cte.col.sender_id,
                    recipient_id=cte.col.recipient_id,
                    topic=cte.col.topic,
                    flags=cte.col.flags,
                    recipient__type=F("type"),
                    recipient__type_id=F("type_id"),
                )
                .values(
                    "message_id",
                    "sender_id",
                    "topic",
                    "flags",
                    "recipient_id",
                    "recipient__type",
                    "recipient__type_id",
                )
                # Output in ascending order. We can't just reverse,
                # since the CTE join does not guarantee that it
                # preserves the original descending order.
                .order_by("message_id")
            )

            rows = list(user_msgs)
        finally:
            cursor.execute("SET enable_bitmapscan TO on")
        return extract_unread_data_from_um_rows(rows, user_profile)


def extract_unread_data_from_um_rows(
    rows: list[dict[str, Any]], user_profile: UserProfile | None
) -> RawUnreadMessagesResult:
    pm_dict: dict[int, RawUnreadDirectMessageDict] = {}
    stream_dict: dict[int, RawUnreadStreamDict] = {}
    muted_stream_ids: set[int] = set()
    unmuted_stream_msgs: set[int] = set()
    direct_message_group_dict: dict[int, RawUnreadDirectMessageGroupDict] = {}
    mentions: set[int] = set()
    total_unreads = 0

    raw_unread_messages: RawUnreadMessagesResult = dict(
        pm_dict=pm_dict,
        stream_dict=stream_dict,
        muted_stream_ids=muted_stream_ids,
        unmuted_stream_msgs=unmuted_stream_msgs,
        huddle_dict=direct_message_group_dict,
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

    direct_message_group_cache: dict[int, str] = {}

    def get_direct_message_group_users(recipient_id: int) -> str:
        if recipient_id in direct_message_group_cache:
            return direct_message_group_cache[recipient_id]

        user_ids_string = direct_message_group_users(recipient_id)
        direct_message_group_cache[recipient_id] = user_ids_string
        return user_ids_string

    for row in rows:
        total_unreads += 1
        message_id = row["message_id"]
        msg_type = row["recipient__type"]
        recipient_id = row["recipient_id"]
        sender_id = row["sender_id"]

        if msg_type == Recipient.STREAM:
            stream_id = row["recipient__type_id"]
            topic_name = row["topic"]
            stream_dict[message_id] = dict(
                stream_id=stream_id,
                topic=topic_name,
            )
            if not is_row_muted(stream_id, recipient_id, topic_name):
                unmuted_stream_msgs.add(message_id)

        elif msg_type == Recipient.PERSONAL:
            if sender_id == user_profile.id:
                other_user_id = row["recipient__type_id"]
            else:
                other_user_id = sender_id

            pm_dict[message_id] = dict(
                other_user_id=other_user_id,
            )

        elif msg_type == Recipient.DIRECT_MESSAGE_GROUP:
            user_ids_string = get_direct_message_group_users(recipient_id)
            user_ids = [int(uid) for uid in user_ids_string.split(",")]

            # For API compatibility, we populate pm_dict for 1:1 and self DMs
            # so clients relying on pm_dict continue to work during the migration.
            # We populate direct_message_group_dict for group size > 2.
            if len(user_ids) <= 2:
                if len(user_ids) == 1:
                    # For self-DM, other_user_id is the user's own id
                    other_user_id = user_ids[0]
                else:
                    # For 1:1 DM, other_user_id is the other participant
                    other_user_id = user_ids[1] if user_ids[0] == user_profile.id else user_ids[0]

                pm_dict[message_id] = dict(
                    other_user_id=other_user_id,
                )
            else:
                direct_message_group_dict[message_id] = dict(
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
                stream_id = row["recipient__type_id"]
                topic_name = row["topic"]
                if not is_row_muted(stream_id, recipient_id, topic_name):
                    mentions.add(message_id)
            else:  # nocoverage # TODO: Test wildcard mentions in direct messages.
                mentions.add(message_id)

    # Record whether the user had more than MAX_UNREAD_MESSAGES total
    # unreads -- that's a state where Zulip's behavior will start to
    # be erroneous, and clients should display a warning.
    raw_unread_messages["old_unreads_missing"] = total_unreads == MAX_UNREAD_MESSAGES

    return raw_unread_messages


def aggregate_streams(
    *, input_dict: dict[int, RawUnreadStreamDict], allow_empty_topic_name: bool
) -> list[UnreadStreamInfo]:
    lookup_dict: dict[tuple[int, str], UnreadStreamInfo] = {}
    for message_id, attribute_dict in input_dict.items():
        stream_id = attribute_dict["stream_id"]
        topic_name = attribute_dict["topic"]
        if topic_name == "" and not allow_empty_topic_name:
            topic_name = Message.EMPTY_TOPIC_FALLBACK_NAME
        lookup_key = (stream_id, topic_name.lower())
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
    *, input_dict: dict[int, RawUnreadDirectMessageDict]
) -> list[UnreadDirectMessageInfo]:
    lookup_dict: dict[int, UnreadDirectMessageInfo] = {}
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


def aggregate_direct_message_groups(
    *, input_dict: dict[int, RawUnreadDirectMessageGroupDict]
) -> list[UnreadDirectMessageGroupInfo]:
    lookup_dict: dict[str, UnreadDirectMessageGroupInfo] = {}
    for message_id, attribute_dict in input_dict.items():
        user_ids_string = attribute_dict["user_ids_string"]
        if user_ids_string not in lookup_dict:
            obj = UnreadDirectMessageGroupInfo(
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


def aggregate_unread_data(
    raw_data: RawUnreadMessagesResult, allow_empty_topic_name: bool
) -> UnreadMessagesResult:
    pm_dict = raw_data["pm_dict"]
    stream_dict = raw_data["stream_dict"]
    unmuted_stream_msgs = raw_data["unmuted_stream_msgs"]
    direct_message_group_dict = raw_data["huddle_dict"]
    mentions = list(raw_data["mentions"])

    count = len(pm_dict) + len(unmuted_stream_msgs) + len(direct_message_group_dict)

    pm_objects = aggregate_pms(input_dict=pm_dict)
    stream_objects = aggregate_streams(
        input_dict=stream_dict, allow_empty_topic_name=allow_empty_topic_name
    )
    direct_message_groups = aggregate_direct_message_groups(input_dict=direct_message_group_dict)

    result: UnreadMessagesResult = dict(
        pms=pm_objects,
        streams=stream_objects,
        huddles=direct_message_groups,
        mentions=mentions,
        count=count,
        old_unreads_missing=raw_data["old_unreads_missing"],
    )

    return result


def apply_unread_message_event(
    user_profile: UserProfile,
    state: RawUnreadMessagesResult,
    message: dict[str, Any],
    flags: list[str],
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
        visibility_policy = get_topic_visibility_policy(
            user_profile, stream_id, topic_name=maybe_rename_general_chat_to_empty_topic(topic_name)
        )
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

        state["huddle_dict"][message_id] = RawUnreadDirectMessageGroupDict(
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
) -> dict[str, MessageDetailsDict]:
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
        user_ids: list[int] = message_details["user_ids"]
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
            state["huddle_dict"][message_id] = RawUnreadDirectMessageGroupDict(
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


def _get_recent_conversations_via_legacy_personal_recipient(
    user_profile_id: int, recipient_id: int
) -> list[tuple[int, int]]:
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
    """
    RECENT_CONVERSATIONS_LIMIT = 1000

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
                          WHEN m.recipient_id = %(recipient_id)s
                          THEN m.sender_id
                          ELSE NULL
                   END AS sender_id,
                   CASE
                          WHEN m.recipient_id <> %(recipient_id)s
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
                "user_profile_id": user_profile_id,
                "conversation_limit": RECENT_CONVERSATIONS_LIMIT,
                "recipient_id": recipient_id,
            },
        )
        return cursor.fetchall()


def _get_recent_conversations_via_direct_message_group(
    user_profile_id: int,
) -> list[tuple[int, int]]:
    """
    This functions fetches the most recent conversations given that all
    private messages of this user are through direct message groups.
    """
    RECENT_CONVERSATIONS_LIMIT = 1000

    recent_pm_message_ids = (
        UserMessage.objects.filter(user_profile_id=user_profile_id)
        .extra(where=[UserMessage.where_flag_is_present(UserMessage.flags.is_private)])  # noqa: S610
        .order_by("-message_id")
        .values_list("message_id", flat=True)[:RECENT_CONVERSATIONS_LIMIT]
    )

    return list(
        Message.objects.filter(id__in=recent_pm_message_ids)
        .values("recipient_id")
        .annotate(max_message_id=Max("id"))
        .values_list("recipient_id", "max_message_id")
    )


def get_recent_private_conversations(user_profile: UserProfile) -> dict[int, dict[str, Any]]:
    """
    We return a dictionary structure for convenient modification
    below; this structure is converted into its final form by
    post_process.
    """
    # Step 1: Collect recent message info
    if user_profile.recipient_id is not None:
        recent_conversations = _get_recent_conversations_via_legacy_personal_recipient(
            user_profile.id, user_profile.recipient_id
        )
    else:
        recent_conversations = _get_recent_conversations_via_direct_message_group(user_profile.id)

    recipient_map: dict[int, dict[str, Any]] = {
        recipient_id: {"max_message_id": max_message_id, "user_ids": []}
        for recipient_id, max_message_id in recent_conversations
    }

    # Now we need to map all the recipient_id objects to lists of user IDs
    subscriptions = (
        Subscription.objects.filter(recipient_id__in=recipient_map.keys())
        .exclude(user_profile_id=user_profile.id)
        .values_list("recipient_id", "user_profile_id")
    )
    for recipient_id, user_profile_id in subscriptions:
        recipient_map[recipient_id]["user_ids"].append(user_profile_id)

    # Sort to prevent test flakes and client bugs.
    for rec in recipient_map.values():
        rec["user_ids"].sort()

    return recipient_map


def can_mention_many_users(sender: UserProfile) -> bool:
    """Helper function for 'topic_wildcard_mention_allowed' and
    'stream_wildcard_mention_allowed' to check if the sender is allowed to use
    wildcard mentions based on the 'can_mention_many_users_group' setting of that realm.
    This check is used only if the participants count in the topic or the subscribers
    count in the stream is greater than 'Realm.WILDCARD_MENTION_THRESHOLD'.
    """
    return sender.has_permission("can_mention_many_users_group")


def topic_wildcard_mention_allowed(
    sender: UserProfile, topic_participant_count: int, realm: Realm
) -> bool:
    if topic_participant_count <= Realm.WILDCARD_MENTION_THRESHOLD:
        return True
    return can_mention_many_users(sender)


def stream_wildcard_mention_allowed(sender: UserProfile, stream: Stream, realm: Realm) -> bool:
    # If there are fewer than Realm.WILDCARD_MENTION_THRESHOLD, we
    # allow sending.  In the future, we may want to make this behavior
    # a default, and also just allow explicitly setting whether this
    # applies to a stream as an override.
    if num_subscribers_for_stream_id(stream.id) <= Realm.WILDCARD_MENTION_THRESHOLD:
        return True
    return can_mention_many_users(sender)


def check_user_group_mention_allowed(sender: UserProfile, user_group_ids: list[int]) -> None:
    user_groups = NamedUserGroup.objects.filter(id__in=user_group_ids).select_related(
        "can_mention_group", "can_mention_group__named_user_group"
    )

    for group in user_groups:
        if not sender_can_mention_group(sender, group):
            raise JsonableError(
                _("You are not allowed to mention user group '{user_group_name}'.").format(
                    user_group_name=group.name
                )
            )


def parse_message_time_limit_setting(
    value: int | str,
    special_values_map: Mapping[str, int | None],
    *,
    setting_name: str,
) -> int | None:
    if isinstance(value, str) and value in special_values_map:
        return special_values_map[value]
    if isinstance(value, str) or value <= 0:
        raise RequestVariableConversionError(setting_name, value)
    assert isinstance(value, int)
    return value


def visibility_policy_for_participation(
    sender: UserProfile,
    is_stream_muted: bool | None,
) -> int | None:
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
    is_stream_muted: bool | None,
) -> int | None:
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
    is_stream_muted: bool | None,
    current_visibility_policy: int,
) -> int | None:
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
    old_accessible_messages_in_topic: QuerySet[Message] | QuerySet[UserMessage]
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
            message__is_channel_message=True,
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
    if not message.is_channel_message:
        return False

    if user_profile.is_bot:
        return False

    if user_profile.realm != message.get_realm():
        return False

    return True


def remove_single_newlines(content: str) -> str:
    content = content.strip("\n")
    return re.sub(r"(?<!\n)\n(?!\n|[-*] |[0-9]+\. ) *", " ", content)


def is_1_to_1_message(message: Message) -> bool:
    if message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        direct_message_group = DirectMessageGroup.objects.get(id=message.recipient.type_id)
        return direct_message_group.group_size <= 2

    if message.recipient.type == Recipient.PERSONAL:
        return True

    return False


def is_message_to_self(message: Message) -> bool:
    if message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        group_members = get_display_recipient(message.recipient)
        return len(group_members) == 1 and group_members[0]["id"] == message.sender.id

    if message.recipient.type == Recipient.PERSONAL:
        return message.recipient == message.sender.recipient

    return False

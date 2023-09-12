import copy
import datetime
import zlib
from dataclasses import dataclass, field
from typing import (
    Any,
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

import ahocorasick
import orjson
from django.conf import settings
from django.db import connection
from django.db.models import Max, Sum
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django_stubs_ext import ValuesQuerySet
from psycopg2.sql import SQL

from analytics.lib.counts import COUNT_STATS
from analytics.models import RealmCount
from zerver.lib.avatar import get_avatar_field
from zerver.lib.cache import (
    cache_set_many,
    cache_with_key,
    generic_bulk_cached_fetch,
    to_dict_cache_key,
    to_dict_cache_key_id,
)
from zerver.lib.display_recipient import bulk_fetch_display_recipients
from zerver.lib.exceptions import JsonableError, MissingAuthenticationError
from zerver.lib.markdown import MessageRenderingResult, markdown_convert, topic_links
from zerver.lib.markdown import version as markdown_version
from zerver.lib.mention import MentionData
from zerver.lib.request import RequestVariableConversionError
from zerver.lib.stream_subscription import (
    get_stream_subscriptions_for_user,
    get_subscribed_stream_recipient_ids_for_user,
    num_subscribers_for_stream_id,
)
from zerver.lib.streams import get_web_public_streams_queryset
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import DB_TOPIC_NAME, MESSAGE__TOPIC, TOPIC_LINKS, TOPIC_NAME
from zerver.lib.types import DisplayRecipientT, EditHistoryEvent, UserDisplayRecipient
from zerver.lib.url_preview.types import UrlEmbedData
from zerver.lib.user_groups import is_user_in_group
from zerver.lib.user_topics import build_topic_mute_checker, topic_has_visibility_policy
from zerver.models import (
    MAX_TOPIC_NAME_LENGTH,
    Message,
    Reaction,
    Realm,
    Recipient,
    Stream,
    SubMessage,
    Subscription,
    UserGroup,
    UserMessage,
    UserProfile,
    UserTopic,
    get_display_recipient_by_id,
    get_usermessage_by_message_id,
    query_for_ids,
)


class MessageDetailsDict(TypedDict, total=False):
    type: str
    mentioned: bool
    user_ids: List[int]
    stream_id: int
    topic: str
    unmuted_stream_msg: bool


class RawReactionRow(TypedDict):
    emoji_code: str
    emoji_name: str
    message_id: int
    reaction_type: str
    user_profile__email: str
    user_profile__full_name: str
    user_profile_id: int


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
    muted_stream_ids: List[int]
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
    deliver_at: Optional[datetime.datetime] = None
    delivery_type: Optional[str] = None
    limit_unread_user_ids: Optional[Set[int]] = None
    service_queue_events: Optional[Dict[str, List[Dict[str, Any]]]] = None
    disable_external_notifications: bool = False


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


def truncate_topic(topic: str) -> str:
    return truncate_content(topic, MAX_TOPIC_NAME_LENGTH, "...")


def messages_for_ids(
    message_ids: List[int],
    user_message_flags: Dict[int, List[str]],
    search_fields: Dict[int, Dict[str, str]],
    apply_markdown: bool,
    client_gravatar: bool,
    allow_edit_history: bool,
) -> List[Dict[str, Any]]:
    cache_transformer = MessageDict.build_dict_from_raw_db_row
    id_fetcher = lambda row: row["id"]

    message_dicts = generic_bulk_cached_fetch(
        to_dict_cache_key_id,
        MessageDict.get_raw_db_rows,
        message_ids,
        id_fetcher=id_fetcher,
        cache_transformer=cache_transformer,
        extractor=extract_message_dict,
        setter=stringify_message_dict,
    )

    message_list: List[Dict[str, Any]] = []

    for message_id in message_ids:
        msg_dict = message_dicts[message_id]
        msg_dict.update(flags=user_message_flags[message_id])
        if message_id in search_fields:
            msg_dict.update(search_fields[message_id])
        # Make sure that we never send message edit history to clients
        # in realms with allow_edit_history disabled.
        if "edit_history" in msg_dict and not allow_edit_history:
            del msg_dict["edit_history"]
        message_list.append(msg_dict)

    MessageDict.post_process_dicts(message_list, apply_markdown, client_gravatar)

    return message_list


def sew_messages_and_reactions(
    messages: List[Dict[str, Any]], reactions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Given a iterable of messages and reactions stitch reactions
    into messages.
    """
    # Add all messages with empty reaction item
    for message in messages:
        message["reactions"] = []

    # Convert list of messages into dictionary to make reaction stitching easy
    converted_messages = {message["id"]: message for message in messages}

    for reaction in reactions:
        converted_messages[reaction["message_id"]]["reactions"].append(reaction)

    return list(converted_messages.values())


def sew_messages_and_submessages(
    messages: List[Dict[str, Any]], submessages: List[Dict[str, Any]]
) -> None:
    # This is super similar to sew_messages_and_reactions.
    for message in messages:
        message["submessages"] = []

    message_dict = {message["id"]: message for message in messages}

    for submessage in submessages:
        message_id = submessage["message_id"]
        if message_id in message_dict:
            message = message_dict[message_id]
            message["submessages"].append(submessage)


def extract_message_dict(message_bytes: bytes) -> Dict[str, Any]:
    return orjson.loads(zlib.decompress(message_bytes))


def stringify_message_dict(message_dict: Dict[str, Any]) -> bytes:
    return zlib.compress(orjson.dumps(message_dict))


@cache_with_key(to_dict_cache_key, timeout=3600 * 24)
def message_to_dict_json(message: Message, realm_id: Optional[int] = None) -> bytes:
    return MessageDict.to_dict_uncached([message], realm_id)[message.id]


def save_message_rendered_content(message: Message, content: str) -> str:
    rendering_result = render_markdown(message, content, realm=message.get_realm())
    rendered_content = None
    if rendering_result is not None:
        rendered_content = rendering_result.rendered_content
    message.rendered_content = rendered_content
    message.rendered_content_version = markdown_version
    message.save_rendered_content()
    return rendered_content


class MessageDict:
    """MessageDict is the core class responsible for marshalling Message
    objects obtained from the database into a format that can be sent
    to clients via the Zulip API, whether via `GET /messages`,
    outgoing webhooks, or other code paths.  There are two core flows through
    which this class is used:

    * For just-sent messages, we construct a single `wide_dict` object
      containing all the data for the message and the related
      UserProfile models (sender_info and recipient_info); this object
      can be stored in queues, caches, etc., and then later turned
      into an API-format JSONable dictionary via finalize_payload.

    * When fetching messages from the database, we fetch their data in
      bulk using messages_for_ids, which makes use of caching, bulk
      fetches that skip the Django ORM, etc., to provide an optimized
      interface for fetching hundreds of thousands of messages from
      the database and then turning them into API-format JSON
      dictionaries.

    """

    @staticmethod
    def wide_dict(message: Message, realm_id: Optional[int] = None) -> Dict[str, Any]:
        """
        The next two lines get the cacheable field related
        to our message object, with the side effect of
        populating the cache.
        """
        json = message_to_dict_json(message, realm_id)
        obj = extract_message_dict(json)

        """
        The steps below are similar to what we do in
        post_process_dicts(), except we don't call finalize_payload(),
        since that step happens later in the queue
        processor.
        """
        MessageDict.bulk_hydrate_sender_info([obj])
        MessageDict.bulk_hydrate_recipient_info([obj])

        return obj

    @staticmethod
    def post_process_dicts(
        objs: List[Dict[str, Any]], apply_markdown: bool, client_gravatar: bool
    ) -> None:
        """
        NOTE: This function mutates the objects in
              the `objs` list, rather than making
              shallow copies.  It might be safer to
              make shallow copies here, but performance
              is somewhat important here, as we are
              often fetching hundreds of messages.
        """
        MessageDict.bulk_hydrate_sender_info(objs)
        MessageDict.bulk_hydrate_recipient_info(objs)

        for obj in objs:
            MessageDict.finalize_payload(obj, apply_markdown, client_gravatar, skip_copy=True)

    @staticmethod
    def finalize_payload(
        obj: Dict[str, Any],
        apply_markdown: bool,
        client_gravatar: bool,
        keep_rendered_content: bool = False,
        skip_copy: bool = False,
    ) -> Dict[str, Any]:
        """
        By default, we make a shallow copy of the incoming dict to avoid
        mutation-related bugs.  Code paths that are passing a unique object
        can pass skip_copy=True to avoid this extra work.
        """
        if not skip_copy:
            obj = copy.copy(obj)

        if obj["sender_email_address_visibility"] != UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
            # If email address of the sender is only available to administrators,
            # clients cannot compute gravatars, so we force-set it to false.
            # If we plumbed the current user's role, we could allow client_gravatar=True
            # here if the current user's role has access to the target user's email address.
            client_gravatar = False

        MessageDict.set_sender_avatar(obj, client_gravatar)
        if apply_markdown:
            obj["content_type"] = "text/html"
            obj["content"] = obj["rendered_content"]
        else:
            obj["content_type"] = "text/x-markdown"

        if not keep_rendered_content:
            del obj["rendered_content"]
        del obj["sender_realm_id"]
        del obj["sender_avatar_source"]
        del obj["sender_delivery_email"]
        del obj["sender_avatar_version"]

        del obj["recipient_type"]
        del obj["recipient_type_id"]
        del obj["sender_is_mirror_dummy"]
        del obj["sender_email_address_visibility"]
        return obj

    @staticmethod
    def sew_submessages_and_reactions_to_msgs(
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        msg_ids = [msg["id"] for msg in messages]
        submessages = SubMessage.get_raw_db_rows(msg_ids)
        sew_messages_and_submessages(messages, submessages)

        reactions = Reaction.get_raw_db_rows(msg_ids)
        return sew_messages_and_reactions(messages, reactions)

    @staticmethod
    def to_dict_uncached(
        messages: List[Message], realm_id: Optional[int] = None
    ) -> Dict[int, bytes]:
        messages_dict = MessageDict.to_dict_uncached_helper(messages, realm_id)
        encoded_messages = {msg["id"]: stringify_message_dict(msg) for msg in messages_dict}
        return encoded_messages

    @staticmethod
    def to_dict_uncached_helper(
        messages: List[Message], realm_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        # Near duplicate of the build_message_dict + get_raw_db_rows
        # code path that accepts already fetched Message objects
        # rather than message IDs.

        def get_rendering_realm_id(message: Message) -> int:
            # realm_id can differ among users, currently only possible
            # with cross realm bots.
            if realm_id is not None:
                return realm_id
            if message.recipient.type == Recipient.STREAM:
                return Stream.objects.get(id=message.recipient.type_id).realm_id
            return message.realm_id

        message_rows = [
            {
                "id": message.id,
                DB_TOPIC_NAME: message.topic_name(),
                "date_sent": message.date_sent,
                "last_edit_time": message.last_edit_time,
                "edit_history": message.edit_history,
                "content": message.content,
                "rendered_content": message.rendered_content,
                "rendered_content_version": message.rendered_content_version,
                "recipient_id": message.recipient.id,
                "recipient__type": message.recipient.type,
                "recipient__type_id": message.recipient.type_id,
                "rendering_realm_id": get_rendering_realm_id(message),
                "sender_id": message.sender.id,
                "sending_client__name": message.sending_client.name,
                "sender__realm_id": message.sender.realm_id,
            }
            for message in messages
        ]

        MessageDict.sew_submessages_and_reactions_to_msgs(message_rows)
        return [MessageDict.build_dict_from_raw_db_row(row) for row in message_rows]

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        # This is a special purpose function optimized for
        # callers like get_messages_backend().
        fields = [
            "id",
            DB_TOPIC_NAME,
            "date_sent",
            "last_edit_time",
            "edit_history",
            "content",
            "rendered_content",
            "rendered_content_version",
            "recipient_id",
            "recipient__type",
            "recipient__type_id",
            "sender_id",
            "sending_client__name",
            "sender__realm_id",
        ]
        # Uses index: zerver_message_pkey
        messages = Message.objects.filter(id__in=needed_ids).values(*fields)
        return MessageDict.sew_submessages_and_reactions_to_msgs(messages)

    @staticmethod
    def build_dict_from_raw_db_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        row is a row from a .values() call, and it needs to have
        all the relevant fields populated
        """
        return MessageDict.build_message_dict(
            message_id=row["id"],
            last_edit_time=row["last_edit_time"],
            edit_history_json=row["edit_history"],
            content=row["content"],
            topic_name=row[DB_TOPIC_NAME],
            date_sent=row["date_sent"],
            rendered_content=row["rendered_content"],
            rendered_content_version=row["rendered_content_version"],
            sender_id=row["sender_id"],
            sender_realm_id=row["sender__realm_id"],
            sending_client_name=row["sending_client__name"],
            rendering_realm_id=row.get("rendering_realm_id", row["sender__realm_id"]),
            recipient_id=row["recipient_id"],
            recipient_type=row["recipient__type"],
            recipient_type_id=row["recipient__type_id"],
            reactions=row["reactions"],
            submessages=row["submessages"],
        )

    @staticmethod
    def build_message_dict(
        message_id: int,
        last_edit_time: Optional[datetime.datetime],
        edit_history_json: Optional[str],
        content: str,
        topic_name: str,
        date_sent: datetime.datetime,
        rendered_content: Optional[str],
        rendered_content_version: Optional[int],
        sender_id: int,
        sender_realm_id: int,
        sending_client_name: str,
        rendering_realm_id: int,
        recipient_id: int,
        recipient_type: int,
        recipient_type_id: int,
        reactions: List[RawReactionRow],
        submessages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        obj = dict(
            id=message_id,
            sender_id=sender_id,
            content=content,
            recipient_type_id=recipient_type_id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            timestamp=datetime_to_timestamp(date_sent),
            client=sending_client_name,
        )

        obj[TOPIC_NAME] = topic_name
        obj["sender_realm_id"] = sender_realm_id

        # Render topic_links with the stream's realm instead of the
        # sender's realm; this is important for messages sent by
        # cross-realm bots like NOTIFICATION_BOT.
        obj[TOPIC_LINKS] = topic_links(rendering_realm_id, topic_name)

        if last_edit_time is not None:
            obj["last_edit_timestamp"] = datetime_to_timestamp(last_edit_time)
            assert edit_history_json is not None
            edit_history: List[EditHistoryEvent] = orjson.loads(edit_history_json)
            obj["edit_history"] = edit_history

        if Message.need_to_render_content(
            rendered_content, rendered_content_version, markdown_version
        ):
            # We really shouldn't be rendering objects in this method, but there is
            # a scenario where we upgrade the version of Markdown and fail to run
            # management commands to re-render historical messages, and then we
            # need to have side effects.  This method is optimized to not need full
            # blown ORM objects, but the Markdown renderer is unfortunately highly
            # coupled to Message, and we also need to persist the new rendered content.
            # If we don't have a message object passed in, we get one here.  The cost
            # of going to the DB here should be overshadowed by the cost of rendering
            # and updating the row.
            # TODO: see #1379 to eliminate Markdown dependencies
            message = Message.objects.select_related("sender").get(id=message_id)

            assert message is not None  # Hint for mypy.
            # It's unfortunate that we need to have side effects on the message
            # in some cases.
            rendered_content = save_message_rendered_content(message, content)

        if rendered_content is not None:
            obj["rendered_content"] = rendered_content
        else:
            obj[
                "rendered_content"
            ] = "<p>[Zulip note: Sorry, we could not understand the formatting of your message]</p>"

        if rendered_content is not None:
            obj["is_me_message"] = Message.is_status_message(content, rendered_content)
        else:
            obj["is_me_message"] = False

        obj["reactions"] = [
            ReactionDict.build_dict_from_raw_db_row(reaction) for reaction in reactions
        ]
        obj["submessages"] = submessages
        return obj

    @staticmethod
    def bulk_hydrate_sender_info(objs: List[Dict[str, Any]]) -> None:
        sender_ids = list({obj["sender_id"] for obj in objs})

        if not sender_ids:
            return

        query = UserProfile.objects.values(
            "id",
            "full_name",
            "delivery_email",
            "email",
            "realm__string_id",
            "avatar_source",
            "avatar_version",
            "is_mirror_dummy",
            "email_address_visibility",
        )

        rows = query_for_ids(query, sender_ids, "zerver_userprofile.id")

        sender_dict = {row["id"]: row for row in rows}

        for obj in objs:
            sender_id = obj["sender_id"]
            user_row = sender_dict[sender_id]
            obj["sender_full_name"] = user_row["full_name"]
            obj["sender_email"] = user_row["email"]
            obj["sender_delivery_email"] = user_row["delivery_email"]
            obj["sender_realm_str"] = user_row["realm__string_id"]
            obj["sender_avatar_source"] = user_row["avatar_source"]
            obj["sender_avatar_version"] = user_row["avatar_version"]
            obj["sender_is_mirror_dummy"] = user_row["is_mirror_dummy"]
            obj["sender_email_address_visibility"] = user_row["email_address_visibility"]

    @staticmethod
    def hydrate_recipient_info(obj: Dict[str, Any], display_recipient: DisplayRecipientT) -> None:
        """
        This method hyrdrates recipient info with things
        like full names and emails of senders.  Eventually
        our clients should be able to hyrdrate these fields
        themselves with info they already have on users.
        """

        recipient_type = obj["recipient_type"]
        recipient_type_id = obj["recipient_type_id"]
        sender_is_mirror_dummy = obj["sender_is_mirror_dummy"]
        sender_email = obj["sender_email"]
        sender_full_name = obj["sender_full_name"]
        sender_id = obj["sender_id"]

        if recipient_type == Recipient.STREAM:
            display_type = "stream"
        elif recipient_type in (Recipient.HUDDLE, Recipient.PERSONAL):
            assert not isinstance(display_recipient, str)
            display_type = "private"
            if len(display_recipient) == 1:
                # add the sender in if this isn't a message between
                # someone and themself, preserving ordering
                recip: UserDisplayRecipient = {
                    "email": sender_email,
                    "full_name": sender_full_name,
                    "id": sender_id,
                    "is_mirror_dummy": sender_is_mirror_dummy,
                }
                if recip["email"] < display_recipient[0]["email"]:
                    display_recipient = [recip, display_recipient[0]]
                elif recip["email"] > display_recipient[0]["email"]:
                    display_recipient = [display_recipient[0], recip]
        else:
            raise AssertionError(f"Invalid recipient type {recipient_type}")

        obj["display_recipient"] = display_recipient
        obj["type"] = display_type
        if obj["type"] == "stream":
            obj["stream_id"] = recipient_type_id

    @staticmethod
    def bulk_hydrate_recipient_info(objs: List[Dict[str, Any]]) -> None:
        recipient_tuples = {  # We use set to eliminate duplicate tuples.
            (
                obj["recipient_id"],
                obj["recipient_type"],
                obj["recipient_type_id"],
            )
            for obj in objs
        }
        display_recipients = bulk_fetch_display_recipients(recipient_tuples)

        for obj in objs:
            MessageDict.hydrate_recipient_info(obj, display_recipients[obj["recipient_id"]])

    @staticmethod
    def set_sender_avatar(obj: Dict[str, Any], client_gravatar: bool) -> None:
        sender_id = obj["sender_id"]
        sender_realm_id = obj["sender_realm_id"]
        sender_delivery_email = obj["sender_delivery_email"]
        sender_avatar_source = obj["sender_avatar_source"]
        sender_avatar_version = obj["sender_avatar_version"]

        obj["avatar_url"] = get_avatar_field(
            user_id=sender_id,
            realm_id=sender_realm_id,
            email=sender_delivery_email,
            avatar_source=sender_avatar_source,
            avatar_version=sender_avatar_version,
            medium=False,
            client_gravatar=client_gravatar,
        )


class ReactionDict:
    @staticmethod
    def build_dict_from_raw_db_row(row: RawReactionRow) -> Dict[str, Any]:
        return {
            "emoji_name": row["emoji_name"],
            "emoji_code": row["emoji_code"],
            "reaction_type": row["reaction_type"],
            # TODO: We plan to remove this redundant user dictionary once
            # clients are updated to support accessing use user_id.  See
            # https://github.com/zulip/zulip/pull/14711 for details.
            #
            # When we do that, we can likely update the `.values()` query to
            # not fetch the extra user_profile__* fields from the database
            # as a small performance optimization.
            "user": {
                "email": row["user_profile__email"],
                "id": row["user_profile_id"],
                "full_name": row["user_profile__full_name"],
            },
            "user_id": row["user_profile_id"],
        }


def access_message(
    user_profile: UserProfile,
    message_id: int,
    lock_message: bool = False,
) -> Tuple[Message, Optional[UserMessage]]:
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

    user_message = get_usermessage_by_message_id(user_profile, message_id)

    if has_message_access(user_profile, message, has_user_message=user_message is not None):
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
    has_user_message: bool,
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
        return has_user_message

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
        return has_user_message and is_subscribed_helper()

    # is_history_public_to_subscribers, so check if you're subscribed
    return is_subscribed_helper()


def bulk_access_messages(
    user_profile: UserProfile, messages: Collection[Message], *, stream: Optional[Stream] = None
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
        has_user_message = message.id in user_message_set
        is_subscribed = message.recipient_id in subscribed_recipient_ids
        if has_message_access(
            user_profile,
            message,
            has_user_message=has_user_message,
            stream=streams.get(message.recipient_id) if stream is None else stream,
            is_subscribed=is_subscribed,
        ):
            filtered_messages.append(message)
    return filtered_messages


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


def render_markdown(
    message: Message,
    content: str,
    realm: Optional[Realm] = None,
    realm_alert_words_automaton: Optional[ahocorasick.Automaton] = None,
    url_embed_data: Optional[Dict[str, Optional[UrlEmbedData]]] = None,
    mention_data: Optional[MentionData] = None,
    email_gateway: bool = False,
) -> MessageRenderingResult:
    """
    This is basically just a wrapper for do_render_markdown.
    """

    if realm is None:
        realm = message.get_realm()

    sender = message.sender
    sent_by_bot = sender.is_bot
    translate_emoticons = sender.translate_emoticons

    rendering_result = markdown_convert(
        content,
        realm_alert_words_automaton=realm_alert_words_automaton,
        message=message,
        message_realm=realm,
        sent_by_bot=sent_by_bot,
        translate_emoticons=translate_emoticons,
        url_embed_data=url_embed_data,
        mention_data=mention_data,
        email_gateway=email_gateway,
    )

    return rendering_result


def huddle_users(recipient_id: int) -> str:
    display_recipient: List[UserDisplayRecipient] = get_display_recipient_by_id(
        recipient_id,
        Recipient.HUDDLE,
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


def get_muted_stream_ids(user_profile: UserProfile) -> List[int]:
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
    muted_stream_ids = [row["recipient__type_id"] for row in rows]
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
    unmuted_stream_msgs: Set[int] = set()
    huddle_dict: Dict[int, RawUnreadHuddleDict] = {}
    mentions: Set[int] = set()
    total_unreads = 0

    raw_unread_messages: RawUnreadMessagesResult = dict(
        pm_dict=pm_dict,
        stream_dict=stream_dict,
        muted_stream_ids=[],
        unmuted_stream_msgs=unmuted_stream_msgs,
        huddle_dict=huddle_dict,
        mentions=mentions,
        old_unreads_missing=False,
    )

    if user_profile is None:
        return raw_unread_messages

    muted_stream_ids = get_muted_stream_ids(user_profile)
    raw_unread_messages["muted_stream_ids"] = muted_stream_ids

    topic_mute_checker = build_topic_mute_checker(user_profile)

    def is_row_muted(stream_id: int, recipient_id: int, topic: str) -> bool:
        if stream_id in muted_stream_ids:
            return True

        if topic_mute_checker(recipient_id, topic):
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
            topic = row[MESSAGE__TOPIC]
            stream_dict[message_id] = dict(
                stream_id=stream_id,
                topic=topic,
            )
            if not is_row_muted(stream_id, recipient_id, topic):
                unmuted_stream_msgs.add(message_id)

        elif msg_type == Recipient.PERSONAL:
            if sender_id == user_profile.id:
                other_user_id = row["message__recipient__type_id"]
            else:
                other_user_id = sender_id

            pm_dict[message_id] = dict(
                other_user_id=other_user_id,
            )

        elif msg_type == Recipient.HUDDLE:
            user_ids_string = get_huddle_users(recipient_id)
            huddle_dict[message_id] = dict(
                user_ids_string=user_ids_string,
            )

        # TODO: Add support for alert words here as well.
        is_mentioned = (row["flags"] & UserMessage.flags.mentioned) != 0
        is_wildcard_mentioned = (row["flags"] & UserMessage.flags.wildcard_mentioned) != 0
        if is_mentioned:
            mentions.add(message_id)
        if is_wildcard_mentioned:
            if msg_type == Recipient.STREAM:
                stream_id = row["message__recipient__type_id"]
                topic = row[MESSAGE__TOPIC]
                if not is_row_muted(stream_id, recipient_id, topic):
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
        topic = attribute_dict["topic"]
        lookup_key = (stream_id, topic)
        if lookup_key not in lookup_dict:
            obj = UnreadStreamInfo(
                stream_id=stream_id,
                topic=topic,
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
        topic = message[TOPIC_NAME]
        state["stream_dict"][message_id] = RawUnreadStreamDict(
            stream_id=stream_id,
            topic=topic,
        )

        if (
            stream_id not in state["muted_stream_ids"]
            # This next check hits the database.
            and not topic_has_visibility_policy(
                user_profile, stream_id, topic, UserTopic.VisibilityPolicy.MUTED
            )
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
    if "wildcard_mentioned" in flags and message_id in state["unmuted_stream_msgs"]:
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
    d = timezone_now() - datetime.timedelta(hours=hours)
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
    significantly complicated by the fact that for 1:1 direct
    messages, we store the message against a recipient_id of whichever
    user was the recipient, and thus for 1:1 direct messages sent
    directly to us, we need to look up the other user from the
    sender_id on those messages.  You'll see that pattern repeated
    both here and also in zerver/lib/events.py.

    Ideally, we would write these queries using Django, but even
    without the UNION ALL, that seems to not be possible, because the
    equivalent Django syntax (for the first part of this query):

        message_data = UserMessage.objects.select_related("message__recipient_id").filter(
            user_profile=user_profile,
        ).extra(
            where=[UserMessage.where_private()]
        ).order_by("-message_id")[:1000].values(
            "message__recipient_id").annotate(last_message_id=Max("message_id"))

    does not properly nest the GROUP BY (from .annotate) with the slicing.

    We return a dictionary structure for convenient modification
    below; this structure is converted into its final form by
    post_process.

    """
    RECENT_CONVERSATIONS_LIMIT = 1000

    recipient_map = {}
    my_recipient_id = user_profile.recipient_id

    query = SQL(
        """
    SELECT
        subquery.recipient_id, MAX(subquery.message_id)
    FROM (
        (SELECT
            um.message_id AS message_id,
            m.recipient_id AS recipient_id
        FROM
            zerver_usermessage um
        JOIN
            zerver_message m
        ON
            um.message_id = m.id
        WHERE
            um.user_profile_id=%(user_profile_id)s AND
            um.flags & 2048 <> 0 AND
            m.recipient_id <> %(my_recipient_id)s
        ORDER BY message_id DESC
        LIMIT %(conversation_limit)s)
        UNION ALL
        (SELECT
            m.id AS message_id,
            sender_profile.recipient_id AS recipient_id
        FROM
            zerver_message m
        JOIN
            zerver_userprofile sender_profile
        ON
            m.sender_id = sender_profile.id
        WHERE
            m.recipient_id=%(my_recipient_id)s
        ORDER BY message_id DESC
        LIMIT %(conversation_limit)s)
    ) AS subquery
    GROUP BY subquery.recipient_id
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


def wildcard_mention_allowed(sender: UserProfile, stream: Stream, realm: Realm) -> bool:
    # If there are fewer than Realm.WILDCARD_MENTION_THRESHOLD, we
    # allow sending.  In the future, we may want to make this behavior
    # a default, and also just allow explicitly setting whether this
    # applies to a stream as an override.
    if num_subscribers_for_stream_id(stream.id) <= Realm.WILDCARD_MENTION_THRESHOLD:
        return True

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


def check_user_group_mention_allowed(sender: UserProfile, user_group_ids: List[int]) -> None:
    user_groups = UserGroup.objects.filter(id__in=user_group_ids).select_related(
        "can_mention_group"
    )

    for group in user_groups:
        can_mention_group = group.can_mention_group
        if not is_user_in_group(can_mention_group, sender, direct_member_only=False):
            raise JsonableError(
                _(
                    "You are not allowed to mention user group '{user_group_name}'. You must be a member of '{can_mention_group_name}' to mention this group."
                ).format(user_group_name=group.name, can_mention_group_name=can_mention_group.name)
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


def update_to_dict_cache(
    changed_messages: List[Message], realm_id: Optional[int] = None
) -> List[int]:
    """Updates the message as stored in the to_dict cache (for serving
    messages)."""
    items_for_remote_cache = {}
    message_ids = []
    changed_messages_to_dict = MessageDict.to_dict_uncached(changed_messages, realm_id)
    for msg_id, msg in changed_messages_to_dict.items():
        message_ids.append(msg_id)
        key = to_dict_cache_key_id(msg_id)
        items_for_remote_cache[key] = (msg,)

    cache_set_many(items_for_remote_cache)
    return message_ids

import datetime
import logging
from collections import defaultdict
from dataclasses import dataclass
from email.headerregistry import Address
from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    Union,
)

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils.html import escape
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from django_stubs_ext import ValuesQuerySet

from zerver.actions.uploads import do_claim_attachments
from zerver.lib.addressee import Addressee
from zerver.lib.alert_words import get_alert_word_automaton
from zerver.lib.cache import cache_with_key, user_profile_delivery_email_cache_key
from zerver.lib.create_user import create_user
from zerver.lib.exceptions import (
    JsonableError,
    MarkdownRenderingError,
    StreamDoesNotExistError,
    StreamWithIDDoesNotExistError,
    ZephyrMessageAlreadySentError,
)
from zerver.lib.markdown import MessageRenderingResult
from zerver.lib.markdown import version as markdown_version
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.message import (
    MessageDict,
    SendMessageRequest,
    check_user_group_mention_allowed,
    normalize_body,
    render_markdown,
    truncate_topic,
    wildcard_mention_allowed,
)
from zerver.lib.muted_users import get_muting_users
from zerver.lib.notification_data import (
    UserMessageNotificationsData,
    get_user_group_mentions_data,
    user_allows_notifications_in_StreamTopic,
)
from zerver.lib.queue import queue_json_publish
from zerver.lib.recipient_users import recipient_for_user_profiles
from zerver.lib.stream_subscription import (
    get_subscriptions_for_send_message,
    num_subscribers_for_stream_id,
)
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.streams import access_stream_for_send_message, ensure_stream
from zerver.lib.string_validation import check_stream_name
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.topic import participants_for_topic
from zerver.lib.url_preview.types import UrlEmbedData
from zerver.lib.user_message import UserMessageLite, bulk_insert_ums
from zerver.lib.validator import check_widget_content
from zerver.lib.widget import do_widget_post_save_actions
from zerver.models import (
    Client,
    Message,
    NotificationTriggers,
    Realm,
    Recipient,
    Stream,
    UserMessage,
    UserPresence,
    UserProfile,
    UserTopic,
    get_client,
    get_huddle_user_ids,
    get_stream,
    get_stream_by_id_in_realm,
    get_system_bot,
    get_user_by_delivery_email,
    is_cross_realm_bot_email,
    query_for_ids,
)
from zerver.tornado.django_api import send_event


def compute_irc_user_fullname(email: str) -> str:
    return Address(addr_spec=email).username + " (IRC)"


def compute_jabber_user_fullname(email: str) -> str:
    return Address(addr_spec=email).username + " (XMPP)"


def get_user_profile_delivery_email_cache_key(
    realm: Realm, email: str, email_to_fullname: Callable[[str], str]
) -> str:
    return user_profile_delivery_email_cache_key(email, realm)


@cache_with_key(
    get_user_profile_delivery_email_cache_key,
    timeout=3600 * 24 * 7,
)
def create_mirror_user_if_needed(
    realm: Realm, email: str, email_to_fullname: Callable[[str], str]
) -> UserProfile:
    try:
        return get_user_by_delivery_email(email, realm)
    except UserProfile.DoesNotExist:
        try:
            # Forge a user for this person
            return create_user(
                email=email,
                password=None,
                realm=realm,
                full_name=email_to_fullname(email),
                active=False,
                is_mirror_dummy=True,
            )
        except IntegrityError:
            return get_user_by_delivery_email(email, realm)


def render_incoming_message(
    message: Message,
    content: str,
    realm: Realm,
    mention_data: Optional[MentionData] = None,
    url_embed_data: Optional[Dict[str, Optional[UrlEmbedData]]] = None,
    email_gateway: bool = False,
) -> MessageRenderingResult:
    realm_alert_words_automaton = get_alert_word_automaton(realm)
    try:
        rendering_result = render_markdown(
            message=message,
            content=content,
            realm=realm,
            realm_alert_words_automaton=realm_alert_words_automaton,
            mention_data=mention_data,
            url_embed_data=url_embed_data,
            email_gateway=email_gateway,
        )
    except MarkdownRenderingError:
        raise JsonableError(_("Unable to render message"))
    return rendering_result


@dataclass
class RecipientInfoResult:
    active_user_ids: Set[int]
    online_push_user_ids: Set[int]
    dm_mention_email_disabled_user_ids: Set[int]
    dm_mention_push_disabled_user_ids: Set[int]
    stream_email_user_ids: Set[int]
    stream_push_user_ids: Set[int]
    topic_wildcard_mention_user_ids: Set[int]
    stream_wildcard_mention_user_ids: Set[int]
    followed_topic_email_user_ids: Set[int]
    followed_topic_push_user_ids: Set[int]
    topic_wildcard_mention_in_followed_topic_user_ids: Set[int]
    stream_wildcard_mention_in_followed_topic_user_ids: Set[int]
    muted_sender_user_ids: Set[int]
    um_eligible_user_ids: Set[int]
    long_term_idle_user_ids: Set[int]
    default_bot_user_ids: Set[int]
    service_bot_tuples: List[Tuple[int, int]]
    all_bot_user_ids: Set[int]
    topic_participant_user_ids: Set[int]


class ActiveUserDict(TypedDict):
    id: int
    enable_online_push_notifications: bool
    enable_offline_email_notifications: bool
    enable_offline_push_notifications: bool
    long_term_idle: bool
    is_bot: bool
    bot_type: Optional[int]


def get_recipient_info(
    *,
    realm_id: int,
    recipient: Recipient,
    sender_id: int,
    stream_topic: Optional[StreamTopicTarget],
    possibly_mentioned_user_ids: AbstractSet[int] = set(),
    possible_topic_wildcard_mention: bool = True,
    possible_stream_wildcard_mention: bool = True,
) -> RecipientInfoResult:
    stream_push_user_ids: Set[int] = set()
    stream_email_user_ids: Set[int] = set()
    topic_wildcard_mention_user_ids: Set[int] = set()
    stream_wildcard_mention_user_ids: Set[int] = set()
    followed_topic_push_user_ids: Set[int] = set()
    followed_topic_email_user_ids: Set[int] = set()
    topic_wildcard_mention_in_followed_topic_user_ids: Set[int] = set()
    stream_wildcard_mention_in_followed_topic_user_ids: Set[int] = set()
    muted_sender_user_ids: Set[int] = get_muting_users(sender_id)
    topic_participant_user_ids: Set[int] = set()

    if recipient.type == Recipient.PERSONAL:
        # The sender and recipient may be the same id, so
        # de-duplicate using a set.
        message_to_user_ids: Collection[int] = list({recipient.type_id, sender_id})
        assert len(message_to_user_ids) in [1, 2]

    elif recipient.type == Recipient.STREAM:
        # Anybody calling us w/r/t a stream message needs to supply
        # stream_topic.  We may eventually want to have different versions
        # of this function for different message types.
        assert stream_topic is not None

        if possible_topic_wildcard_mention:
            # A topic participant is anyone who either sent or reacted to messages in the topic.
            # It is expensive to call `participants_for_topic` if the topic has a large number
            # of messages. But it is fine to call it here, as this gets called only if the message
            # has syntax that might be a @topic mention without having confirmed the syntax isn't, say,
            # in a code block.
            topic_participant_user_ids = participants_for_topic(
                realm_id, recipient.id, stream_topic.topic_name
            )
        subscription_rows = (
            get_subscriptions_for_send_message(
                realm_id=realm_id,
                stream_id=stream_topic.stream_id,
                topic_name=stream_topic.topic_name,
                possible_stream_wildcard_mention=possible_stream_wildcard_mention,
                topic_participant_user_ids=topic_participant_user_ids,
                possibly_mentioned_user_ids=possibly_mentioned_user_ids,
            )
            .annotate(
                user_profile_email_notifications=F(
                    "user_profile__enable_stream_email_notifications"
                ),
                user_profile_push_notifications=F("user_profile__enable_stream_push_notifications"),
                user_profile_wildcard_mentions_notify=F("user_profile__wildcard_mentions_notify"),
                followed_topic_email_notifications=F(
                    "user_profile__enable_followed_topic_email_notifications"
                ),
                followed_topic_push_notifications=F(
                    "user_profile__enable_followed_topic_push_notifications"
                ),
                followed_topic_wildcard_mentions_notify=F(
                    "user_profile__enable_followed_topic_wildcard_mentions_notify"
                ),
            )
            .values(
                "user_profile_id",
                "push_notifications",
                "email_notifications",
                "wildcard_mentions_notify",
                "followed_topic_push_notifications",
                "followed_topic_email_notifications",
                "followed_topic_wildcard_mentions_notify",
                "user_profile_email_notifications",
                "user_profile_push_notifications",
                "user_profile_wildcard_mentions_notify",
                "is_muted",
            )
            .order_by("user_profile_id")
        )

        message_to_user_ids = [row["user_profile_id"] for row in subscription_rows]
        user_id_to_visibility_policy = stream_topic.user_id_to_visibility_policy_dict()

        def notification_recipients(setting: str) -> Set[int]:
            return {
                row["user_profile_id"]
                for row in subscription_rows
                if user_allows_notifications_in_StreamTopic(
                    row["is_muted"],
                    user_id_to_visibility_policy.get(
                        row["user_profile_id"], UserTopic.VisibilityPolicy.INHERIT
                    ),
                    row[setting],
                    row["user_profile_" + setting],
                )
            }

        stream_push_user_ids = notification_recipients("push_notifications")
        stream_email_user_ids = notification_recipients("email_notifications")

        def followed_topic_notification_recipients(setting: str) -> Set[int]:
            return {
                row["user_profile_id"]
                for row in subscription_rows
                if user_id_to_visibility_policy.get(
                    row["user_profile_id"], UserTopic.VisibilityPolicy.INHERIT
                )
                == UserTopic.VisibilityPolicy.FOLLOWED
                and row["followed_topic_" + setting]
            }

        followed_topic_email_user_ids = followed_topic_notification_recipients(
            "email_notifications"
        )
        followed_topic_push_user_ids = followed_topic_notification_recipients("push_notifications")

        if possible_stream_wildcard_mention or possible_topic_wildcard_mention:
            # We calculate `wildcard_mentions_notify_user_ids` and `followed_topic_wildcard_mentions_notify_user_ids`
            # only if there's a possible stream or topic wildcard mention in the message.
            # This is important so as to avoid unnecessarily sending huge user ID lists with
            # thousands of elements to the event queue (which can happen because these settings
            # are `True` by default for new users.)
            wildcard_mentions_notify_user_ids = notification_recipients("wildcard_mentions_notify")
            followed_topic_wildcard_mentions_notify_user_ids = (
                followed_topic_notification_recipients("wildcard_mentions_notify")
            )

        if possible_stream_wildcard_mention:
            stream_wildcard_mention_user_ids = wildcard_mentions_notify_user_ids
            stream_wildcard_mention_in_followed_topic_user_ids = (
                followed_topic_wildcard_mentions_notify_user_ids
            )

        if possible_topic_wildcard_mention:
            topic_wildcard_mention_user_ids = topic_participant_user_ids.intersection(
                wildcard_mentions_notify_user_ids
            )
            topic_wildcard_mention_in_followed_topic_user_ids = (
                topic_participant_user_ids.intersection(
                    followed_topic_wildcard_mentions_notify_user_ids
                )
            )

    elif recipient.type == Recipient.HUDDLE:
        message_to_user_ids = get_huddle_user_ids(recipient)

    else:
        raise ValueError("Bad recipient type")

    message_to_user_id_set = set(message_to_user_ids)

    user_ids = set(message_to_user_id_set)
    # Important note: Because we haven't rendered Markdown yet, we
    # don't yet know which of these possibly-mentioned users was
    # actually mentioned in the message (in other words, the
    # mention syntax might have been in a code block or otherwise
    # escaped).  `get_ids_for` will filter these extra user rows
    # for our data structures not related to bots
    user_ids |= possibly_mentioned_user_ids

    if user_ids:
        query: ValuesQuerySet[UserProfile, ActiveUserDict] = UserProfile.objects.filter(
            is_active=True
        ).values(
            "id",
            "enable_online_push_notifications",
            "enable_offline_email_notifications",
            "enable_offline_push_notifications",
            "is_bot",
            "bot_type",
            "long_term_idle",
        )

        # query_for_ids is fast highly optimized for large queries, and we
        # need this codepath to be fast (it's part of sending messages)
        query = query_for_ids(
            query=query,
            user_ids=sorted(user_ids),
            field="id",
        )
        rows = list(query)
    else:
        # TODO: We should always have at least one user_id as a recipient
        #       of any message we send.  Right now the exception to this
        #       rule is `notify_new_user`, which, at least in a possibly
        #       contrived test scenario, can attempt to send messages
        #       to an inactive bot.  When we plug that hole, we can avoid
        #       this `else` clause and just `assert(user_ids)`.
        #
        # UPDATE: It's February 2020 (and a couple years after the above
        #         comment was written).  We have simplified notify_new_user
        #         so that it should be a little easier to reason about.
        #         There is currently some cleanup to how we handle cross
        #         realm bots that is still under development.  Once that
        #         effort is complete, we should be able to address this
        #         to-do.
        rows = []

    def get_ids_for(f: Callable[[ActiveUserDict], bool]) -> Set[int]:
        """Only includes users on the explicit message to line"""
        return {row["id"] for row in rows if f(row)} & message_to_user_id_set

    active_user_ids = get_ids_for(lambda r: True)
    online_push_user_ids = get_ids_for(
        lambda r: r["enable_online_push_notifications"],
    )

    # We deal with only the users who have disabled this setting, since that
    # will usually be much smaller a set than those who have enabled it (which
    # is the default)
    dm_mention_email_disabled_user_ids = get_ids_for(
        lambda r: not r["enable_offline_email_notifications"]
    )
    dm_mention_push_disabled_user_ids = get_ids_for(
        lambda r: not r["enable_offline_push_notifications"]
    )

    # Service bots don't get UserMessage rows.
    um_eligible_user_ids = get_ids_for(
        lambda r: not r["is_bot"] or r["bot_type"] not in UserProfile.SERVICE_BOT_TYPES,
    )

    long_term_idle_user_ids = get_ids_for(
        lambda r: r["long_term_idle"],
    )

    # These three bot data structures need to filter from the full set
    # of users who either are receiving the message or might have been
    # mentioned in it, and so can't use get_ids_for.
    #
    # Further in the do_send_messages code path, once
    # `mentioned_user_ids` has been computed via Markdown, we'll filter
    # these data structures for just those users who are either a
    # direct recipient or were mentioned; for now, we're just making
    # sure we have the data we need for that without extra database
    # queries.
    default_bot_user_ids = {
        row["id"] for row in rows if row["is_bot"] and row["bot_type"] == UserProfile.DEFAULT_BOT
    }

    service_bot_tuples = [
        (row["id"], row["bot_type"])
        for row in rows
        if row["is_bot"] and row["bot_type"] in UserProfile.SERVICE_BOT_TYPES
    ]

    # We also need the user IDs of all bots, to avoid trying to send push/email
    # notifications to them. This set will be directly sent to the event queue code
    # where we determine notifiability of the message for users.
    all_bot_user_ids = {row["id"] for row in rows if row["is_bot"]}

    return RecipientInfoResult(
        active_user_ids=active_user_ids,
        online_push_user_ids=online_push_user_ids,
        dm_mention_email_disabled_user_ids=dm_mention_email_disabled_user_ids,
        dm_mention_push_disabled_user_ids=dm_mention_push_disabled_user_ids,
        stream_push_user_ids=stream_push_user_ids,
        stream_email_user_ids=stream_email_user_ids,
        topic_wildcard_mention_user_ids=topic_wildcard_mention_user_ids,
        stream_wildcard_mention_user_ids=stream_wildcard_mention_user_ids,
        followed_topic_push_user_ids=followed_topic_push_user_ids,
        followed_topic_email_user_ids=followed_topic_email_user_ids,
        topic_wildcard_mention_in_followed_topic_user_ids=topic_wildcard_mention_in_followed_topic_user_ids,
        stream_wildcard_mention_in_followed_topic_user_ids=stream_wildcard_mention_in_followed_topic_user_ids,
        muted_sender_user_ids=muted_sender_user_ids,
        um_eligible_user_ids=um_eligible_user_ids,
        long_term_idle_user_ids=long_term_idle_user_ids,
        default_bot_user_ids=default_bot_user_ids,
        service_bot_tuples=service_bot_tuples,
        all_bot_user_ids=all_bot_user_ids,
        topic_participant_user_ids=topic_participant_user_ids,
    )


def get_service_bot_events(
    sender: UserProfile,
    service_bot_tuples: List[Tuple[int, int]],
    mentioned_user_ids: Set[int],
    active_user_ids: Set[int],
    recipient_type: int,
) -> Dict[str, List[Dict[str, Any]]]:
    event_dict: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # Avoid infinite loops by preventing messages sent by bots from generating
    # Service events.
    if sender.is_bot:
        return event_dict

    def maybe_add_event(user_profile_id: int, bot_type: int) -> None:
        if bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            queue_name = "outgoing_webhooks"
        elif bot_type == UserProfile.EMBEDDED_BOT:
            queue_name = "embedded_bots"
        else:
            logging.error(
                "Unexpected bot_type for Service bot id=%s: %s",
                user_profile_id,
                bot_type,
            )
            return

        is_stream = recipient_type == Recipient.STREAM

        # Important note: service_bot_tuples may contain service bots
        # who were not actually mentioned in the message (e.g. if
        # mention syntax for that bot appeared in a code block).
        # Thus, it is important to filter any users who aren't part of
        # either mentioned_user_ids (the actual mentioned users) or
        # active_user_ids (the actual recipients).
        #
        # So even though this is implied by the logic below, we filter
        # these not-actually-mentioned users here, to help keep this
        # function future-proof.
        if user_profile_id not in mentioned_user_ids and user_profile_id not in active_user_ids:
            return

        # Mention triggers, for stream messages
        if is_stream and user_profile_id in mentioned_user_ids:
            trigger = "mention"
        # Direct message triggers for personal and huddle messages
        elif not is_stream and user_profile_id in active_user_ids:
            trigger = NotificationTriggers.DIRECT_MESSAGE
        else:
            return

        event_dict[queue_name].append(
            {
                "trigger": trigger,
                "user_profile_id": user_profile_id,
            }
        )

    for user_profile_id, bot_type in service_bot_tuples:
        maybe_add_event(
            user_profile_id=user_profile_id,
            bot_type=bot_type,
        )

    return event_dict


def build_message_send_dict(
    message: Message,
    stream: Optional[Stream] = None,
    local_id: Optional[str] = None,
    sender_queue_id: Optional[str] = None,
    widget_content_dict: Optional[Dict[str, Any]] = None,
    email_gateway: bool = False,
    mention_backend: Optional[MentionBackend] = None,
    limit_unread_user_ids: Optional[Set[int]] = None,
    disable_external_notifications: bool = False,
) -> SendMessageRequest:
    """Returns a dictionary that can be passed into do_send_messages.  In
    production, this is always called by check_message, but some
    testing code paths call it directly.
    """
    realm = message.realm

    if mention_backend is None:
        mention_backend = MentionBackend(realm.id)

    mention_data = MentionData(
        mention_backend=mention_backend,
        content=message.content,
    )

    if message.is_stream_message():
        stream_id = message.recipient.type_id
        stream_topic: Optional[StreamTopicTarget] = StreamTopicTarget(
            stream_id=stream_id,
            topic_name=message.topic_name(),
        )
    else:
        stream_topic = None

    info = get_recipient_info(
        realm_id=realm.id,
        recipient=message.recipient,
        sender_id=message.sender_id,
        stream_topic=stream_topic,
        possibly_mentioned_user_ids=mention_data.get_user_ids(),
        possible_topic_wildcard_mention=mention_data.message_has_topic_wildcards(),
        possible_stream_wildcard_mention=mention_data.message_has_stream_wildcards(),
    )

    # Render our message_dicts.
    assert message.rendered_content is None

    rendering_result = render_incoming_message(
        message,
        message.content,
        realm,
        mention_data=mention_data,
        email_gateway=email_gateway,
    )
    message.rendered_content = rendering_result.rendered_content
    message.rendered_content_version = markdown_version
    links_for_embed = rendering_result.links_for_preview

    mentioned_user_groups_map = get_user_group_mentions_data(
        mentioned_user_ids=rendering_result.mentions_user_ids,
        mentioned_user_group_ids=list(rendering_result.mentions_user_group_ids),
        mention_data=mention_data,
    )

    # For single user as well as user group mentions, we set the `mentioned`
    # flag on `UserMessage`
    for group_id in rendering_result.mentions_user_group_ids:
        members = mention_data.get_group_members(group_id)
        rendering_result.mentions_user_ids.update(members)

    # Only send data to Tornado about stream or topic wildcard mentions if message
    # rendering determined the message had an actual stream or topic wildcard
    # mention in it (and not e.g. stream or topic wildcard mention syntax inside a
    # code block).
    if rendering_result.mentions_stream_wildcard:
        stream_wildcard_mention_user_ids = info.stream_wildcard_mention_user_ids
        stream_wildcard_mention_in_followed_topic_user_ids = (
            info.stream_wildcard_mention_in_followed_topic_user_ids
        )
    else:
        stream_wildcard_mention_user_ids = set()
        stream_wildcard_mention_in_followed_topic_user_ids = set()

    if rendering_result.mentions_topic_wildcard:
        topic_wildcard_mention_user_ids = info.topic_wildcard_mention_user_ids
        topic_wildcard_mention_in_followed_topic_user_ids = (
            info.topic_wildcard_mention_in_followed_topic_user_ids
        )
        topic_participant_user_ids = info.topic_participant_user_ids
    else:
        topic_wildcard_mention_user_ids = set()
        topic_wildcard_mention_in_followed_topic_user_ids = set()
        topic_participant_user_ids = set()
    """
    Once we have the actual list of mentioned ids from message
    rendering, we can patch in "default bots" (aka normal bots)
    who were directly mentioned in this message as eligible to
    get UserMessage rows.
    """
    mentioned_user_ids = rendering_result.mentions_user_ids
    default_bot_user_ids = info.default_bot_user_ids
    mentioned_bot_user_ids = default_bot_user_ids & mentioned_user_ids
    info.um_eligible_user_ids |= mentioned_bot_user_ids

    message_send_dict = SendMessageRequest(
        stream=stream,
        local_id=local_id,
        sender_queue_id=sender_queue_id,
        realm=realm,
        mention_data=mention_data,
        mentioned_user_groups_map=mentioned_user_groups_map,
        message=message,
        rendering_result=rendering_result,
        active_user_ids=info.active_user_ids,
        online_push_user_ids=info.online_push_user_ids,
        dm_mention_email_disabled_user_ids=info.dm_mention_email_disabled_user_ids,
        dm_mention_push_disabled_user_ids=info.dm_mention_push_disabled_user_ids,
        stream_push_user_ids=info.stream_push_user_ids,
        stream_email_user_ids=info.stream_email_user_ids,
        followed_topic_push_user_ids=info.followed_topic_push_user_ids,
        followed_topic_email_user_ids=info.followed_topic_email_user_ids,
        muted_sender_user_ids=info.muted_sender_user_ids,
        um_eligible_user_ids=info.um_eligible_user_ids,
        long_term_idle_user_ids=info.long_term_idle_user_ids,
        default_bot_user_ids=info.default_bot_user_ids,
        service_bot_tuples=info.service_bot_tuples,
        all_bot_user_ids=info.all_bot_user_ids,
        topic_wildcard_mention_user_ids=topic_wildcard_mention_user_ids,
        stream_wildcard_mention_user_ids=stream_wildcard_mention_user_ids,
        topic_wildcard_mention_in_followed_topic_user_ids=topic_wildcard_mention_in_followed_topic_user_ids,
        stream_wildcard_mention_in_followed_topic_user_ids=stream_wildcard_mention_in_followed_topic_user_ids,
        links_for_embed=links_for_embed,
        widget_content=widget_content_dict,
        limit_unread_user_ids=limit_unread_user_ids,
        disable_external_notifications=disable_external_notifications,
        topic_participant_user_ids=topic_participant_user_ids,
    )

    return message_send_dict


def create_user_messages(
    message: Message,
    rendering_result: MessageRenderingResult,
    um_eligible_user_ids: AbstractSet[int],
    long_term_idle_user_ids: AbstractSet[int],
    stream_push_user_ids: AbstractSet[int],
    stream_email_user_ids: AbstractSet[int],
    mentioned_user_ids: AbstractSet[int],
    followed_topic_push_user_ids: AbstractSet[int],
    followed_topic_email_user_ids: AbstractSet[int],
    mark_as_read_user_ids: Set[int],
    limit_unread_user_ids: Optional[Set[int]],
    scheduled_message_to_self: bool,
    topic_participant_user_ids: Set[int],
) -> List[UserMessageLite]:
    # These properties on the Message are set via
    # render_markdown by code in the Markdown inline patterns
    ids_with_alert_words = rendering_result.user_ids_with_alert_words
    sender_id = message.sender.id
    is_stream_message = message.is_stream_message()

    base_flags = 0
    if rendering_result.mentions_stream_wildcard:
        base_flags |= UserMessage.flags.wildcard_mentioned
    if message.recipient.type in [Recipient.HUDDLE, Recipient.PERSONAL]:
        base_flags |= UserMessage.flags.is_private

    # For long_term_idle (aka soft-deactivated) users, we are allowed
    # to optimize by lazily not creating UserMessage rows that would
    # have the default 0 flag set (since the soft-reactivation logic
    # knows how to create those when the user comes back).  We need to
    # create the UserMessage rows for these long_term_idle users
    # non-lazily in a few cases:
    #
    # * There are nonzero flags (e.g. the user was mentioned), since
    #   that case is rare and this saves a lot of complexity in
    #   soft-reactivation.
    #
    # * If the user is going to be notified (e.g. they get push/email
    #   notifications for every message on a stream), since in that
    #   case the notifications code will call `access_message` on the
    #   message to re-verify permissions, and for private streams,
    #   will get an error if the UserMessage row doesn't exist yet.
    #
    # See https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#soft-deactivation
    # for details on this system.
    user_messages = []
    for user_profile_id in um_eligible_user_ids:
        flags = base_flags
        if (
            (
                # Messages you sent from a non-API client are
                # automatically marked as read for yourself; scheduled
                # messages to yourself only are not.
                user_profile_id == sender_id
                and message.sent_by_human()
                and not scheduled_message_to_self
            )
            or user_profile_id in mark_as_read_user_ids
            or (limit_unread_user_ids is not None and user_profile_id not in limit_unread_user_ids)
        ):
            flags |= UserMessage.flags.read
        if user_profile_id in mentioned_user_ids:
            flags |= UserMessage.flags.mentioned
        if user_profile_id in ids_with_alert_words:
            flags |= UserMessage.flags.has_alert_word
        if (
            rendering_result.mentions_topic_wildcard
            and user_profile_id in topic_participant_user_ids
        ):
            flags |= UserMessage.flags.wildcard_mentioned

        if (
            user_profile_id in long_term_idle_user_ids
            and user_profile_id not in stream_push_user_ids
            and user_profile_id not in stream_email_user_ids
            and user_profile_id not in followed_topic_push_user_ids
            and user_profile_id not in followed_topic_email_user_ids
            and is_stream_message
            and int(flags) == 0
        ):
            continue

        um = UserMessageLite(
            user_profile_id=user_profile_id,
            message_id=message.id,
            flags=flags,
        )
        user_messages.append(um)

    return user_messages


def filter_presence_idle_user_ids(user_ids: Set[int]) -> List[int]:
    # Given a set of user IDs (the recipients of a message), accesses
    # the UserPresence table to determine which of these users are
    # currently idle and should potentially get email notifications
    # (and push notifications with with
    # user_profile.enable_online_push_notifications=False).

    if not user_ids:
        return []

    recent = timezone_now() - datetime.timedelta(seconds=settings.OFFLINE_THRESHOLD_SECS)
    rows = UserPresence.objects.filter(
        user_profile_id__in=user_ids,
        last_active_time__gte=recent,
    ).values("user_profile_id")
    active_user_ids = {row["user_profile_id"] for row in rows}
    idle_user_ids = user_ids - active_user_ids
    return sorted(idle_user_ids)


def get_active_presence_idle_user_ids(
    realm: Realm,
    sender_id: int,
    user_notifications_data_list: List[UserMessageNotificationsData],
) -> List[int]:
    """
    Given a list of active_user_ids, we build up a subset
    of those users who fit these criteria:

        * They are likely to receive push or email notifications.
        * They are no longer "present" according to the
          UserPresence table.
    """

    if realm.presence_disabled:
        return []

    user_ids = set()
    for user_notifications_data in user_notifications_data_list:
        # We only need to know the presence idle state for a user if this message would be notifiable
        # for them if they were indeed idle. Only including those users in the calculation below is a
        # very important optimization for open communities with many inactive users.
        if user_notifications_data.is_notifiable(sender_id, idle=True):
            user_ids.add(user_notifications_data.user_id)

    return filter_presence_idle_user_ids(user_ids)


def do_send_messages(
    send_message_requests_maybe_none: Sequence[Optional[SendMessageRequest]],
    *,
    email_gateway: bool = False,
    scheduled_message_to_self: bool = False,
    mark_as_read: Sequence[int] = [],
) -> List[int]:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """

    # Filter out messages which didn't pass internal_prep_message properly
    send_message_requests = [
        send_request
        for send_request in send_message_requests_maybe_none
        if send_request is not None
    ]

    # Save the message receipts in the database
    user_message_flags: Dict[int, Dict[int, List[str]]] = defaultdict(dict)
    with transaction.atomic():
        Message.objects.bulk_create(send_request.message for send_request in send_message_requests)

        # Claim attachments in message
        for send_request in send_message_requests:
            if do_claim_attachments(
                send_request.message, send_request.rendering_result.potential_attachment_path_ids
            ):
                send_request.message.has_attachment = True
                send_request.message.save(update_fields=["has_attachment"])

        ums: List[UserMessageLite] = []
        for send_request in send_message_requests:
            # Service bots (outgoing webhook bots and embedded bots) don't store UserMessage rows;
            # they will be processed later.
            mentioned_user_ids = send_request.rendering_result.mentions_user_ids

            # Extend the set with users who have muted the sender.
            mark_as_read_user_ids = send_request.muted_sender_user_ids
            mark_as_read_user_ids.update(mark_as_read)

            user_messages = create_user_messages(
                message=send_request.message,
                rendering_result=send_request.rendering_result,
                um_eligible_user_ids=send_request.um_eligible_user_ids,
                long_term_idle_user_ids=send_request.long_term_idle_user_ids,
                stream_push_user_ids=send_request.stream_push_user_ids,
                stream_email_user_ids=send_request.stream_email_user_ids,
                mentioned_user_ids=mentioned_user_ids,
                followed_topic_push_user_ids=send_request.followed_topic_push_user_ids,
                followed_topic_email_user_ids=send_request.followed_topic_email_user_ids,
                mark_as_read_user_ids=mark_as_read_user_ids,
                limit_unread_user_ids=send_request.limit_unread_user_ids,
                scheduled_message_to_self=scheduled_message_to_self,
                topic_participant_user_ids=send_request.topic_participant_user_ids,
            )

            for um in user_messages:
                user_message_flags[send_request.message.id][um.user_profile_id] = um.flags_list()

            ums.extend(user_messages)

            send_request.service_queue_events = get_service_bot_events(
                sender=send_request.message.sender,
                service_bot_tuples=send_request.service_bot_tuples,
                mentioned_user_ids=mentioned_user_ids,
                active_user_ids=send_request.active_user_ids,
                recipient_type=send_request.message.recipient.type,
            )

        bulk_insert_ums(ums)

        for send_request in send_message_requests:
            do_widget_post_save_actions(send_request)

    # This next loop is responsible for notifying other parts of the
    # Zulip system about the messages we just committed to the database:
    # * Notifying clients via send_event
    # * Triggering outgoing webhooks via the service event queue.
    # * Updating the `first_message_id` field for streams without any message history.
    # * Implementing the Welcome Bot reply hack
    # * Adding links to the embed_links queue for open graph processing.
    for send_request in send_message_requests:
        realm_id: Optional[int] = None
        if send_request.message.is_stream_message():
            if send_request.stream is None:
                stream_id = send_request.message.recipient.type_id
                send_request.stream = Stream.objects.select_related().get(id=stream_id)
            # assert needed because stubs for django are missing
            assert send_request.stream is not None
            realm_id = send_request.stream.realm_id

        # Deliver events to the real-time push system, as well as
        # enqueuing any additional processing triggered by the message.
        wide_message_dict = MessageDict.wide_dict(send_request.message, realm_id)

        user_flags = user_message_flags.get(send_request.message.id, {})

        """
        TODO:  We may want to limit user_ids to only those users who have
               UserMessage rows, if only for minor performance reasons.

               For now we queue events for all subscribers/sendees of the
               message, since downstream code may still do notifications
               that don't require UserMessage rows.

               Our automated tests have gotten better on this codepath,
               but we may have coverage gaps, so we should be careful
               about changing the next line.
        """
        user_ids = send_request.active_user_ids | set(user_flags.keys())
        sender_id = send_request.message.sender_id

        # We make sure the sender is listed first in the `users` list;
        # this results in the sender receiving the message first if
        # there are thousands of recipients, decreasing perceived latency.
        if sender_id in user_ids:
            user_list = [sender_id, *user_ids - {sender_id}]
        else:
            user_list = list(user_ids)

        class UserData(TypedDict):
            id: int
            flags: List[str]
            mentioned_user_group_id: Optional[int]

        users: List[UserData] = []
        for user_id in user_list:
            flags = user_flags.get(user_id, [])
            user_data: UserData = dict(id=user_id, flags=flags, mentioned_user_group_id=None)

            if user_id in send_request.mentioned_user_groups_map:
                user_data["mentioned_user_group_id"] = send_request.mentioned_user_groups_map[
                    user_id
                ]

            users.append(user_data)

        sender = send_request.message.sender
        message_type = wide_message_dict["type"]
        user_notifications_data_list = [
            UserMessageNotificationsData.from_user_id_sets(
                user_id=user_id,
                flags=user_flags.get(user_id, []),
                private_message=message_type == "private",
                disable_external_notifications=send_request.disable_external_notifications,
                online_push_user_ids=send_request.online_push_user_ids,
                dm_mention_push_disabled_user_ids=send_request.dm_mention_push_disabled_user_ids,
                dm_mention_email_disabled_user_ids=send_request.dm_mention_email_disabled_user_ids,
                stream_push_user_ids=send_request.stream_push_user_ids,
                stream_email_user_ids=send_request.stream_email_user_ids,
                topic_wildcard_mention_user_ids=send_request.topic_wildcard_mention_user_ids,
                stream_wildcard_mention_user_ids=send_request.stream_wildcard_mention_user_ids,
                followed_topic_push_user_ids=send_request.followed_topic_push_user_ids,
                followed_topic_email_user_ids=send_request.followed_topic_email_user_ids,
                topic_wildcard_mention_in_followed_topic_user_ids=send_request.topic_wildcard_mention_in_followed_topic_user_ids,
                stream_wildcard_mention_in_followed_topic_user_ids=send_request.stream_wildcard_mention_in_followed_topic_user_ids,
                muted_sender_user_ids=send_request.muted_sender_user_ids,
                all_bot_user_ids=send_request.all_bot_user_ids,
            )
            for user_id in send_request.active_user_ids
        ]

        presence_idle_user_ids = get_active_presence_idle_user_ids(
            realm=send_request.realm,
            sender_id=sender.id,
            user_notifications_data_list=user_notifications_data_list,
        )

        event = dict(
            type="message",
            message=send_request.message.id,
            message_dict=wide_message_dict,
            presence_idle_user_ids=presence_idle_user_ids,
            online_push_user_ids=list(send_request.online_push_user_ids),
            dm_mention_push_disabled_user_ids=list(send_request.dm_mention_push_disabled_user_ids),
            dm_mention_email_disabled_user_ids=list(
                send_request.dm_mention_email_disabled_user_ids
            ),
            stream_push_user_ids=list(send_request.stream_push_user_ids),
            stream_email_user_ids=list(send_request.stream_email_user_ids),
            topic_wildcard_mention_user_ids=list(send_request.topic_wildcard_mention_user_ids),
            stream_wildcard_mention_user_ids=list(send_request.stream_wildcard_mention_user_ids),
            followed_topic_push_user_ids=list(send_request.followed_topic_push_user_ids),
            followed_topic_email_user_ids=list(send_request.followed_topic_email_user_ids),
            topic_wildcard_mention_in_followed_topic_user_ids=list(
                send_request.topic_wildcard_mention_in_followed_topic_user_ids
            ),
            stream_wildcard_mention_in_followed_topic_user_ids=list(
                send_request.stream_wildcard_mention_in_followed_topic_user_ids
            ),
            muted_sender_user_ids=list(send_request.muted_sender_user_ids),
            all_bot_user_ids=list(send_request.all_bot_user_ids),
            disable_external_notifications=send_request.disable_external_notifications,
        )

        if send_request.message.is_stream_message():
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.

            # assert needed because stubs for django are missing
            assert send_request.stream is not None
            if send_request.stream.is_public():
                event["realm_id"] = send_request.stream.realm_id
                event["stream_name"] = send_request.stream.name
            if send_request.stream.invite_only:
                event["invite_only"] = True
            if send_request.stream.first_message_id is None:
                send_request.stream.first_message_id = send_request.message.id
                send_request.stream.save(update_fields=["first_message_id"])
        if send_request.local_id is not None:
            event["local_id"] = send_request.local_id
        if send_request.sender_queue_id is not None:
            event["sender_queue_id"] = send_request.sender_queue_id
        send_event(send_request.realm, event, users)

        if send_request.links_for_embed:
            event_data = {
                "message_id": send_request.message.id,
                "message_content": send_request.message.content,
                "message_realm_id": send_request.realm.id,
                "urls": list(send_request.links_for_embed),
            }
            queue_json_publish("embed_links", event_data)

        if send_request.message.recipient.type == Recipient.PERSONAL:
            welcome_bot_id = get_system_bot(settings.WELCOME_BOT, send_request.realm.id).id
            if (
                welcome_bot_id in send_request.active_user_ids
                and welcome_bot_id != send_request.message.sender_id
            ):
                from zerver.lib.onboarding import send_welcome_bot_response

                send_welcome_bot_response(send_request)

        assert send_request.service_queue_events is not None
        for queue_name, events in send_request.service_queue_events.items():
            for event in events:
                queue_json_publish(
                    queue_name,
                    {
                        "message": wide_message_dict,
                        "trigger": event["trigger"],
                        "user_profile_id": event["user_profile_id"],
                    },
                )

    return [send_request.message.id for send_request in send_message_requests]


def already_sent_mirrored_message_id(message: Message) -> Optional[int]:
    if message.recipient.type == Recipient.HUDDLE:
        # For huddle messages, we use a 10-second window because the
        # timestamps aren't guaranteed to actually match between two
        # copies of the same message.
        time_window = datetime.timedelta(seconds=10)
    else:
        time_window = datetime.timedelta(seconds=0)

    messages = Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_subject
        realm_id=message.realm_id,
        sender=message.sender,
        recipient=message.recipient,
        subject=message.topic_name(),
        content=message.content,
        sending_client=message.sending_client,
        date_sent__gte=message.date_sent - time_window,
        date_sent__lte=message.date_sent + time_window,
    )

    if messages.exists():
        return messages[0].id
    return None


def extract_stream_indicator(s: str) -> Union[str, int]:
    # Users can pass stream name as either an id or a name,
    # and if they choose to pass a name, they may JSON encode
    # it for legacy reasons.

    try:
        data = orjson.loads(s)
    except orjson.JSONDecodeError:
        # If there was no JSON encoding, then we just
        # have a raw stream name.
        return s

    # We should stop supporting this odd use case
    # once we improve our documentation.
    if isinstance(data, list):
        if len(data) != 1:  # nocoverage
            raise JsonableError(_("Expected exactly one stream"))
        data = data[0]

    if isinstance(data, str):
        # We had a JSON-encoded stream name.
        return data

    if isinstance(data, int):
        # We had a stream id.
        return data

    raise JsonableError(_("Invalid data type for stream"))


def extract_private_recipients(s: str) -> Union[List[str], List[int]]:
    # We try to accept multiple incoming formats for recipients.
    # See test_extract_recipients() for examples of what we allow.

    try:
        data = orjson.loads(s)
    except orjson.JSONDecodeError:
        data = s

    if isinstance(data, str):
        data = data.split(",")

    if not isinstance(data, list):
        raise JsonableError(_("Invalid data type for recipients"))

    if not data:
        # We don't complain about empty message recipients here
        return data

    if isinstance(data[0], str):
        return get_validated_emails(data)

    if not isinstance(data[0], int):
        raise JsonableError(_("Invalid data type for recipients"))

    return get_validated_user_ids(data)


def get_validated_user_ids(user_ids: Collection[int]) -> List[int]:
    for user_id in user_ids:
        if not isinstance(user_id, int):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(set(user_ids))


def get_validated_emails(emails: Collection[str]) -> List[str]:
    for email in emails:
        if not isinstance(email, str):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(filter(bool, {email.strip() for email in emails}))


def check_send_stream_message(
    sender: UserProfile,
    client: Client,
    stream_name: str,
    topic: str,
    body: str,
    realm: Optional[Realm] = None,
) -> int:
    addressee = Addressee.for_stream_name(stream_name, topic)
    message = check_message(sender, client, addressee, body, realm)

    return do_send_messages([message])[0]


def check_send_stream_message_by_id(
    sender: UserProfile,
    client: Client,
    stream_id: int,
    topic: str,
    body: str,
    realm: Optional[Realm] = None,
) -> int:
    addressee = Addressee.for_stream_id(stream_id, topic)
    message = check_message(sender, client, addressee, body, realm)

    return do_send_messages([message])[0]


def check_send_private_message(
    sender: UserProfile, client: Client, receiving_user: UserProfile, body: str
) -> int:
    addressee = Addressee.for_user_profile(receiving_user)
    message = check_message(sender, client, addressee, body)

    return do_send_messages([message])[0]


# check_send_message:
# Returns the id of the sent message.  Has same argspec as check_message.
def check_send_message(
    sender: UserProfile,
    client: Client,
    recipient_type_name: str,
    message_to: Union[Sequence[int], Sequence[str]],
    topic_name: Optional[str],
    message_content: str,
    realm: Optional[Realm] = None,
    forged: bool = False,
    forged_timestamp: Optional[float] = None,
    forwarder_user_profile: Optional[UserProfile] = None,
    local_id: Optional[str] = None,
    sender_queue_id: Optional[str] = None,
    widget_content: Optional[str] = None,
    *,
    skip_stream_access_check: bool = False,
) -> int:
    addressee = Addressee.legacy_build(sender, recipient_type_name, message_to, topic_name)
    try:
        message = check_message(
            sender,
            client,
            addressee,
            message_content,
            realm,
            forged,
            forged_timestamp,
            forwarder_user_profile,
            local_id,
            sender_queue_id,
            widget_content,
            skip_stream_access_check=skip_stream_access_check,
        )
    except ZephyrMessageAlreadySentError as e:
        return e.message_id
    return do_send_messages([message])[0]


def send_rate_limited_pm_notification_to_bot_owner(
    sender: UserProfile, realm: Realm, content: str
) -> None:
    """
    Sends a direct message error notification to a bot's owner if one
    hasn't already been sent in the last 5 minutes.
    """
    if sender.realm.is_zephyr_mirror_realm or sender.realm.deactivated:
        return

    if not sender.is_bot or sender.bot_owner is None:
        return

    # Don't send these notifications for cross-realm bot messages
    # (e.g. from EMAIL_GATEWAY_BOT) since the owner for
    # EMAIL_GATEWAY_BOT is probably the server administrator, not
    # the owner of the bot who could potentially fix the problem.
    if sender.realm != realm:
        return

    # We warn the user once every 5 minutes to avoid a flood of
    # direct messages on a misconfigured integration, re-using the
    # UserProfile.last_reminder field, which is not used for bots.
    last_reminder = sender.last_reminder
    waitperiod = datetime.timedelta(minutes=UserProfile.BOT_OWNER_STREAM_ALERT_WAITPERIOD)
    if last_reminder and timezone_now() - last_reminder <= waitperiod:
        return

    internal_send_private_message(
        get_system_bot(settings.NOTIFICATION_BOT, sender.bot_owner.realm_id),
        sender.bot_owner,
        content,
    )

    sender.last_reminder = timezone_now()
    sender.save(update_fields=["last_reminder"])


def send_pm_if_empty_stream(
    stream: Optional[Stream],
    realm: Realm,
    sender: UserProfile,
    stream_name: Optional[str] = None,
    stream_id: Optional[int] = None,
) -> None:
    """If a bot sends a message to a stream that doesn't exist or has no
    subscribers, sends a notification to the bot owner (if not a
    cross-realm bot) so that the owner can correct the issue."""
    if not sender.is_bot or sender.bot_owner is None:
        return

    if sender.bot_owner is not None:
        with override_language(sender.bot_owner.default_language):
            arg_dict: Dict[str, Any] = {
                "bot_identity": f"`{sender.delivery_email}`",
            }
            if stream is None:
                if stream_id is not None:
                    arg_dict = {
                        **arg_dict,
                        "stream_id": stream_id,
                    }
                    content = _(
                        "Your bot {bot_identity} tried to send a message to stream ID "
                        "{stream_id}, but there is no stream with that ID."
                    ).format(**arg_dict)
                else:
                    assert stream_name is not None
                    arg_dict = {
                        **arg_dict,
                        "stream_name": f"#**{stream_name}**",
                        "new_stream_link": "#streams/new",
                    }
                    content = _(
                        "Your bot {bot_identity} tried to send a message to stream "
                        "{stream_name}, but that stream does not exist. "
                        "Click [here]({new_stream_link}) to create it."
                    ).format(**arg_dict)
            else:
                if num_subscribers_for_stream_id(stream.id) > 0:
                    return
                arg_dict = {
                    **arg_dict,
                    "stream_name": f"#**{stream.name}**",
                }
                content = _(
                    "Your bot {bot_identity} tried to send a message to "
                    "stream {stream_name}. The stream exists but "
                    "does not have any subscribers."
                ).format(**arg_dict)

        send_rate_limited_pm_notification_to_bot_owner(sender, realm, content)


def validate_stream_name_with_pm_notification(
    stream_name: str, realm: Realm, sender: UserProfile
) -> Stream:
    stream_name = stream_name.strip()
    check_stream_name(stream_name)

    try:
        stream = get_stream(stream_name, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_name=stream_name)
        raise StreamDoesNotExistError(escape(stream_name))

    return stream


def validate_stream_id_with_pm_notification(
    stream_id: int, realm: Realm, sender: UserProfile
) -> Stream:
    try:
        stream = get_stream_by_id_in_realm(stream_id, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_id=stream_id)
        raise StreamWithIDDoesNotExistError(stream_id)

    return stream


def check_private_message_policy(
    realm: Realm, sender: UserProfile, user_profiles: Sequence[UserProfile]
) -> None:
    if realm.private_message_policy == Realm.PRIVATE_MESSAGE_POLICY_DISABLED:
        if sender.is_bot or (len(user_profiles) == 1 and user_profiles[0].is_bot):
            # We allow direct messages only between users and bots,
            # to avoid breaking the tutorial as well as automated
            # notifications from system bots to users.
            return

        raise JsonableError(_("Direct messages are disabled in this organization."))


# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(
    sender: UserProfile,
    client: Client,
    addressee: Addressee,
    message_content_raw: str,
    realm: Optional[Realm] = None,
    forged: bool = False,
    forged_timestamp: Optional[float] = None,
    forwarder_user_profile: Optional[UserProfile] = None,
    local_id: Optional[str] = None,
    sender_queue_id: Optional[str] = None,
    widget_content: Optional[str] = None,
    email_gateway: bool = False,
    *,
    skip_stream_access_check: bool = False,
    mention_backend: Optional[MentionBackend] = None,
    limit_unread_user_ids: Optional[Set[int]] = None,
    disable_external_notifications: bool = False,
) -> SendMessageRequest:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """
    stream = None

    message_content = normalize_body(message_content_raw)

    if realm is None:
        realm = sender.realm

    if addressee.is_stream():
        topic_name = addressee.topic()
        topic_name = truncate_topic(topic_name)

        stream_name = addressee.stream_name()
        stream_id = addressee.stream_id()

        if stream_name is not None:
            stream = validate_stream_name_with_pm_notification(stream_name, realm, sender)
        elif stream_id is not None:
            stream = validate_stream_id_with_pm_notification(stream_id, realm, sender)
        else:
            stream = addressee.stream()
        assert stream is not None

        # To save a database round trip, we construct the Recipient
        # object for the Stream rather than fetching it from the
        # database using the stream.recipient foreign key.
        #
        # This is simpler than ensuring that code paths that fetch a
        # Stream that will be used for sending a message have a
        # `select_related("recipient"), which would also needlessly
        # expand Stream objects in memory (all the fields of Recipient
        # are already known given the Stream object).
        recipient = Recipient(
            id=stream.recipient_id,
            type_id=stream.id,
            type=Recipient.STREAM,
        )

        if not skip_stream_access_check:
            access_stream_for_send_message(
                sender=sender, stream=stream, forwarder_user_profile=forwarder_user_profile
            )
        else:
            # Defensive assertion - the only currently supported use case
            # for this option is for outgoing webhook bots and since this
            # is security-sensitive code, it's beneficial to ensure nothing
            # else can sneak past the access check.
            assert sender.bot_type == sender.OUTGOING_WEBHOOK_BOT

        if realm.mandatory_topics and topic_name == "(no topic)":
            raise JsonableError(_("Topics are required in this organization"))

    elif addressee.is_private():
        user_profiles = addressee.user_profiles()
        mirror_message = client.name in [
            "zephyr_mirror",
            "irc_mirror",
            "jabber_mirror",
            "JabberMirror",
        ]

        check_private_message_policy(realm, sender, user_profiles)

        # API super-users who set the `forged` flag are allowed to
        # forge messages sent by any user, so we disable the
        # `forwarded_mirror_message` security check in that case.
        forwarded_mirror_message = mirror_message and not forged
        try:
            recipient = recipient_for_user_profiles(
                user_profiles, forwarded_mirror_message, forwarder_user_profile, sender
            )
        except ValidationError as e:
            assert isinstance(e.messages[0], str)
            raise JsonableError(e.messages[0])
    else:
        # This is defensive code--Addressee already validates
        # the message type.
        raise AssertionError("Invalid message type")

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    message.realm = realm
    if addressee.is_stream():
        message.set_topic_name(topic_name)
    if forged and forged_timestamp is not None:
        # Forged messages come with a timestamp
        message.date_sent = timestamp_to_datetime(forged_timestamp)
    else:
        message.date_sent = timezone_now()
    message.sending_client = client

    # We render messages later in the process.
    assert message.rendered_content is None

    if client.name == "zephyr_mirror":
        id = already_sent_mirrored_message_id(message)
        if id is not None:
            raise ZephyrMessageAlreadySentError(id)

    widget_content_dict = None
    if widget_content is not None:
        try:
            widget_content_dict = orjson.loads(widget_content)
        except orjson.JSONDecodeError:
            raise JsonableError(_("Widgets: API programmer sent invalid JSON content"))

        try:
            check_widget_content(widget_content_dict)
        except ValidationError as error:
            raise JsonableError(
                _("Widgets: {error_msg}").format(
                    error_msg=error.message,
                )
            )

    message_send_dict = build_message_send_dict(
        message=message,
        stream=stream,
        local_id=local_id,
        sender_queue_id=sender_queue_id,
        widget_content_dict=widget_content_dict,
        email_gateway=email_gateway,
        mention_backend=mention_backend,
        limit_unread_user_ids=limit_unread_user_ids,
        disable_external_notifications=disable_external_notifications,
    )

    if (
        stream is not None
        and message_send_dict.rendering_result.has_wildcard_mention()
        and not wildcard_mention_allowed(sender, stream, realm)
    ):
        raise JsonableError(
            _("You do not have permission to use wildcard mentions in this stream.")
        )

    if message_send_dict.rendering_result.mentions_user_group_ids:
        mentioned_group_ids = list(message_send_dict.rendering_result.mentions_user_group_ids)
        check_user_group_mention_allowed(sender, mentioned_group_ids)

    return message_send_dict


def _internal_prep_message(
    realm: Realm,
    sender: UserProfile,
    addressee: Addressee,
    content: str,
    *,
    email_gateway: bool = False,
    mention_backend: Optional[MentionBackend] = None,
    limit_unread_user_ids: Optional[Set[int]] = None,
    disable_external_notifications: bool = False,
) -> Optional[SendMessageRequest]:
    """
    Create a message object and checks it, but doesn't send it or save it to the database.
    The internal function that calls this can therefore batch send a bunch of created
    messages together as one database query.
    Call do_send_messages with a list of the return values of this method.
    """
    # If we have a stream name, and the stream doesn't exist, we
    # create it here (though this code path should probably be removed
    # eventually, moving that responsibility to the caller).  If
    # addressee.stream_name() is None (i.e. we're sending to a stream
    # by ID), we skip this, as the stream object must already exist.
    if addressee.is_stream():
        stream_name = addressee.stream_name()
        if stream_name is not None:
            ensure_stream(realm, stream_name, acting_user=sender)

    try:
        return check_message(
            sender,
            get_client("Internal"),
            addressee,
            content,
            realm=realm,
            email_gateway=email_gateway,
            mention_backend=mention_backend,
            limit_unread_user_ids=limit_unread_user_ids,
            disable_external_notifications=disable_external_notifications,
        )
    except JsonableError as e:
        logging.exception(
            "Error queueing internal message by %s: %s",
            sender.delivery_email,
            e.msg,
            stack_info=True,
        )

    return None


def internal_prep_stream_message(
    sender: UserProfile,
    stream: Stream,
    topic: str,
    content: str,
    *,
    email_gateway: bool = False,
    limit_unread_user_ids: Optional[Set[int]] = None,
) -> Optional[SendMessageRequest]:
    """
    See _internal_prep_message for details of how this works.
    """
    realm = stream.realm
    addressee = Addressee.for_stream(stream, topic)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
        email_gateway=email_gateway,
        limit_unread_user_ids=limit_unread_user_ids,
    )


def internal_prep_stream_message_by_name(
    realm: Realm,
    sender: UserProfile,
    stream_name: str,
    topic: str,
    content: str,
) -> Optional[SendMessageRequest]:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_stream_name(stream_name, topic)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )


def internal_prep_private_message(
    sender: UserProfile,
    recipient_user: UserProfile,
    content: str,
    *,
    mention_backend: Optional[MentionBackend] = None,
    disable_external_notifications: bool = False,
) -> Optional[SendMessageRequest]:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_user_profile(recipient_user)
    if not is_cross_realm_bot_email(recipient_user.delivery_email):
        realm = recipient_user.realm
    else:
        realm = sender.realm

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
        mention_backend=mention_backend,
        disable_external_notifications=disable_external_notifications,
    )


def internal_send_private_message(
    sender: UserProfile,
    recipient_user: UserProfile,
    content: str,
    *,
    disable_external_notifications: bool = False,
) -> Optional[int]:
    message = internal_prep_private_message(
        sender,
        recipient_user,
        content,
        disable_external_notifications=disable_external_notifications,
    )
    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]


def internal_send_stream_message(
    sender: UserProfile,
    stream: Stream,
    topic: str,
    content: str,
    *,
    email_gateway: bool = False,
    limit_unread_user_ids: Optional[Set[int]] = None,
) -> Optional[int]:
    message = internal_prep_stream_message(
        sender,
        stream,
        topic,
        content,
        email_gateway=email_gateway,
        limit_unread_user_ids=limit_unread_user_ids,
    )

    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]


def internal_send_stream_message_by_name(
    realm: Realm,
    sender: UserProfile,
    stream_name: str,
    topic: str,
    content: str,
) -> Optional[int]:
    message = internal_prep_stream_message_by_name(
        realm,
        sender,
        stream_name,
        topic,
        content,
    )

    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]


def internal_send_huddle_message(
    realm: Realm, sender: UserProfile, emails: List[str], content: str
) -> Optional[int]:
    addressee = Addressee.for_private(emails, realm)
    message = _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )
    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]

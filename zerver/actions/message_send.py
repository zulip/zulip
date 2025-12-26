import logging
from collections import defaultdict
from collections.abc import Callable, Collection, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import timedelta
from email.headerregistry import Address
from typing import Any, TypedDict, cast

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, OuterRef, Q, QuerySet
from django.utils.html import escape
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from django_stubs_ext import WithAnnotations

from zerver.actions.uploads import do_claim_attachments
from zerver.actions.user_topics import (
    bulk_do_set_user_topic_visibility_policy,
    do_set_user_topic_visibility_policy,
)
from zerver.lib.addressee import Addressee
from zerver.lib.alert_words import get_alert_word_automaton
from zerver.lib.cache import cache_with_key, user_profile_delivery_email_cache_key
from zerver.lib.create_user import create_user
from zerver.lib.exceptions import (
    DirectMessageInitiationError,
    DirectMessagePermissionError,
    JsonableError,
    MarkdownRenderingError,
    MessagesNotAllowedInEmptyTopicError,
    StreamDoesNotExistError,
    StreamWildcardMentionNotAllowedError,
    StreamWithIDDoesNotExistError,
    TopicsNotAllowedError,
    TopicWildcardMentionNotAllowedError,
)
from zerver.lib.markdown import MessageRenderingResult, render_message_markdown
from zerver.lib.markdown import version as markdown_version
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.message import (
    SendMessageRequest,
    check_user_group_mention_allowed,
    normalize_body,
    set_visibility_policy_possible,
    stream_wildcard_mention_allowed,
    topic_wildcard_mention_allowed,
    truncate_topic,
    visibility_policy_for_send_message,
)
from zerver.lib.message_cache import MessageDict
from zerver.lib.muted_users import get_muting_users
from zerver.lib.notification_data import (
    UserMessageNotificationsData,
    get_user_group_mentions_data,
    user_allows_notifications_in_StreamTopic,
)
from zerver.lib.query_helpers import query_for_ids
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.recipient_users import recipient_for_user_profiles
from zerver.lib.stream_subscription import (
    get_subscriptions_for_send_message,
    num_subscribers_for_stream_id,
)
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.streams import (
    access_stream_for_send_message,
    channel_events_topic_name,
    check_for_can_create_topic_group_violation,
    ensure_stream,
    get_stream_topics_policy,
    notify_stream_is_recently_active_update,
    subscribed_to_stream,
)
from zerver.lib.string_validation import check_stream_name
from zerver.lib.thumbnail import manifest_and_get_user_upload_previews, rewrite_thumbnailed_images
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.topic import get_topic_display_name, participants_for_topic
from zerver.lib.topic_link_util import get_fallback_markdown_link, get_stream_link_syntax
from zerver.lib.url_encoding import message_link_url
from zerver.lib.url_preview.types import UrlEmbedData
from zerver.lib.user_groups import (
    check_any_user_has_permission_by_role,
    check_user_has_permission_by_role,
    is_any_user_in_group,
    is_user_in_group,
)
from zerver.lib.user_message import UserMessageLite, bulk_insert_ums
from zerver.lib.users import (
    check_can_access_user,
    get_inaccessible_user_ids,
    get_subscribers_of_target_user_subscriptions,
    get_user_ids_who_can_access_user,
    get_users_involved_in_dms_with_target_users,
    user_access_restricted_in_realm,
)
from zerver.lib.validator import check_widget_content
from zerver.lib.widget import do_widget_post_save_actions
from zerver.models import (
    Client,
    Message,
    PushDevice,
    PushDeviceToken,
    Realm,
    Recipient,
    Stream,
    UserMessage,
    UserPresence,
    UserProfile,
    UserTopic,
)
from zerver.models.clients import get_client
from zerver.models.groups import SystemGroups, get_realm_system_groups_name_dict
from zerver.models.recipients import get_direct_message_group_user_ids
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.streams import (
    StreamTopicsPolicyEnum,
    get_stream_by_id_for_sending_message,
    get_stream_by_name_for_sending_message,
)
from zerver.models.users import get_system_bot, get_user_by_delivery_email, is_cross_realm_bot_email
from zerver.tornado.django_api import send_event_on_commit


def compute_irc_user_fullname(email: str) -> str:
    return Address(addr_spec=email).username + " (IRC)"


def compute_jabber_user_fullname(email: str) -> str:
    return Address(addr_spec=email).username + " (XMPP)"


def get_user_profile_delivery_email_cache_key(
    realm: Realm, email: str, email_to_fullname: Callable[[str], str]
) -> str:
    return user_profile_delivery_email_cache_key(email, realm.id)


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
    mention_data: MentionData | None = None,
    url_embed_data: dict[str, UrlEmbedData | None] | None = None,
    email_gateway: bool = False,
    acting_user: UserProfile | None = None,
    no_previews: bool = False,
) -> MessageRenderingResult:
    realm_alert_words_automaton = get_alert_word_automaton(realm)
    try:
        rendering_result = render_message_markdown(
            message=message,
            content=content,
            realm=realm,
            realm_alert_words_automaton=realm_alert_words_automaton,
            mention_data=mention_data,
            url_embed_data=url_embed_data,
            email_gateway=email_gateway,
            no_previews=no_previews,
            acting_user=acting_user,
        )
    except MarkdownRenderingError:
        raise JsonableError(_("Unable to render message"))
    return rendering_result


@dataclass
class RecipientInfoResult:
    active_user_ids: set[int]
    online_push_user_ids: set[int]
    dm_mention_email_disabled_user_ids: set[int]
    dm_mention_push_disabled_user_ids: set[int]
    stream_email_user_ids: set[int]
    stream_push_user_ids: set[int]
    topic_wildcard_mention_user_ids: set[int]
    stream_wildcard_mention_user_ids: set[int]
    followed_topic_email_user_ids: set[int]
    followed_topic_push_user_ids: set[int]
    topic_wildcard_mention_in_followed_topic_user_ids: set[int]
    stream_wildcard_mention_in_followed_topic_user_ids: set[int]
    muted_sender_user_ids: set[int]
    um_eligible_user_ids: set[int]
    long_term_idle_user_ids: set[int]
    default_bot_user_ids: set[int]
    service_bot_tuples: list[tuple[int, int]]
    all_bot_user_ids: set[int]
    topic_participant_user_ids: set[int]
    sender_muted_stream: bool | None
    push_device_registered_user_ids: set[int]


class ActiveUserDict(TypedDict):
    id: int
    enable_online_push_notifications: bool
    enable_offline_email_notifications: bool
    enable_offline_push_notifications: bool
    long_term_idle: bool
    is_bot: bool
    bot_type: int | None
    has_push_device_registered: bool


class UserProfileAnnotations(TypedDict):
    has_push_device_registered: bool


@dataclass
class SentMessageResult:
    message_id: int
    message_url: str | None = None
    message_link: str | None = None
    automatic_new_visibility_policy: int | None = None


def get_recipient_info(
    *,
    realm_id: int,
    recipient: Recipient,
    sender_id: int,
    stream_topic: StreamTopicTarget | None,
    possibly_mentioned_user_ids: AbstractSet[int] = set(),
    possible_topic_wildcard_mention: bool = True,
    possible_stream_wildcard_mention: bool = True,
) -> RecipientInfoResult:
    stream_push_user_ids: set[int] = set()
    stream_email_user_ids: set[int] = set()
    topic_wildcard_mention_user_ids: set[int] = set()
    stream_wildcard_mention_user_ids: set[int] = set()
    followed_topic_push_user_ids: set[int] = set()
    followed_topic_email_user_ids: set[int] = set()
    topic_wildcard_mention_in_followed_topic_user_ids: set[int] = set()
    stream_wildcard_mention_in_followed_topic_user_ids: set[int] = set()
    muted_sender_user_ids: set[int] = get_muting_users(sender_id)
    topic_participant_user_ids: set[int] = set()
    sender_muted_stream: bool | None = None

    if recipient.type == Recipient.PERSONAL:
        # The sender and recipient may be the same id, so
        # de-duplicate using a set.
        message_to_user_id_set = {recipient.type_id, sender_id}
        assert len(message_to_user_id_set) in [1, 2]

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
            # We explicitly include the sender as a topic participant because the message will
            # be actually sent at a later stage in this codepath, so `participants_for_topic`
            # misses this sender. This is useful when the sender is sending their first message
            # in the topic.
            topic_participant_user_ids.add(sender_id)
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

        message_to_user_id_set = set()
        for row in subscription_rows:
            message_to_user_id_set.add(row["user_profile_id"])
            # We store the 'sender_muted_stream' information here to avoid db query at
            # a later stage when we perform automatically unmute topic in muted stream operation.
            if row["user_profile_id"] == sender_id:
                sender_muted_stream = row["is_muted"]

        user_id_to_visibility_policy = stream_topic.user_id_to_visibility_policy_dict()

        def notification_recipients(setting: str) -> set[int]:
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

        def followed_topic_notification_recipients(setting: str) -> set[int]:
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

    elif recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        message_to_user_id_set = set(get_direct_message_group_user_ids(recipient))

    else:
        raise ValueError("Bad recipient type")

    # Important note: Because we haven't rendered Markdown yet, we
    # don't yet know which of these possibly-mentioned users was
    # actually mentioned in the message (in other words, the
    # mention syntax might have been in a code block or otherwise
    # escaped).  `get_ids_for` will filter these extra user rows
    # for our data structures not related to bots
    user_ids = message_to_user_id_set | possibly_mentioned_user_ids

    if user_ids:
        query: QuerySet[WithAnnotations[UserProfile, UserProfileAnnotations], ActiveUserDict] = (
            # We use 'cast' because django-stubs says:
            # Currently, the mypy plugin can recognize that specific names were passed to `QuerySet.annotate`
            # and include them in the type, but does not record the types of these attributes.
            #
            # The knowledge of the specific annotated fields is not yet used in creating more specific types
            # for `QuerySet`'s `values` method, however knowledge that the model was annotated _is_ used to
            # create a broader type result type for `values`, and to allow `filter`ing on any field.
            #
            # ref: https://github.com/typeddjango/django-stubs/blob/de8e0b4dd6588129f0e02f601a71486f42799533/README.md?plain=1#L263
            cast(
                "QuerySet[WithAnnotations[UserProfile, UserProfileAnnotations], ActiveUserDict]",
                UserProfile.objects.filter(is_active=True)
                .annotate(
                    # Uses index "zerver_pushdevice_user_bouncer_device_id_idx"
                    # and "zerver_pushdevicetoken_user_id_015e5dc1".
                    has_push_device_registered=Exists(
                        PushDevice.objects.filter(
                            user_id=OuterRef("id"), bouncer_device_id__isnull=False
                        )
                    )
                    | Exists(PushDeviceToken.objects.filter(user_id=OuterRef("id")))
                )
                .values(
                    "id",
                    "enable_online_push_notifications",
                    "enable_offline_email_notifications",
                    "enable_offline_push_notifications",
                    "is_bot",
                    "bot_type",
                    "long_term_idle",
                    "has_push_device_registered",
                ),
            )
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

    def get_ids_for(f: Callable[[ActiveUserDict], bool]) -> set[int]:
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

    um_eligible_user_ids = get_ids_for(lambda r: True)

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

    # Users who have at least one push device registered to receive push notifications.
    push_device_registered_user_ids = get_ids_for(lambda r: r["has_push_device_registered"])

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
        sender_muted_stream=sender_muted_stream,
        push_device_registered_user_ids=push_device_registered_user_ids,
    )


def get_service_bot_events(
    sender: UserProfile,
    service_bot_tuples: list[tuple[int, int]],
    mentioned_user_ids: set[int],
    active_user_ids: set[int],
    recipient_type: int,
) -> dict[str, list[dict[str, Any]]]:
    event_dict: dict[str, list[dict[str, Any]]] = defaultdict(list)

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
        # Direct message triggers for personal and group direct messages
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
    stream: Stream | None = None,
    local_id: str | None = None,
    sender_queue_id: str | None = None,
    widget_content_dict: dict[str, Any] | None = None,
    email_gateway: bool = False,
    mention_backend: MentionBackend | None = None,
    limit_unread_user_ids: set[int] | None = None,
    disable_external_notifications: bool = False,
    recipients_for_user_creation_events: dict[UserProfile, set[int]] | None = None,
    acting_user: UserProfile | None = None,
    no_previews: bool = False,
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
        message_sender=message.sender,
    )

    if message.is_channel_message:
        stream_id = message.recipient.type_id
        stream_topic: StreamTopicTarget | None = StreamTopicTarget(
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
        acting_user=acting_user,
        no_previews=no_previews,
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
        sender_muted_stream=info.sender_muted_stream,
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
        push_device_registered_user_ids=info.push_device_registered_user_ids,
        topic_wildcard_mention_user_ids=topic_wildcard_mention_user_ids,
        stream_wildcard_mention_user_ids=stream_wildcard_mention_user_ids,
        topic_wildcard_mention_in_followed_topic_user_ids=topic_wildcard_mention_in_followed_topic_user_ids,
        stream_wildcard_mention_in_followed_topic_user_ids=stream_wildcard_mention_in_followed_topic_user_ids,
        links_for_embed=links_for_embed,
        widget_content=widget_content_dict,
        limit_unread_user_ids=limit_unread_user_ids,
        disable_external_notifications=disable_external_notifications,
        topic_participant_user_ids=topic_participant_user_ids,
        recipients_for_user_creation_events=recipients_for_user_creation_events,
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
    mark_as_read_user_ids: set[int],
    limit_unread_user_ids: set[int] | None,
    topic_participant_user_ids: set[int],
) -> list[UserMessageLite]:
    # These properties on the Message are set via
    # render_message_markdown by code in the Markdown inline patterns
    ids_with_alert_words = rendering_result.user_ids_with_alert_words
    is_stream_message = message.is_channel_message

    base_flags = 0
    if rendering_result.mentions_stream_wildcard:
        base_flags |= UserMessage.flags.stream_wildcard_mentioned
    if message.recipient.type in [Recipient.DIRECT_MESSAGE_GROUP, Recipient.PERSONAL]:
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
        if user_profile_id in mark_as_read_user_ids or (
            limit_unread_user_ids is not None and user_profile_id not in limit_unread_user_ids
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
            flags |= UserMessage.flags.topic_wildcard_mentioned

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


def filter_presence_idle_user_ids(user_ids: set[int]) -> list[int]:
    # Given a set of user IDs (the recipients of a message), accesses
    # the UserPresence table to determine which of these users are
    # currently idle and should potentially get email notifications
    # (and push notifications with with
    # user_profile.enable_online_push_notifications=False).

    if not user_ids:
        return []

    recent = timezone_now() - timedelta(seconds=settings.OFFLINE_THRESHOLD_SECS)
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
    user_notifications_data_list: list[UserMessageNotificationsData],
) -> list[int]:
    """
    Given a list of active_user_ids, we build up a subset
    of those users who fit these criteria:

        * They are likely to receive push or email notifications.
        * They are no longer "present" according to the
          UserPresence table.
    """

    if realm.presence_disabled:  # nocoverage
        return []

    user_ids = set()
    for user_notifications_data in user_notifications_data_list:
        # We only need to know the presence idle state for a user if this message would be notifiable
        # for them if they were indeed idle. Only including those users in the calculation below is a
        # very important optimization for open communities with many inactive users.
        if user_notifications_data.is_notifiable(sender_id, idle=True):
            user_ids.add(user_notifications_data.user_id)

    return filter_presence_idle_user_ids(user_ids)


@transaction.atomic(savepoint=False)
def do_send_messages(
    send_message_requests_maybe_none: Sequence[SendMessageRequest | None],
    *,
    mark_as_read: Sequence[int] = [],
) -> list[SentMessageResult]:
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
    user_message_flags: dict[int, dict[int, list[str]]] = defaultdict(dict)

    Message.objects.bulk_create(send_request.message for send_request in send_message_requests)

    # Claim attachments in message
    for send_request in send_message_requests:
        if do_claim_attachments(
            send_request.message, send_request.rendering_result.potential_attachment_path_ids
        ):
            send_request.message.has_attachment = True
            update_fields = ["has_attachment"]

            # Lock the ImageAttachment rows that we pulled when rendering
            # outside of the transaction; they may be out of date now, and we
            # need to post-process the rendered_content to swap out the
            # spinner.  We would ideally take a `FOR SHARE` lock here
            # (https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS),
            # which would block UPDATEs but not other `FOR SHARE`, but Django
            # does not support this yet: (https://code.djangoproject.com/ticket/10088)
            assert send_request.message.rendered_content is not None
            if send_request.rendering_result.thumbnail_spinners:
                previews = manifest_and_get_user_upload_previews(
                    send_request.message.realm_id,
                    send_request.message.content,
                    lock=True,
                    enqueue=False,
                    path_ids=list(send_request.rendering_result.thumbnail_spinners),
                ).image_metadata
                new_rendered_content = rewrite_thumbnailed_images(
                    send_request.message.rendered_content, previews
                )[0]
                if new_rendered_content is not None:
                    send_request.message.rendered_content = new_rendered_content
                    update_fields.append("rendered_content")

            send_request.message.save(update_fields=update_fields)

    ums: list[UserMessageLite] = []
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
    # * Sender automatically follows or unmutes the topic depending on 'automatically_follow_topics_policy'
    #   and 'automatically_unmute_topics_in_muted_streams_policy' user settings.
    # * Notifying clients via send_event_on_commit
    # * Triggering outgoing webhooks via the service event queue.
    # * Updating the `first_message_id` field for streams without any message history.
    # * Implementing the Welcome Bot reply hack
    # * Adding links to the embed_links queue for open graph processing.
    for send_request in send_message_requests:
        realm_id: int | None = None
        if send_request.message.is_channel_message:
            if send_request.stream is None:
                stream_id = send_request.message.recipient.type_id
                send_request.stream = Stream.objects.get(id=stream_id)
            # assert needed because stubs for django are missing
            assert send_request.stream is not None
            realm_id = send_request.stream.realm_id
            sender = send_request.message.sender

            # Determine and set the visibility_policy depending on 'automatically_follow_topics_policy'
            # and 'automatically_unmute_topics_in_muted_streams_policy'.
            if set_visibility_policy_possible(sender, send_request.message) and not (
                sender.automatically_follow_topics_policy
                == sender.automatically_unmute_topics_in_muted_streams_policy
                == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ):
                try:
                    user_topic = UserTopic.objects.get(
                        user_profile=sender,
                        stream_id=send_request.stream.id,
                        topic_name__iexact=send_request.message.topic_name(),
                    )
                    visibility_policy = user_topic.visibility_policy
                except UserTopic.DoesNotExist:
                    visibility_policy = UserTopic.VisibilityPolicy.INHERIT

                new_visibility_policy = visibility_policy_for_send_message(
                    sender,
                    send_request.message,
                    send_request.stream,
                    send_request.sender_muted_stream,
                    visibility_policy,
                )
                if new_visibility_policy:
                    do_set_user_topic_visibility_policy(
                        user_profile=sender,
                        stream=send_request.stream,
                        topic_name=send_request.message.topic_name(),
                        visibility_policy=new_visibility_policy,
                    )
                    send_request.automatic_new_visibility_policy = new_visibility_policy

            # Set the visibility_policy of the users mentioned in the message
            # to "FOLLOWED" if "automatically_follow_topics_where_mentioned" is "True".
            human_user_personal_mentions = send_request.rendering_result.mentions_user_ids & (
                send_request.active_user_ids - send_request.all_bot_user_ids
            )
            expect_follow_user_profiles: set[UserProfile] = set()

            if len(human_user_personal_mentions) > 0:
                expect_follow_user_profiles = set(
                    UserProfile.objects.filter(
                        realm_id=realm_id,
                        id__in=human_user_personal_mentions,
                        automatically_follow_topics_where_mentioned=True,
                    )
                )
            if len(expect_follow_user_profiles) > 0:
                user_topics_query_set = UserTopic.objects.filter(
                    user_profile__in=expect_follow_user_profiles,
                    stream_id=send_request.stream.id,
                    topic_name__iexact=send_request.message.topic_name(),
                    visibility_policy__in=[
                        # Explicitly muted takes precedence over this setting.
                        UserTopic.VisibilityPolicy.MUTED,
                        # Already followed
                        UserTopic.VisibilityPolicy.FOLLOWED,
                    ],
                )
                skip_follow_users = {
                    user_topic.user_profile for user_topic in user_topics_query_set
                }

                to_follow_users = list(expect_follow_user_profiles - skip_follow_users)

                if to_follow_users:
                    bulk_do_set_user_topic_visibility_policy(
                        user_profiles=to_follow_users,
                        stream=send_request.stream,
                        topic_name=send_request.message.topic_name(),
                        visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
                    )

        wide_message_dict = MessageDict.wide_dict(send_request.message, realm_id)

        # Compute URL of the message.
        send_request.message_url = message_link_url(send_request.realm, wide_message_dict)
        if send_request.stream:
            send_request.message_link = get_fallback_markdown_link(
                send_request.stream.id,
                send_request.stream.name,
                send_request.message.topic_name(),
                send_request.message.id,
            )
        else:
            # There is no special Zulip markdown syntax for direct message URLs.
            send_request.message_link = send_request.message_url

        # Deliver events to the real-time push system, as well as
        # enqueuing any additional processing triggered by the message.
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
            flags: list[str]
            mentioned_user_group_id: int | None

        users: list[UserData] = []
        for user_id in user_list:
            flags = user_flags.get(user_id, [])
            # TODO/compatibility: The `wildcard_mentioned` flag was deprecated in favor of
            # the `stream_wildcard_mentioned` and `topic_wildcard_mentioned` flags.  The
            # `wildcard_mentioned` flag exists for backwards-compatibility with older
            # clients.  Remove this when we no longer support legacy clients that have not
            # been updated to access `stream_wildcard_mentioned`.
            if "stream_wildcard_mentioned" in flags or "topic_wildcard_mentioned" in flags:
                flags.append("wildcard_mentioned")
            user_data: UserData = dict(id=user_id, flags=flags, mentioned_user_group_id=None)

            if user_id in send_request.mentioned_user_groups_map:
                user_data["mentioned_user_group_id"] = send_request.mentioned_user_groups_map[
                    user_id
                ]

            users.append(user_data)

        sender = send_request.message.sender
        recipient_type = wide_message_dict["type"]
        user_notifications_data_list = [
            UserMessageNotificationsData.from_user_id_sets(
                user_id=user_id,
                flags=user_flags.get(user_id, []),
                private_message=recipient_type == "private",
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
                push_device_registered_user_ids=send_request.push_device_registered_user_ids,
            )
            for user_id in send_request.active_user_ids
        ]

        presence_idle_user_ids = get_active_presence_idle_user_ids(
            realm=send_request.realm,
            sender_id=sender.id,
            user_notifications_data_list=user_notifications_data_list,
        )

        if send_request.recipients_for_user_creation_events is not None:
            from zerver.actions.create_user import notify_created_user

            for (
                new_accessible_user,
                notify_user_ids,
            ) in send_request.recipients_for_user_creation_events.items():
                notify_created_user(new_accessible_user, list(notify_user_ids))

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
            push_device_registered_user_ids=list(send_request.push_device_registered_user_ids),
            disable_external_notifications=send_request.disable_external_notifications,
            realm_host=send_request.realm.host,
        )

        if send_request.message.is_channel_message:
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.

            # assert needed because stubs for django are missing
            assert send_request.stream is not None
            stream_update_fields = []
            if send_request.stream.is_public():
                event["realm_id"] = send_request.stream.realm_id
                event["stream_name"] = send_request.stream.name
            if send_request.stream.invite_only:
                event["invite_only"] = True
            if send_request.stream.first_message_id is None:
                send_request.stream.first_message_id = send_request.message.id
                stream_update_fields.append("first_message_id")
            if not send_request.stream.is_recently_active:
                send_request.stream.is_recently_active = True
                stream_update_fields.append("is_recently_active")
                notify_stream_is_recently_active_update(send_request.stream, True)

            if len(stream_update_fields) > 0:
                send_request.stream.save(update_fields=stream_update_fields)

            # Performance note: This check can theoretically do
            # database queries in a loop if many messages are being
            # sent via a single do_send_messages call.
            #
            # This is not a practical concern at present, because our
            # only use case for bulk-sending messages via this API
            # endpoint is for direct messages bulk-sent by system
            # bots; and for system bots,
            # "user_access_restricted_in_realm" will always return
            # False without doing any database queries at all.
            if user_access_restricted_in_realm(
                send_request.message.sender
            ) and not subscribed_to_stream(send_request.message.sender, send_request.stream.id):
                user_ids_who_can_access_sender = get_user_ids_who_can_access_user(
                    send_request.message.sender
                )
                user_ids_receiving_event = {user["id"] for user in users}
                user_ids_without_access_to_sender = user_ids_receiving_event - set(
                    user_ids_who_can_access_sender
                )
                event["user_ids_without_access_to_sender"] = list(user_ids_without_access_to_sender)

        if send_request.local_id is not None:
            event["local_id"] = send_request.local_id
        if send_request.sender_queue_id is not None:
            event["sender_queue_id"] = send_request.sender_queue_id
        send_event_on_commit(send_request.realm, event, users)

        if send_request.links_for_embed:
            event_data = {
                "message_id": send_request.message.id,
                "message_content": send_request.message.content,
                "message_realm_id": send_request.realm.id,
                "urls": list(send_request.links_for_embed),
            }
            queue_event_on_commit("embed_links", event_data)

        # Check if this is a 1:1 DM between a user and the Welcome Bot,
        # in which case we may want to send an automated response.
        if not send_request.message.is_channel_message and len(send_request.active_user_ids) == 2:
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
                queue_event_on_commit(
                    queue_name,
                    {
                        "message": wide_message_dict,
                        "trigger": event["trigger"],
                        "user_profile_id": event["user_profile_id"],
                    },
                )

    sent_message_results = [
        SentMessageResult(
            message_id=send_request.message.id,
            message_url=send_request.message_url,
            message_link=send_request.message_link,
            automatic_new_visibility_policy=send_request.automatic_new_visibility_policy,
        )
        for send_request in send_message_requests
    ]
    return sent_message_results


def extract_stream_indicator(s: str) -> str | int:
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
            raise JsonableError(_("Expected exactly one channel"))
        data = data[0]

    if isinstance(data, str):
        # We had a JSON-encoded stream name.
        return data

    if isinstance(data, int):
        # We had a stream id.
        return data

    raise JsonableError(_("Invalid data type for channel"))


def extract_private_recipients(s: str) -> list[str] | list[int]:
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


def get_validated_user_ids(user_ids: Collection[int]) -> list[int]:
    for user_id in user_ids:
        if not isinstance(user_id, int):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(set(user_ids))


def get_validated_emails(emails: Collection[str]) -> list[str]:
    for email in emails:
        if not isinstance(email, str):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(filter(bool, {email.strip() for email in emails}))


def check_send_stream_message(
    sender: UserProfile,
    client: Client,
    stream_name: str,
    topic_name: str,
    body: str,
    *,
    realm: Realm | None = None,
    read_by_sender: bool = False,
    no_previews: bool = False,
) -> int:
    addressee = Addressee.for_stream_name(stream_name, topic_name)
    message_request = check_message(sender, client, addressee, body, realm, no_previews=no_previews)
    sent_message_result = do_send_messages(
        [message_request], mark_as_read=[sender.id] if read_by_sender else []
    )[0]
    return sent_message_result.message_id


def check_send_stream_message_by_id(
    sender: UserProfile,
    client: Client,
    stream_id: int,
    topic_name: str,
    body: str,
    realm: Realm | None = None,
    no_previews: bool = False,
) -> int:
    addressee = Addressee.for_stream_id(stream_id, topic_name)
    message_request = check_message(sender, client, addressee, body, realm, no_previews=no_previews)
    sent_message_result = do_send_messages([message_request])[0]
    return sent_message_result.message_id


def check_send_private_message(
    sender: UserProfile,
    client: Client,
    receiving_user: UserProfile,
    body: str,
    no_previews: bool = False,
) -> int:
    addressee = Addressee.for_user_profile(receiving_user)
    message_request = check_message(sender, client, addressee, body, no_previews=no_previews)
    sent_message_result = do_send_messages([message_request])[0]
    return sent_message_result.message_id


# check_send_message:
# Returns the id of the sent message.  Has same argspec as check_message.
def check_send_message(
    sender: UserProfile,
    client: Client,
    recipient_type_name: str,
    message_to: Sequence[int] | Sequence[str],
    topic_name: str | None,
    message_content: str,
    realm: Realm | None = None,
    forged: bool = False,
    forged_timestamp: float | None = None,
    forwarder_user_profile: UserProfile | None = None,
    local_id: str | None = None,
    sender_queue_id: str | None = None,
    widget_content: str | None = None,
    *,
    skip_stream_access_check: bool = False,
    read_by_sender: bool = False,
) -> SentMessageResult:
    addressee = Addressee.legacy_build(sender, recipient_type_name, message_to, topic_name)
    message_request = check_message(
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
    return do_send_messages(
        [message_request],
        mark_as_read=[sender.id] if read_by_sender else [],
    )[0]


def send_rate_limited_pm_notification_to_bot_owner(
    sender: UserProfile, realm: Realm, content: str
) -> None:
    """
    Sends a direct message error notification to a bot's owner if one
    hasn't already been sent in the last 5 minutes.
    """
    if sender.realm.deactivated:
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
    # direct messages on a misconfigured integration, reusing the
    # UserProfile.last_reminder field, which is not used for bots.
    last_reminder = sender.last_reminder
    waitperiod = timedelta(minutes=UserProfile.BOT_OWNER_STREAM_ALERT_WAITPERIOD)
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
    stream: Stream | None,
    realm: Realm,
    sender: UserProfile,
    stream_name: str | None = None,
    stream_id: int | None = None,
) -> None:
    """If a bot sends a message to a stream that doesn't exist or has no
    subscribers, sends a notification to the bot owner (if not a
    cross-realm bot) so that the owner can correct the issue."""
    if not sender.is_bot or sender.bot_owner is None:
        return

    if sender.bot_owner is not None:
        with override_language(sender.bot_owner.default_language):
            arg_dict: dict[str, Any] = {
                "bot_identity": f"`{sender.delivery_email}`",
            }
            if stream is None:
                if stream_id is not None:
                    arg_dict = {
                        **arg_dict,
                        "channel_id": stream_id,
                    }
                    content = _(
                        "Your bot {bot_identity} tried to send a message to channel ID "
                        "{channel_id}, but there is no channel with that ID."
                    ).format(**arg_dict)
                else:
                    assert stream_name is not None
                    arg_dict = {
                        **arg_dict,
                        "channel_name": f"#**{stream_name}**",
                        "new_channel_link": "#channels/new",
                    }
                    content = _(
                        "Your bot {bot_identity} tried to send a message to channel "
                        "{channel_name}, but that channel does not exist. "
                        "Click [here]({new_channel_link}) to create it."
                    ).format(**arg_dict)
            else:
                if num_subscribers_for_stream_id(stream.id) > 0:
                    return
                arg_dict = {
                    **arg_dict,
                    "channel_name": f"{get_stream_link_syntax(stream.id, stream.name)}",
                }
                content = _(
                    "Your bot {bot_identity} tried to send a message to "
                    "channel {channel_name}. The channel exists but "
                    "does not have any subscribers."
                ).format(**arg_dict)

        send_rate_limited_pm_notification_to_bot_owner(sender, realm, content)


def validate_stream_name_with_pm_notification(
    stream_name: str, realm: Realm, sender: UserProfile
) -> Stream:
    stream_name = stream_name.strip()
    check_stream_name(stream_name)

    try:
        stream = get_stream_by_name_for_sending_message(stream_name, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_name=stream_name)
        raise StreamDoesNotExistError(escape(stream_name))

    return stream


def validate_stream_id_with_pm_notification(
    stream_id: int, realm: Realm, sender: UserProfile
) -> Stream:
    try:
        stream = get_stream_by_id_for_sending_message(stream_id, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_id=stream_id)
        raise StreamWithIDDoesNotExistError(stream_id)

    return stream


def check_can_send_direct_message(
    realm: Realm, sender: UserProfile, recipient_users: Sequence[UserProfile], recipient: Recipient
) -> None:
    if sender.is_bot:
        return

    if all(user_profile.is_bot or user_profile.id == sender.id for user_profile in recipient_users):
        return

    system_groups_name_dict = get_realm_system_groups_name_dict(realm.id)
    if realm.direct_message_permission_group_id in system_groups_name_dict:
        users = set(recipient_users) | {sender}
        if not check_any_user_has_permission_by_role(
            users, realm.direct_message_permission_group_id, system_groups_name_dict
        ):
            is_nobody_group = (
                system_groups_name_dict[realm.direct_message_permission_group_id]
                == SystemGroups.NOBODY
            )
            raise DirectMessagePermissionError(is_nobody_group)
    else:
        user_ids = {recipient_user.id for recipient_user in recipient_users} | {sender.id}
        if not is_any_user_in_group(realm.direct_message_permission_group_id, user_ids):
            raise DirectMessagePermissionError(is_nobody_group=False)

    if realm.direct_message_initiator_group_id in system_groups_name_dict:
        if check_user_has_permission_by_role(
            sender, realm.direct_message_initiator_group_id, system_groups_name_dict
        ):
            return
    else:
        if is_user_in_group(realm.direct_message_initiator_group_id, sender):
            return

    # TODO: This check is inefficient; we should in the future be able to cache
    # on the Huddle object whether the conversation already exists, likely in the
    # form of a `first_message_id` field, and be able to save doing this check in the
    # common case that this is not the first message in a conversation.
    if recipient.type == Recipient.PERSONAL:
        recipient_user_profile = recipient_users[0]
        previous_messages_exist = (
            Message.objects.filter(
                realm=realm,
                recipient__type=Recipient.PERSONAL,
            )
            .filter(
                Q(sender=sender, recipient=recipient)
                | Q(sender=recipient_user_profile, recipient_id=sender.recipient_id)
            )
            .exists()
        )
    else:
        assert recipient.type == Recipient.DIRECT_MESSAGE_GROUP
        previous_messages_exist = Message.objects.filter(
            realm=realm,
            recipient=recipient,
        ).exists()
    if not previous_messages_exist:
        raise DirectMessageInitiationError


def check_sender_can_access_recipients(
    realm: Realm, sender: UserProfile, user_profiles: Sequence[UserProfile]
) -> None:
    recipient_user_ids = [user.id for user in user_profiles]
    inaccessible_recipients = get_inaccessible_user_ids(recipient_user_ids, sender)

    if inaccessible_recipients:
        raise JsonableError(_("You do not have permission to access some of the recipients."))


def get_recipients_for_user_creation_events(
    realm: Realm, sender: UserProfile, user_profiles: Sequence[UserProfile]
) -> dict[UserProfile, set[int]]:
    """
    This function returns a dictionary with data about which users would
    receive stream creation events due to gaining access to a user.
    The key of the dictionary is a user object and the value is a set of
    user_ids that would gain access to that user.
    """
    recipients_for_user_creation_events: dict[UserProfile, set[int]] = defaultdict(set)

    # If none of the users in the direct message conversation are
    # guests, then there is no possible can_access_all_users_group
    # policy that would mean sending this message changes any user's
    # user access to other users.
    guest_recipients = [user for user in user_profiles if user.is_guest]
    if len(guest_recipients) == 0:
        return recipients_for_user_creation_events

    if not user_access_restricted_in_realm(sender):
        return recipients_for_user_creation_events

    if len(user_profiles) == 1:
        if not check_can_access_user(sender, user_profiles[0]):
            recipients_for_user_creation_events[sender].add(user_profiles[0].id)
        return recipients_for_user_creation_events

    users_involved_in_dms = get_users_involved_in_dms_with_target_users(guest_recipients, realm)
    subscribers_of_guest_recipient_subscriptions = get_subscribers_of_target_user_subscriptions(
        guest_recipients
    )

    for recipient_user in guest_recipients:
        for user in user_profiles:
            if user.id == recipient_user.id or user.is_bot:
                continue

            if (
                user.id not in users_involved_in_dms[recipient_user.id]
                and user.id not in subscribers_of_guest_recipient_subscriptions[recipient_user.id]
            ):
                recipients_for_user_creation_events[user].add(recipient_user.id)

        if (
            not sender.is_bot
            and sender.id not in users_involved_in_dms[recipient_user.id]
            and sender.id not in subscribers_of_guest_recipient_subscriptions[recipient_user.id]
        ):
            recipients_for_user_creation_events[sender].add(recipient_user.id)

    return recipients_for_user_creation_events


# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(
    sender: UserProfile,
    client: Client,
    addressee: Addressee,
    message_content_raw: str,
    realm: Realm | None = None,
    forged: bool = False,
    forged_timestamp: float | None = None,
    forwarder_user_profile: UserProfile | None = None,
    local_id: str | None = None,
    sender_queue_id: str | None = None,
    widget_content: str | None = None,
    email_gateway: bool = False,
    *,
    skip_stream_access_check: bool = False,
    message_type: int = Message.MessageType.NORMAL,
    mention_backend: MentionBackend | None = None,
    limit_unread_user_ids: set[int] | None = None,
    disable_external_notifications: bool = False,
    archived_channel_notice: bool = False,
    no_previews: bool = False,
    acting_user: UserProfile | None = None,
) -> SendMessageRequest:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """
    stream = None

    message_content = normalize_body(message_content_raw)

    if realm is None:
        realm = sender.realm

    recipients_for_user_creation_events = None
    if addressee.is_stream():
        topic_name = addressee.topic_name()
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
                sender=sender,
                stream=stream,
                forwarder_user_profile=forwarder_user_profile,
                archived_channel_notice=archived_channel_notice,
            )
        else:
            # Defensive assertion - the only currently supported use case
            # for this option is for outgoing webhook bots and since this
            # is security-sensitive code, it's beneficial to ensure nothing
            # else can sneak past the access check.
            assert sender.bot_type == sender.OUTGOING_WEBHOOK_BOT

        check_for_can_create_topic_group_violation(
            user_profile=sender, stream=stream, topic_name=topic_name
        )

        topics_policy = get_stream_topics_policy(realm, stream)
        empty_topic_display_name = get_topic_display_name("", sender.default_language)
        if topics_policy == StreamTopicsPolicyEnum.disable_empty_topic.value and topic_name == "":
            raise MessagesNotAllowedInEmptyTopicError(empty_topic_display_name)

        if topics_policy == StreamTopicsPolicyEnum.empty_topic_only.value and topic_name != "":
            raise TopicsNotAllowedError(empty_topic_display_name)

    elif addressee.is_private():
        user_profiles = addressee.user_profiles()
        mirror_message = client.name in [
            "irc_mirror",
            "jabber_mirror",
            "JabberMirror",
        ]

        check_sender_can_access_recipients(realm, sender, user_profiles)

        recipients_for_user_creation_events = get_recipients_for_user_creation_events(
            realm, sender, user_profiles
        )

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

        check_can_send_direct_message(realm, sender, user_profiles, recipient)
    else:
        # This is defensive code--Addressee already validates
        # the message type.
        raise AssertionError("Invalid message type")

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    message.type = message_type
    message.realm = realm
    if addressee.is_stream():
        message.set_topic_name(topic_name)
        message.is_channel_message = True
    else:
        message.set_topic_name(Message.DM_TOPIC)
        message.is_channel_message = False
    if forged and forged_timestamp is not None:
        # Forged messages come with a timestamp
        message.date_sent = timestamp_to_datetime(forged_timestamp)
    else:
        message.date_sent = timezone_now()
    message.sending_client = client

    # We render messages later in the process.
    assert message.rendered_content is None

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
        recipients_for_user_creation_events=recipients_for_user_creation_events,
        acting_user=acting_user,
        no_previews=no_previews,
    )

    if (
        stream is not None
        and message_send_dict.rendering_result.mentions_stream_wildcard
        and not stream_wildcard_mention_allowed(sender, stream, realm)
    ):
        raise StreamWildcardMentionNotAllowedError

    topic_participant_count = len(message_send_dict.topic_participant_user_ids)
    if (
        stream is not None
        and message_send_dict.rendering_result.mentions_topic_wildcard
        and not topic_wildcard_mention_allowed(sender, topic_participant_count, realm)
    ):
        raise TopicWildcardMentionNotAllowedError

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
    message_type: int = Message.MessageType.NORMAL,
    mention_backend: MentionBackend | None = None,
    limit_unread_user_ids: set[int] | None = None,
    disable_external_notifications: bool = False,
    forged: bool = False,
    forged_timestamp: float | None = None,
    archived_channel_notice: bool = False,
    acting_user: UserProfile | None = None,
) -> SendMessageRequest | None:
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
            message_type=message_type,
            mention_backend=mention_backend,
            limit_unread_user_ids=limit_unread_user_ids,
            disable_external_notifications=disable_external_notifications,
            forged=forged,
            forged_timestamp=forged_timestamp,
            archived_channel_notice=archived_channel_notice,
            acting_user=acting_user,
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
    topic_name: str,
    content: str,
    *,
    email_gateway: bool = False,
    message_type: int = Message.MessageType.NORMAL,
    limit_unread_user_ids: set[int] | None = None,
    forged: bool = False,
    forged_timestamp: float | None = None,
    archived_channel_notice: bool = False,
    acting_user: UserProfile | None = None,
) -> SendMessageRequest | None:
    """
    See _internal_prep_message for details of how this works.
    """
    realm = stream.realm
    addressee = Addressee.for_stream(stream, topic_name)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
        email_gateway=email_gateway,
        message_type=message_type,
        limit_unread_user_ids=limit_unread_user_ids,
        forged=forged,
        forged_timestamp=forged_timestamp,
        archived_channel_notice=archived_channel_notice,
        acting_user=acting_user,
    )


def internal_prep_stream_message_by_name(
    realm: Realm,
    sender: UserProfile,
    stream_name: str,
    topic_name: str,
    content: str,
) -> SendMessageRequest | None:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_stream_name(stream_name, topic_name)

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
    mention_backend: MentionBackend | None = None,
    disable_external_notifications: bool = False,
    acting_user: UserProfile | None = None,
) -> SendMessageRequest | None:
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
        acting_user=acting_user,
    )


def internal_send_private_message(
    sender: UserProfile,
    recipient_user: UserProfile,
    content: str,
    *,
    disable_external_notifications: bool = False,
    acting_user: UserProfile | None = None,
) -> int | None:
    message_request = internal_prep_private_message(
        sender,
        recipient_user,
        content,
        disable_external_notifications=disable_external_notifications,
        acting_user=acting_user,
    )
    if message_request is None:
        return None
    sent_message_result = do_send_messages([message_request])[0]
    return sent_message_result.message_id


def internal_send_stream_message(
    sender: UserProfile,
    stream: Stream,
    topic_name: str,
    content: str,
    *,
    email_gateway: bool = False,
    message_type: int = Message.MessageType.NORMAL,
    limit_unread_user_ids: set[int] | None = None,
    mark_as_read_for_acting_user: bool = False,
    archived_channel_notice: bool = False,
    acting_user: UserProfile | None = None,
) -> int | None:
    message_request = internal_prep_stream_message(
        sender,
        stream,
        topic_name,
        content,
        email_gateway=email_gateway,
        message_type=message_type,
        limit_unread_user_ids=limit_unread_user_ids,
        archived_channel_notice=archived_channel_notice,
        acting_user=acting_user,
    )

    if message_request is None:
        return None

    mark_as_read = []
    if mark_as_read_for_acting_user and acting_user is not None:
        mark_as_read.append(acting_user.id)

    sent_message_result = do_send_messages([message_request], mark_as_read=mark_as_read)[0]
    return sent_message_result.message_id


def internal_send_stream_message_by_name(
    realm: Realm,
    sender: UserProfile,
    stream_name: str,
    topic_name: str,
    content: str,
) -> int | None:
    message_request = internal_prep_stream_message_by_name(
        realm,
        sender,
        stream_name,
        topic_name,
        content,
    )

    if message_request is None:
        return None
    sent_message_result = do_send_messages([message_request])[0]
    return sent_message_result.message_id


def internal_prep_group_direct_message(
    realm: Realm,
    sender: UserProfile,
    content: str,
    *,
    emails: list[str] | None = None,
    recipient_users: list[UserProfile] | None = None,
) -> SendMessageRequest | None:
    if recipient_users is not None:
        addressee = Addressee.for_user_profiles(recipient_users)
    else:
        assert emails is not None
        addressee = Addressee.for_private(emails, realm)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )


def internal_send_group_direct_message(
    realm: Realm,
    sender: UserProfile,
    content: str,
    *,
    emails: list[str] | None = None,
    recipient_users: list[UserProfile] | None = None,
) -> int | None:
    message_request = internal_prep_group_direct_message(
        realm, sender, content, emails=emails, recipient_users=recipient_users
    )

    if message_request is None:
        return None

    sent_message_result = do_send_messages([message_request])[0]
    return sent_message_result.message_id


def maybe_send_channel_events_notice(
    sender: UserProfile,
    stream: Stream,
    content: str,
    *,
    email_gateway: bool = False,
    message_type: int = Message.MessageType.NORMAL,
    limit_unread_user_ids: set[int] | None = None,
    mark_as_read_for_acting_user: bool = False,
    archived_channel_notice: bool = False,
    acting_user: UserProfile | None = None,
) -> int | None:
    if not stream.realm.send_channel_events_messages:
        return None

    return internal_send_stream_message(
        sender,
        stream,
        channel_events_topic_name(stream),
        content,
        email_gateway=email_gateway,
        message_type=message_type,
        limit_unread_user_ids=limit_unread_user_ids,
        mark_as_read_for_acting_user=mark_as_read_for_acting_user,
        archived_channel_notice=archived_channel_notice,
        acting_user=acting_user,
    )

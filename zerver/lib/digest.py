import functools
import heapq
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Collection, Dict, Iterator, List, Optional, Set, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from typing_extensions import TypeAlias

from confirmation.models import one_click_unsubscribe_link
from zerver.context_processors import common_context
from zerver.lib.email_notifications import build_message_list
from zerver.lib.logging_util import log_to_file
from zerver.lib.message import get_last_message_id
from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress, send_future_email
from zerver.lib.url_encoding import stream_narrow_url
from zerver.models import (
    Message,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserActivityInterval,
    UserProfile,
)
from zerver.models.streams import get_active_streams

logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)

DIGEST_CUTOFF = 5
MAX_HOT_TOPICS_TO_BE_INCLUDED_IN_DIGEST = 4

TopicKey: TypeAlias = Tuple[int, str]


class DigestTopic:
    def __init__(self, topic_key: TopicKey) -> None:
        self.topic_key = topic_key
        self.human_senders: Set[str] = set()
        self.sample_messages: List[Message] = []
        self.num_human_messages = 0

    def stream_id(self) -> int:
        # topic_key is (stream_id, topic_name)
        return self.topic_key[0]

    def add_message(self, message: Message) -> None:
        if len(self.sample_messages) < 2:
            self.sample_messages.append(message)

        if not message.sender.is_bot:
            self.human_senders.add(message.sender.full_name)
            self.num_human_messages += 1

    def length(self) -> int:
        return self.num_human_messages

    def diversity(self) -> int:
        return len(self.human_senders)

    def teaser_data(self, user: UserProfile, stream_id_map: Dict[int, Stream]) -> Dict[str, Any]:
        teaser_count = self.num_human_messages - len(self.sample_messages)
        first_few_messages = build_message_list(
            user=user,
            messages=self.sample_messages,
            stream_id_map=stream_id_map,
        )
        return {
            "participants": sorted(self.human_senders),
            "count": teaser_count,
            "first_few_messages": first_few_messages,
        }


# Digests accumulate 2 types of interesting traffic for a user:
# 1. New streams
# 2. Interesting stream traffic, as determined by the longest and most
#    diversely comment upon topics.


# Changes to this should also be reflected in
# zerver/worker/digest_emails.py:DigestWorker.consume()
def queue_digest_user_ids(user_ids: List[int], cutoff: datetime) -> None:
    # Convert cutoff to epoch seconds for transit.
    event = {"user_ids": user_ids, "cutoff": cutoff.strftime("%s")}
    queue_json_publish("digest_emails", event)


def enqueue_emails(cutoff: datetime) -> None:
    if not settings.SEND_DIGEST_EMAILS:
        return

    weekday = timezone_now().weekday()
    for realm in Realm.objects.filter(
        deactivated=False, digest_emails_enabled=True, digest_weekday=weekday
    ).exclude(string_id__in=settings.SYSTEM_ONLY_REALMS):
        _enqueue_emails_for_realm(realm, cutoff)


def _enqueue_emails_for_realm(realm: Realm, cutoff: datetime) -> None:
    # This should only be called directly by tests.  Use enqueue_emails
    # to process all realms that are set up for processing on any given day.
    twelve_hours_ago = timezone_now() - timedelta(hours=12)

    target_users = (
        UserProfile.objects.filter(
            realm=realm,
            is_active=True,
            is_bot=False,
            enable_digest_emails=True,
        )
        .alias(
            recent_activity=Exists(
                UserActivityInterval.objects.filter(user_profile_id=OuterRef("id"), end__gt=cutoff)
            )
        )
        .filter(recent_activity=False)
        .alias(
            sent_recent_digest=Exists(
                RealmAuditLog.objects.filter(
                    realm_id=realm.id,
                    event_type=RealmAuditLog.USER_DIGEST_EMAIL_CREATED,
                    event_time__gt=twelve_hours_ago,
                    modified_user_id=OuterRef("id"),
                )
            )
        )
        .filter(sent_recent_digest=False)
    )

    user_ids = target_users.order_by("id").values_list("id", flat=True)

    # We process batches of 30.  We want a big enough batch
    # to amortize work, but not so big that a single item
    # from the queue takes too long to process.
    chunk_size = 30
    for i in range(0, len(user_ids), chunk_size):
        chunk_user_ids = list(user_ids[i : i + chunk_size])
        queue_digest_user_ids(chunk_user_ids, cutoff)
        logger.info(
            "Queuing user_ids for potential digest: %s",
            chunk_user_ids,
        )


last_realm_id: Optional[int] = None
last_cutoff: Optional[float] = None


def maybe_clear_recent_topics_cache(realm_id: int, cutoff: float) -> None:
    # As an optimization, we clear the digest caches when we switch to
    # a new realm or cutoff value.  Since these values are part of the
    # cache key, this is not necessary for correctness -- it merely
    # helps reduce the memory footprint of the cache.
    global last_realm_id, last_cutoff
    if last_realm_id != realm_id or last_cutoff != cutoff:
        logger.info("Flushing stream cache: %s", get_recent_topics.cache_info())
        get_recent_topics.cache_clear()
    last_realm_id = realm_id
    last_cutoff = cutoff


# We cache both by stream-id and cutoff, which ensures the per-stream
# cache also does not contain data from old digests
@functools.lru_cache(maxsize=5000)
def get_recent_topics(
    realm_id: int,
    stream_id: int,
    cutoff_date: datetime,
) -> List[DigestTopic]:
    # Gather information about topic conversations, then
    # classify by:
    #   * topic length
    #   * number of senders

    messages = (
        # Uses index: zerver_message_realm_recipient_date_sent
        Message.objects.filter(
            realm_id=realm_id,
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream_id,
            date_sent__gt=cutoff_date,
        )
        .order_by(
            "id",  # we will sample the first few messages
        )
        .select_related(
            "recipient",  # build_message_list looks up recipient.type
            "sender",  # we need the sender's full name
        )
        .defer(
            # This construction, to only fetch the sender's full_name and is_bot,
            # is because `.only()` doesn't work with select_related tables.
            *{
                f"sender__{f.name}"
                for f in UserProfile._meta.fields
                if f.name not in {"full_name", "is_bot"}
            }
        )
    )

    digest_topic_map: Dict[TopicKey, DigestTopic] = {}
    for message in messages:
        topic_key = (stream_id, message.topic_name())

        if topic_key not in digest_topic_map:
            digest_topic_map[topic_key] = DigestTopic(topic_key)

        digest_topic_map[topic_key].add_message(message)

    topics = list(digest_topic_map.values())

    return topics


def get_hot_topics(
    all_topics: List[DigestTopic],
    stream_ids: Set[int],
) -> List[DigestTopic]:
    topics = [topic for topic in all_topics if topic.stream_id() in stream_ids]

    hot_topics = heapq.nlargest(2, topics, key=DigestTopic.diversity)

    for topic in heapq.nlargest(
        MAX_HOT_TOPICS_TO_BE_INCLUDED_IN_DIGEST, topics, key=DigestTopic.length
    ):
        if topic not in hot_topics:
            hot_topics.append(topic)
        if len(hot_topics) == MAX_HOT_TOPICS_TO_BE_INCLUDED_IN_DIGEST:
            break

    return hot_topics


def get_recently_created_streams(realm: Realm, threshold: datetime) -> List[Stream]:
    fields = ["id", "name", "is_web_public", "invite_only"]
    return list(get_active_streams(realm).filter(date_created__gt=threshold).only(*fields))


def gather_new_streams(
    realm: Realm,
    recently_created_streams: List[Stream],  # streams only need id and name
    can_access_public: bool,
) -> Tuple[int, Dict[str, List[str]]]:
    if can_access_public:
        new_streams = [stream for stream in recently_created_streams if not stream.invite_only]
    else:
        new_streams = [stream for stream in recently_created_streams if stream.is_web_public]

    channels_html = []
    channels_plain = []

    for stream in new_streams:
        narrow_url = stream_narrow_url(realm, stream)
        channel_link = f"<a href='{narrow_url}'>{stream.name}</a>"
        channels_html.append(channel_link)
        channels_plain.append(stream.name)

    return len(new_streams), {"html": channels_html, "plain": channels_plain}


def enough_traffic(hot_conversations: str, new_streams: int) -> bool:
    return bool(hot_conversations or new_streams)


def get_user_stream_map(user_ids: List[int], cutoff_date: datetime) -> Dict[int, Set[int]]:
    """Skipping streams where the user's subscription status has changed
    when constructing digests is critical to ensure correctness for
    streams without shared history, guest users, and long-term idle
    users, because it means that every user has the same view of the
    history of a given stream whose message history is being included
    (and thus we can share a lot of work).

    The downside is that newly created streams are never included in
    the first digest email after their creation.  Should we wish to
    change that, we will need to be very careful to avoid creating
    bugs for any of those classes of users.
    """
    events = [
        RealmAuditLog.SUBSCRIPTION_CREATED,
        RealmAuditLog.SUBSCRIPTION_ACTIVATED,
        RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
    ]
    # This uses the zerver_realmauditlog_user_subscriptions_idx
    # partial index on RealmAuditLog which is specifically for those
    # three event types.
    rows = (
        Subscription.objects.filter(
            user_profile_id__in=user_ids,
            recipient__type=Recipient.STREAM,
            active=True,
            is_muted=False,
        )
        .alias(
            was_modified=Exists(
                RealmAuditLog.objects.filter(
                    modified_stream_id=OuterRef("recipient__type_id"),
                    modified_user_id=OuterRef("user_profile_id"),
                    event_time__gt=cutoff_date,
                    event_type__in=events,
                )
            )
        )
        .filter(was_modified=False)
        .values("user_profile_id", "recipient__type_id")
    )

    # maps user_id -> {stream_id, stream_id, ...}
    dct: Dict[int, Set[int]] = defaultdict(set)
    for row in rows:
        dct[row["user_profile_id"]].add(row["recipient__type_id"])

    return dct


def get_slim_stream_id_map(realm: Realm) -> Dict[int, Stream]:
    # "slim" because it only fetches the names of the stream objects,
    # suitable for passing into build_message_list.
    streams = get_active_streams(realm).only("id", "name")
    return {stream.id: stream for stream in streams}


def bulk_get_digest_context(
    users: Collection[UserProfile] | QuerySet[UserProfile], cutoff: float
) -> Iterator[Tuple[UserProfile, Dict[str, Any]]]:
    # We expect a non-empty list of users all from the same realm.
    assert users
    realm = next(iter(users)).realm
    for user in users:
        assert user.realm_id == realm.id

    # Convert from epoch seconds to a datetime object.
    cutoff_date = datetime.fromtimestamp(int(cutoff), tz=timezone.utc)

    maybe_clear_recent_topics_cache(realm.id, cutoff)

    stream_id_map = get_slim_stream_id_map(realm)
    recently_created_streams = get_recently_created_streams(realm, cutoff_date)

    user_ids = [user.id for user in users]
    user_stream_map = get_user_stream_map(user_ids, cutoff_date)

    for user in users:
        stream_ids = user_stream_map[user.id]

        recent_topics = []
        for stream_id in stream_ids:
            recent_topics += get_recent_topics(realm.id, stream_id, cutoff_date)

        hot_topics = get_hot_topics(recent_topics, stream_ids)

        context = common_context(user)

        # Start building email template data.
        unsubscribe_link = one_click_unsubscribe_link(user, "digest")
        context.update(unsubscribe_link=unsubscribe_link)

        # Get context data for hot conversations.
        context["hot_conversations"] = [
            hot_topic.teaser_data(user, stream_id_map) for hot_topic in hot_topics
        ]

        # Gather new streams.
        new_streams_count, new_streams = gather_new_streams(
            realm=realm,
            recently_created_streams=recently_created_streams,
            can_access_public=user.can_access_public_streams(),
        )
        context["new_channels"] = new_streams
        context["new_streams_count"] = new_streams_count

        yield user, context


def get_digest_context(user: UserProfile, cutoff: float) -> Dict[str, Any]:
    for ignored, context in bulk_get_digest_context([user], cutoff):
        return context
    raise AssertionError("Unreachable")


@transaction.atomic
def bulk_handle_digest_email(user_ids: List[int], cutoff: float) -> None:
    # We go directly to the database to get user objects,
    # since inactive users are likely to not be in the cache.
    users = (
        UserProfile.objects.filter(id__in=user_ids, is_active=True, realm__deactivated=False)
        .order_by("id")
        .select_related("realm")
    )
    digest_users = []

    for user, context in bulk_get_digest_context(users, cutoff):
        # We don't want to send emails containing almost no information.
        if not enough_traffic(context["hot_conversations"], context["new_streams_count"]):
            continue

        digest_users.append(user)
        logger.info("Sending digest email for user %s", user.id)

        # Send now, as a ScheduledEmail
        send_future_email(
            "zerver/emails/digest",
            user.realm,
            to_user_ids=[user.id],
            from_name=_("{service_name} digest").format(service_name=settings.INSTALLATION_NAME),
            from_address=FromAddress.no_reply_placeholder,
            context=context,
        )

    bulk_write_realm_audit_logs(digest_users)


def bulk_write_realm_audit_logs(users: List[UserProfile]) -> None:
    if not users:
        return

    # We write RealmAuditLog rows for auditing, and we will also
    # use these rows during the next run to possibly exclude the
    # users (if insufficient time has passed).
    last_message_id = get_last_message_id()
    now = timezone_now()

    log_rows = [
        RealmAuditLog(
            realm_id=user.realm_id,
            modified_user_id=user.id,
            event_last_message_id=last_message_id,
            event_time=now,
            event_type=RealmAuditLog.USER_DIGEST_EMAIL_CREATED,
        )
        for user in users
    ]

    RealmAuditLog.objects.bulk_create(log_rows)

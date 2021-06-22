import datetime
import heapq
import logging
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now

from confirmation.models import one_click_unsubscribe_link
from zerver.context_processors import common_context
from zerver.lib.email_notifications import build_message_list
from zerver.lib.logging_util import log_to_file
from zerver.lib.message import get_last_message_id
from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress, send_future_email
from zerver.lib.url_encoding import encode_stream
from zerver.models import (
    Message,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserActivityInterval,
    UserProfile,
    get_active_streams,
)

logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)

DIGEST_CUTOFF = 5
MAX_HOT_TOPICS_TO_BE_INCLUDED_IN_DIGEST = 4

TopicKey = Tuple[int, str]


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

        if message.sent_by_human():
            self.human_senders.add(message.sender.full_name)
            self.num_human_messages += 1

    def length(self) -> int:
        return self.num_human_messages

    def diversity(self) -> int:
        return len(self.human_senders)

    def teaser_data(self, user: UserProfile, stream_map: Dict[int, Stream]) -> Dict[str, Any]:
        teaser_count = self.num_human_messages - len(self.sample_messages)
        first_few_messages = build_message_list(
            user=user,
            messages=self.sample_messages,
            stream_map=stream_map,
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


def should_process_digest(realm_str: str) -> bool:
    if realm_str in settings.SYSTEM_ONLY_REALMS:
        # Don't try to send emails to system-only realms
        return False
    return True


# Changes to this should also be reflected in
# zerver/worker/queue_processors.py:DigestWorker.consume()
def queue_digest_user_ids(user_ids: List[int], cutoff: datetime.datetime) -> None:
    # Convert cutoff to epoch seconds for transit.
    event = {"user_ids": user_ids, "cutoff": cutoff.strftime("%s")}
    queue_json_publish("digest_emails", event)


def enqueue_emails(cutoff: datetime.datetime) -> None:
    if not settings.SEND_DIGEST_EMAILS:
        return

    weekday = timezone_now().weekday()
    for realm in Realm.objects.filter(
        deactivated=False, digest_emails_enabled=True, digest_weekday=weekday
    ):
        if should_process_digest(realm.string_id):
            _enqueue_emails_for_realm(realm, cutoff)


def _enqueue_emails_for_realm(realm: Realm, cutoff: datetime.datetime) -> None:
    # This should only be called directly by tests.  Use enqueue_emails
    # to process all realms that are set up for processing on any given day.
    realm_user_ids = set(
        UserProfile.objects.filter(
            realm=realm,
            is_active=True,
            is_bot=False,
            enable_digest_emails=True,
        ).values_list("id", flat=True)
    )

    twelve_hours_ago = timezone_now() - datetime.timedelta(hours=12)

    recent_user_ids = set(
        RealmAuditLog.objects.filter(
            realm_id=realm.id,
            event_type=RealmAuditLog.USER_DIGEST_EMAIL_CREATED,
            event_time__gt=twelve_hours_ago,
        )
        .values_list("modified_user_id", flat=True)
        .distinct()
    )

    realm_user_ids -= recent_user_ids

    active_user_ids = set(
        UserActivityInterval.objects.filter(
            user_profile_id__in=realm_user_ids,
            end__gt=cutoff,
        )
        .values_list("user_profile_id", flat=True)
        .distinct()
    )

    user_ids = list(realm_user_ids - active_user_ids)
    user_ids.sort()

    # We process batches of 30.  We want a big enough batch
    # to amorize work, but not so big that a single item
    # from the queue takes too long to process.
    chunk_size = 30
    for i in range(0, len(user_ids), chunk_size):
        chunk_user_ids = user_ids[i : i + chunk_size]
        queue_digest_user_ids(chunk_user_ids, cutoff)
        logger.info(
            "Queuing user_ids for potential digest: %s",
            chunk_user_ids,
        )


def get_recent_topics(
    stream_ids: List[int],
    cutoff_date: datetime.datetime,
) -> List[DigestTopic]:
    # Gather information about topic conversations, then
    # classify by:
    #   * topic length
    #   * number of senders

    messages = (
        Message.objects.filter(
            recipient__type=Recipient.STREAM,
            recipient__type_id__in=stream_ids,
            date_sent__gt=cutoff_date,
        )
        .order_by(
            "id",  # we will sample the first few messages
        )
        .select_related(
            "recipient",  # we need stream_id
            "sender",  # we need the sender's full name
            "sending_client",  # for Message.sent_by_human
        )
    )

    digest_topic_map: Dict[TopicKey, DigestTopic] = {}
    for message in messages:
        topic_key = (message.recipient.type_id, message.topic_name())

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


def get_recent_streams(realm: Realm, threshold: datetime.datetime) -> List[Stream]:
    fields = ["id", "name", "is_web_public", "invite_only"]
    return list(get_active_streams(realm).filter(date_created__gt=threshold).only(*fields))


def gather_new_streams(
    realm: Realm,
    recent_streams: List[Stream],  # streams only need id and name
    can_access_public: bool,
) -> Tuple[int, Dict[str, List[str]]]:
    if can_access_public:
        new_streams = [stream for stream in recent_streams if not stream.invite_only]
    else:
        new_streams = [stream for stream in recent_streams if stream.is_web_public]

    base_url = f"{realm.uri}/#narrow/stream/"

    streams_html = []
    streams_plain = []

    for stream in new_streams:
        narrow_url = base_url + encode_stream(stream.id, stream.name)
        stream_link = f"<a href='{narrow_url}'>{stream.name}</a>"
        streams_html.append(stream_link)
        streams_plain.append(stream.name)

    return len(new_streams), {"html": streams_html, "plain": streams_plain}


def enough_traffic(hot_conversations: str, new_streams: int) -> bool:
    return bool(hot_conversations or new_streams)


def get_user_stream_map(user_ids: List[int]) -> Dict[int, Set[int]]:
    rows = Subscription.objects.filter(
        user_profile_id__in=user_ids,
        recipient__type=Recipient.STREAM,
        active=True,
        is_muted=False,
    ).values("user_profile_id", "recipient__type_id")

    # maps user_id -> {stream_id, stream_id, ...}
    dct: Dict[int, Set[int]] = defaultdict(set)
    for row in rows:
        dct[row["user_profile_id"]].add(row["recipient__type_id"])

    return dct


def get_slim_stream_map(stream_ids: Set[int]) -> Dict[int, Stream]:
    # This can be passed to build_message_list.
    streams = Stream.objects.filter(
        id__in=stream_ids,
    ).only("id", "name")

    return {stream.id: stream for stream in streams}


def bulk_get_digest_context(users: List[UserProfile], cutoff: float) -> Dict[int, Dict[str, Any]]:
    # We expect a non-empty list of users all from the same realm.
    assert users
    realm = users[0].realm
    for user in users:
        assert user.realm_id == realm.id

    # Convert from epoch seconds to a datetime object.
    cutoff_date = datetime.datetime.fromtimestamp(int(cutoff), tz=datetime.timezone.utc)

    result: Dict[int, Dict[str, Any]] = {}

    user_ids = [user.id for user in users]

    user_stream_map = get_user_stream_map(user_ids)

    recently_modified_streams = get_modified_streams(user_ids, cutoff_date)

    all_stream_ids = set()

    for user in users:
        stream_ids = user_stream_map[user.id]
        stream_ids -= recently_modified_streams.get(user.id, set())
        all_stream_ids |= stream_ids

    # Get all the recent topics for all the users.  This does the heavy
    # lifting of making an expensive query to the Message table.  Then
    # for each user, we filter to just the streams they care about.
    recent_topics = get_recent_topics(sorted(list(all_stream_ids)), cutoff_date)

    stream_map = get_slim_stream_map(all_stream_ids)

    recent_streams = get_recent_streams(realm, cutoff_date)

    for user in users:
        stream_ids = user_stream_map[user.id]

        hot_topics = get_hot_topics(recent_topics, stream_ids)

        context = common_context(user)

        # Start building email template data.
        unsubscribe_link = one_click_unsubscribe_link(user, "digest")
        context.update(unsubscribe_link=unsubscribe_link)

        # Get context data for hot conversations.
        context["hot_conversations"] = [
            hot_topic.teaser_data(user, stream_map) for hot_topic in hot_topics
        ]

        # Gather new streams.
        new_streams_count, new_streams = gather_new_streams(
            realm=realm,
            recent_streams=recent_streams,
            can_access_public=user.can_access_public_streams(),
        )
        context["new_streams"] = new_streams
        context["new_streams_count"] = new_streams_count

        result[user.id] = context

    return result


def get_digest_context(user: UserProfile, cutoff: float) -> Dict[str, Any]:
    return bulk_get_digest_context([user], cutoff)[user.id]


@transaction.atomic(savepoint=False)
def bulk_handle_digest_email(user_ids: List[int], cutoff: float) -> None:
    # We go directly to the database to get user objects,
    # since inactive users are likely to not be in the cache.
    users = UserProfile.objects.filter(id__in=user_ids).order_by("id").select_related("realm")
    context_map = bulk_get_digest_context(users, cutoff)

    digest_users = []

    for user in users:
        context = context_map[user.id]

        # We don't want to send emails containing almost no information.
        if enough_traffic(context["hot_conversations"], context["new_streams_count"]):
            digest_users.append(user)
            logger.info("Sending digest email for user %s", user.id)
            # Send now, as a ScheduledEmail
            send_future_email(
                "zerver/emails/digest",
                user.realm,
                to_user_ids=[user.id],
                from_name="Zulip Digest",
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


def get_modified_streams(
    user_ids: List[int], cutoff_date: datetime.datetime
) -> Dict[int, Set[int]]:
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

    # Get rows where the users' subscriptions have changed.
    rows = (
        RealmAuditLog.objects.filter(
            modified_user_id__in=user_ids,
            event_time__gt=cutoff_date,
            event_type__in=events,
        )
        .values("modified_user_id", "modified_stream_id")
        .distinct()
    )

    result: Dict[int, Set[int]] = defaultdict(set)

    for row in rows:
        user_id = row["modified_user_id"]
        stream_id = row["modified_stream_id"]
        result[user_id].add(stream_id)

    return result

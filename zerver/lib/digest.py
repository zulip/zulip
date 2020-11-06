import datetime
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from django.conf import settings
from django.utils.timezone import now as timezone_now

from confirmation.models import one_click_unsubscribe_link
from zerver.context_processors import common_context
from zerver.lib.email_notifications import build_message_list
from zerver.lib.logging_util import log_to_file
from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress, send_future_email
from zerver.lib.url_encoding import encode_stream
from zerver.models import (
    Message,
    Realm,
    RealmAuditLog,
    Recipient,
    Subscription,
    UserActivity,
    UserProfile,
    get_active_streams,
    get_user_profile_by_id,
)

logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)

DIGEST_CUTOFF = 5

TopicKey = Tuple[int, str]

@dataclass
class TopicActivity:
    topics_by_length: List[TopicKey]
    topics_by_diversity: List[TopicKey]
    topic_senders: Dict[TopicKey, Set[str]]  # full_name
    topic_length: Dict[TopicKey, int]
    topic_messages: Dict[TopicKey, List[Message]]

# Digests accumulate 2 types of interesting traffic for a user:
# 1. New streams
# 2. Interesting stream traffic, as determined by the longest and most
#    diversely comment upon topics.

def inactive_since(user_profile: UserProfile, cutoff: datetime.datetime) -> bool:
    # Hasn't used the app in the last DIGEST_CUTOFF (5) days.
    most_recent_visit = [row.last_visit for row in
                         UserActivity.objects.filter(
                             user_profile=user_profile)]

    if not most_recent_visit:
        # This person has never used the app.
        return True

    last_visit = max(most_recent_visit)
    return last_visit < cutoff

def should_process_digest(realm_str: str) -> bool:
    if realm_str in settings.SYSTEM_ONLY_REALMS:
        # Don't try to send emails to system-only realms
        return False
    return True

# Changes to this should also be reflected in
# zerver/worker/queue_processors.py:DigestWorker.consume()
def queue_digest_recipient(user_profile: UserProfile, cutoff: datetime.datetime) -> None:
    # Convert cutoff to epoch seconds for transit.
    event = {"user_profile_id": user_profile.id,
             "cutoff": cutoff.strftime('%s')}
    queue_json_publish("digest_emails", event)

def enqueue_emails(cutoff: datetime.datetime) -> None:
    if not settings.SEND_DIGEST_EMAILS:
        return

    weekday = timezone_now().weekday()
    for realm in Realm.objects.filter(deactivated=False, digest_emails_enabled=True, digest_weekday=weekday):
        if not should_process_digest(realm.string_id):
            continue

        user_profiles = UserProfile.objects.filter(
            realm=realm, is_active=True, is_bot=False, enable_digest_emails=True)

        for user_profile in user_profiles:
            if inactive_since(user_profile, cutoff):
                queue_digest_recipient(user_profile, cutoff)
                logger.info(
                    "User %s is inactive, queuing for potential digest",
                    user_profile.id,
                )

def get_recent_topic_activity(
    stream_ids: List[int],
    cutoff_date: datetime.datetime,
) -> TopicActivity:
    # Gather information about topic conversations, then
    # classify by:
    #   * topic length
    #   * number of senders

    messages = Message.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        date_sent__gt=cutoff_date).select_related('recipient', 'sender', 'sending_client')

    topic_length: Dict[TopicKey, int] = defaultdict(int)
    topic_messages: Dict[TopicKey, List[Message]] = defaultdict(list)
    topic_senders: Dict[TopicKey, Set[str]] = defaultdict(set)
    for message in messages:
        key = (message.recipient.type_id,
               message.topic_name())

        topic_messages[key].append(message)

        if not message.sent_by_human():
            # Don't include automated messages in the count.
            continue

        topic_senders[key].add(message.sender.full_name)
        topic_length[key] += 1

    topics_by_diversity = list(topic_senders)
    topics_by_diversity.sort(key=lambda key: topic_senders[key], reverse=True)

    topics_by_length = list(topic_length)
    topics_by_diversity.sort(key=lambda key: topic_length[key], reverse=True)

    return TopicActivity(
        topics_by_diversity=topics_by_diversity,
        topics_by_length=topics_by_length,
        topic_senders=topic_senders,
        topic_length=topic_length,
        topic_messages=topic_messages,
    )

def get_hot_topics(
    topic_activity: TopicActivity,
) -> List[TopicKey]:
    # Get out top 4 hottest topics

    topics_by_diversity = topic_activity.topics_by_diversity
    topics_by_length = topic_activity.topics_by_length

    assert set(topics_by_diversity) == set(topics_by_length)

    # Start with the two most diverse topics.
    hot_topics = topics_by_diversity[:2]

    # Pad out our list up to 4 items, using the topics' length (aka message
    # count) as the secondary filter.
    for topic_key in topics_by_length:
        if topic_key not in hot_topics:
            hot_topics.append(topic_key)
        if len(hot_topics) >= 4:
            break

    return hot_topics

def gather_hot_topics(
    user_profile: UserProfile,
    hot_topics: List[TopicKey],
    topic_activity: TopicActivity,
) -> List[Dict[str, Any]]:
    # Returns a list of dictionaries containing the templating
    # information for each hot topic.

    topic_senders = topic_activity.topic_senders
    topic_length = topic_activity.topic_length
    topic_messages = topic_activity.topic_messages

    hot_topic_render_payloads = []
    for h in hot_topics:
        users = list(topic_senders[h])
        count = topic_length[h]
        messages = topic_messages[h]

        # We'll display up to 2 messages from the topic.
        first_few_messages = messages[:2]

        teaser_data = {"participants": users,
                       "count": count - len(first_few_messages),
                       "first_few_messages": build_message_list(
                           user_profile, first_few_messages)}

        hot_topic_render_payloads.append(teaser_data)
    return hot_topic_render_payloads

def gather_new_streams(user_profile: UserProfile,
                       threshold: datetime.datetime) -> Tuple[int, Dict[str, List[str]]]:
    if user_profile.is_guest:
        new_streams = list(get_active_streams(user_profile.realm).filter(
            is_web_public=True, date_created__gt=threshold))

    elif user_profile.can_access_public_streams():
        new_streams = list(get_active_streams(user_profile.realm).filter(
            invite_only=False, date_created__gt=threshold))

    base_url = f"{user_profile.realm.uri}/#narrow/stream/"

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

def bulk_get_digest_context(users: List[UserProfile], cutoff: float) -> Dict[int, Dict[str, Any]]:
    # Convert from epoch seconds to a datetime object.
    cutoff_date = datetime.datetime.fromtimestamp(int(cutoff), tz=datetime.timezone.utc)

    result: Dict[int, Dict[str, Any]] = {}

    user_ids = [user.id for user in users]

    def get_stream_map(user_ids: List[int]) -> Dict[int, Set[int]]:
        rows = Subscription.objects.filter(
            user_profile_id__in=user_ids,
            recipient__type=Recipient.STREAM,
            active=True,
            is_muted=False,
        ).values('user_profile_id', 'recipient__type_id')

        # maps user_id -> {stream_id, stream_id, ...}
        dct: Dict[int, Set[int]] = defaultdict(set)
        for row in rows:
            dct[row['user_profile_id']].add(row['recipient__type_id'])

        return dct

    stream_map = get_stream_map(user_ids)

    for user in users:
        context = common_context(user)

        # Start building email template data.
        unsubscribe_link = one_click_unsubscribe_link(user, "digest")
        context.update(unsubscribe_link=unsubscribe_link)

        stream_ids = stream_map[user.id]

        if user.long_term_idle:
            stream_ids -= streams_recently_modified_for_user(user, cutoff_date)

        topic_activity = get_recent_topic_activity(sorted(list(stream_ids)), cutoff_date)
        hot_topics = get_hot_topics(topic_activity)

        # Gather hot conversations.
        context["hot_conversations"] = gather_hot_topics(user, hot_topics, topic_activity)

        # Gather new streams.
        new_streams_count, new_streams = gather_new_streams(user, cutoff_date)
        context["new_streams"] = new_streams
        context["new_streams_count"] = new_streams_count

        result[user.id] = context

    return result

def get_digest_context(user: UserProfile, cutoff: float) -> Dict[str, Any]:
    return bulk_get_digest_context([user], cutoff)[user.id]

def bulk_handle_digest_email(user_ids: List[int], cutoff: float) -> None:
    users = [get_user_profile_by_id(user_id) for user_id in user_ids]
    context_map = bulk_get_digest_context(users, cutoff)

    for user in users:
        context = context_map[user.id]

        # We don't want to send emails containing almost no information.
        if enough_traffic(context["hot_conversations"], context["new_streams_count"]):
            logger.info("Sending digest email for user %s", user.id)
            # Send now, as a ScheduledEmail
            send_future_email(
                'zerver/emails/digest',
                user.realm,
                to_user_ids=[user.id],
                from_name="Zulip Digest",
                from_address=FromAddress.no_reply_placeholder,
                context=context,
            )

def handle_digest_email(user_id: int, cutoff: float) -> None:
    bulk_handle_digest_email([user_id], cutoff)

def streams_recently_modified_for_user(user: UserProfile, cutoff_date: datetime.datetime) -> Set[int]:
    events = [
        RealmAuditLog.SUBSCRIPTION_CREATED,
        RealmAuditLog.SUBSCRIPTION_ACTIVATED,
        RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
    ]

    # Streams where the user's subscription was changed
    modified_streams = RealmAuditLog.objects.filter(
        realm=user.realm,
        modified_user=user,
        event_time__gt=cutoff_date,
        event_type__in=events).values_list('modified_stream_id', flat=True)

    return set(modified_streams)

"""Core business logic for the "What Did I Miss?" catch-up feature.

This module provides functions for:
1. Detecting a user's last active time (inactivity detection)
2. Aggregating messages since last activity across subscribed streams
3. Scoring and ranking topics by importance
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils.timezone import now as timezone_now

from zerver.models import (
    Message,
    Reaction,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)
from zerver.models.presence import UserPresence
from zerver.models.user_activity import UserActivityInterval
from zerver.models.user_topics import UserTopic

logger = logging.getLogger(__name__)

# Default inactivity threshold: only generate catch-up data if the user
# has been away for at least this many hours.
DEFAULT_INACTIVITY_THRESHOLD_HOURS = 4

# Maximum number of messages to process in a single catch-up request.
MAX_CATCH_UP_MESSAGES = 1000

# Maximum absence period to consider (in days). Prevents overwhelming
# data loads for users who have been away for very long periods.
MAX_ABSENCE_DAYS = 7

# Maximum number of sample (preview) messages to include per topic.
MAX_SAMPLE_MESSAGES_PER_TOPIC = 3

# Importance scoring weights.
WEIGHT_DIRECT_MENTION = 5.0
WEIGHT_WILDCARD_MENTION = 3.0
WEIGHT_GROUP_MENTION = 2.0
WEIGHT_SENDER_DIVERSITY = 1.5
WEIGHT_MESSAGE_COUNT = 1.0
WEIGHT_REACTION_COUNT = 0.5
WEIGHT_RECENCY_BONUS = 0.5


def get_last_active_time(user_profile: UserProfile) -> datetime:
    """Determine the user's last active time.

    Strategy:
    1. Check UserPresence.last_active_time (the real-time presence system).
    2. Fall back to the most recent UserActivityInterval end time.
    3. Fall back to a default of DEFAULT_INACTIVITY_THRESHOLD_HOURS ago.

    Note: UserPresence can be disabled (presence_enabled=False), so
    we also check UserActivityInterval for robustness.
    """
    # TODO: Remove this override after testing.
    # Force 24h lookback for development testing.
    #return timezone_now() - timedelta(hours=24)

    # Try presence data first.
    try:
        presence = UserPresence.objects.get(user_profile=user_profile)
        if presence.last_active_time is not None:
            return presence.last_active_time
    except UserPresence.DoesNotExist:
        pass

    # Fall back to most recent activity interval.
    latest_interval = (
        UserActivityInterval.objects.filter(user_profile=user_profile).order_by("-end").first()
    )
    if latest_interval is not None:
        return latest_interval.end

    # Default: assume the user was last active DEFAULT_INACTIVITY_THRESHOLD_HOURS ago.
    return timezone_now() - timedelta(hours=DEFAULT_INACTIVITY_THRESHOLD_HOURS)

    # Suggestion: new user protection; Use date_joined if they are newer than the given threshold.
    # We don't give summaries of old messages for new summaries. If approved, we need to add 2 tests to ensure that new users only see new messages: 1 has eligible messages before user joined. 
    #return max(user_profile.date_joined, timezone_now() - timedelta(hours=DEFAULT_INACTIVITY_THRESHOLD_HOURS))


def clamp_since_time(since: datetime) -> datetime:
    """Clamp the 'since' time to be no more than MAX_ABSENCE_DAYS in the past."""
    earliest_allowed = timezone_now() - timedelta(days=MAX_ABSENCE_DAYS)
    return max(since, earliest_allowed)


@dataclass
class CatchUpTopic:
    """Aggregated data for a single stream/topic in the catch-up view."""

    stream_id: int
    stream_name: str
    topic_name: str
    message_count: int = 0
    human_senders: set[str] = field(default_factory=set)
    has_mention: bool = False
    has_wildcard_mention: bool = False
    has_group_mention: bool = False
    reaction_count: int = 0
    latest_message_id: int = 0
    first_message_id: int = 0
    latest_date_sent: datetime | None = None
    sample_messages: list[dict[str, object]] = field(default_factory=list)
    key_messages: list[dict[str, object]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    @property
    def sender_count(self) -> int:
        return len(self.human_senders)

    @property
    def senders(self) -> list[str]:
        return sorted(self.human_senders)

    def score(self, now: datetime) -> float:
        """Calculate an importance score for this topic."""
        s = 0.0

        # Mentions are the strongest signal.
        if self.has_mention:
            s += WEIGHT_DIRECT_MENTION
        if self.has_wildcard_mention:
            s += WEIGHT_WILDCARD_MENTION
        if self.has_group_mention:
            s += WEIGHT_GROUP_MENTION

        # Sender diversity: more people talking = more important.
        s += self.sender_count * WEIGHT_SENDER_DIVERSITY


        # the current sender diversity logic assigns equal weighting for any number of senders
        # we could assign a stronger weight for more than 2 people talking
        # s += (self.sender_count * WEIGHT_SENDER_DIVERSITY) * 1.5 if sender_count > 3 else 1 

        # Message volume.
        s += self.message_count * WEIGHT_MESSAGE_COUNT

        # Reactions signal engagement.
        s += self.reaction_count * WEIGHT_REACTION_COUNT

        # Recency bonus: topics active more recently get a small boost.
        if self.latest_date_sent is not None:
            hours_ago = (now - self.latest_date_sent).total_seconds() / 3600
            # Scale: 0-1 bonus, higher for more recent topics.
            recency = max(0.0, 1.0 - hours_ago / 24.0)
            s += recency * WEIGHT_RECENCY_BONUS

        return s

    def to_dict(self, now: datetime) -> dict[str, object]:
        result: dict[str, object] = {
            "stream_id": self.stream_id,
            "stream_name": self.stream_name,
            "topic_name": self.topic_name,
            "score": round(self.score(now), 2),
            "message_count": self.message_count,
            "sender_count": self.sender_count,
            "senders": self.senders,
            "has_mention": self.has_mention,
            "has_wildcard_mention": self.has_wildcard_mention,
            "has_group_mention": self.has_group_mention,
            "reaction_count": self.reaction_count,
            "latest_message_id": self.latest_message_id,
            "first_message_id": self.first_message_id,
            "sample_messages": self.sample_messages,
        }
        if self.key_messages:
            result["key_messages"] = self.key_messages
        if self.keywords:
            result["keywords"] = self.keywords
        return result


TopicKey = tuple[int, str]  # (stream_id, topic_name)


def get_subscribed_stream_map(
    user_profile: UserProfile, include_muted: bool = False
) -> dict[int, str]:
    """Return a mapping of stream_id -> stream_name for the user's
    active, non-deactivated stream subscriptions.

    If include_muted is False (default), muted streams are excluded.
    """
    subs_query = Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
        is_user_active=True,
    ).select_related("recipient")

    if not include_muted:
        subs_query = subs_query.filter(is_muted=False)

    # Get the stream IDs from the subscriptions.
    stream_ids = [sub.recipient.type_id for sub in subs_query]

    if not stream_ids:
        return {}

    # Fetch stream names in bulk.
    streams = Stream.objects.filter(
        id__in=stream_ids,
        deactivated=False,
    ).only("id", "name")

    return {stream.id: stream.name for stream in streams}


def get_muted_topics_for_user(user_profile: UserProfile) -> set[TopicKey]:
    """Return the set of (stream_id, lower(topic_name)) pairs that the
    user has muted."""
    muted = UserTopic.objects.filter(
        user_profile=user_profile,
        visibility_policy=UserTopic.VisibilityPolicy.MUTED,
    ).values_list("stream_id", "topic_name")

    return {(stream_id, topic_name.lower()) for stream_id, topic_name in muted}


def get_catch_up_messages(
    user_profile: UserProfile,
    since: datetime,
    stream_map: dict[int, str],
    include_muted: bool = False,
) -> dict[TopicKey, CatchUpTopic]:
    """Aggregate messages since `since` across the user's subscribed streams,
    grouped by (stream_id, topic_name).

    Returns a dict mapping topic keys to CatchUpTopic objects.
    """
    if not stream_map:
        return {}

    # Get recipient IDs for the subscribed streams.
    # We need to map stream_id -> recipient_id for the query.
    stream_ids = list(stream_map.keys())
    recipients = Recipient.objects.filter(
        type=Recipient.STREAM,
        type_id__in=stream_ids,
    ).values_list("id", "type_id")

    recipient_to_stream: dict[int, int] = {}
    stream_to_recipient: dict[int, int] = {}
    for recipient_id, stream_id in recipients:
        recipient_to_stream[recipient_id] = stream_id
        stream_to_recipient[stream_id] = recipient_id

    recipient_ids = list(recipient_to_stream.keys())

    if not recipient_ids:
        return {}

    # Fetch messages using the zerver_message_realm_recipient_date_sent index.
    messages = (
        Message.objects.filter(
            realm_id=user_profile.realm_id,
            recipient_id__in=recipient_ids,
            #date_sent__gt=since,
            date_sent__gt=clamp_since_time(since),
            # added: use our clamping function, can make a test for this
            is_channel_message=True
        )
        .order_by("id")
        .select_related("sender")[:MAX_CATCH_UP_MESSAGES]
    )

    # Optionally filter out muted topics.
    muted_topics: set[TopicKey] = set()
    if not include_muted:
        muted_topics = get_muted_topics_for_user(user_profile)

    # Group messages by topic.
    topics: dict[TopicKey, CatchUpTopic] = {}

    for message in messages:
        stream_id = recipient_to_stream.get(message.recipient_id)
        if stream_id is None:
            continue

        topic_name = message.topic_name()
        topic_key: TopicKey = (stream_id, topic_name)

        # Skip muted topics.
        if not include_muted and (stream_id, topic_name.lower()) in muted_topics:
            continue

        if topic_key not in topics:
            topics[topic_key] = CatchUpTopic(
                stream_id=stream_id,
                stream_name=stream_map.get(stream_id, ""),
                topic_name=topic_name,
                first_message_id=message.id,
            )

        topic = topics[topic_key]
        topic.message_count += 1

        if not message.sender.is_bot:
            topic.human_senders.add(message.sender.full_name)

        topic.latest_message_id = message.id
        topic.latest_date_sent = message.date_sent

        # Collect sample messages (first N non-bot messages).
        if len(topic.sample_messages) < MAX_SAMPLE_MESSAGES_PER_TOPIC:
            topic.sample_messages.append(
                {
                    "id": message.id,
                    "sender_full_name": message.sender.full_name,
                    "content": message.content[:200],  # Truncate for preview
                    "date_sent": str(message.date_sent),
                }
            )

    return topics


def annotate_mention_flags(
    user_profile: UserProfile,
    topics: dict[TopicKey, CatchUpTopic],
    since: datetime,
) -> None:
    """Check UserMessage flags to identify topics where the user was mentioned.

    This modifies the CatchUpTopic objects in-place.
    """
    if not topics:
        return

    # Collect all message IDs across topics to check mentions in bulk.
    # For efficiency, we only check the first and latest message IDs
    # to build a range, then query UserMessage within that range.
    all_first_ids = [t.first_message_id for t in topics.values()]
    all_latest_ids = [t.latest_message_id for t in topics.values()]
    min_message_id = min(all_first_ids)
    max_message_id = max(all_latest_ids)

    # Query UserMessage rows that have mention flags set.
    mentioned_message_ids = set(
        UserMessage.objects.filter(
            user_profile=user_profile,
            message_id__gte=min_message_id,
            message_id__lte=max_message_id,
        )
        .filter(
            Q(flags__andnz=UserMessage.flags.mentioned.mask)
            | Q(flags__andnz=UserMessage.flags.stream_wildcard_mentioned.mask)
            | Q(flags__andnz=UserMessage.flags.topic_wildcard_mentioned.mask)
            | Q(flags__andnz=UserMessage.flags.group_mentioned.mask)
        )
        .values_list("message_id", flat=True)
    )

    if not mentioned_message_ids:
        return

    # Map mentioned message IDs back to their topics.
    # We need to know which message belongs to which topic.
    # Re-query the messages to get their recipient and topic info.
    mentioned_messages = Message.objects.filter(
        id__in=mentioned_message_ids,
    ).values_list("id", "recipient_id", "subject")

    # Build recipient_id -> stream_id mapping.
    all_stream_ids = {t.stream_id for t in topics.values()}
    recipient_map = dict(
        Recipient.objects.filter(
            type=Recipient.STREAM,
            type_id__in=all_stream_ids,
        ).values_list("id", "type_id")
    )

    for msg_id, recipient_id, subject in mentioned_messages:
        stream_id = recipient_map.get(recipient_id)
        if stream_id is None:
            continue

        topic_key: TopicKey = (stream_id, subject)
        topic = topics.get(topic_key)
        if topic is None:
            continue

        # Check which specific flags are set on this UserMessage.
        try:
            user_message = UserMessage.objects.get(
                user_profile=user_profile, message_id=msg_id
            )
        except UserMessage.DoesNotExist:
            continue

        if user_message.flags.mentioned:
            topic.has_mention = True
        if (
            user_message.flags.stream_wildcard_mentioned
            or user_message.flags.topic_wildcard_mentioned
        ):
            topic.has_wildcard_mention = True
        if user_message.flags.group_mentioned:
            topic.has_group_mention = True


def annotate_reaction_counts(
    topics: dict[TopicKey, CatchUpTopic],
    since: datetime,
    realm_id: int,
) -> None:
    """Annotate topics with reaction counts for messages in the catch-up period.

    This modifies the CatchUpTopic objects in-place.
    """
    if not topics:
        return

    # Build a mapping of message_id -> topic_key so we can attribute
    # reactions to the right topic.
    all_first_ids = [t.first_message_id for t in topics.values()]
    all_latest_ids = [t.latest_message_id for t in topics.values()]
    min_message_id = min(all_first_ids)
    max_message_id = max(all_latest_ids)

    # Count reactions per message in the range.
    reaction_counts = (
        Reaction.objects.filter(
            message_id__gte=min_message_id,
            message_id__lte=max_message_id,
        )
        .values("message__recipient_id", "message__subject")
        .annotate(count=Count("id"))
    )

    # Build recipient_id -> stream_id mapping.
    all_stream_ids = {t.stream_id for t in topics.values()}
    recipient_map = dict(
        Recipient.objects.filter(
            type=Recipient.STREAM,
            type_id__in=all_stream_ids,
        ).values_list("id", "type_id")
    )

    for row in reaction_counts:
        stream_id = recipient_map.get(row["message__recipient_id"])
        if stream_id is None:
            continue

        topic_key: TopicKey = (stream_id, row["message__subject"])
        topic = topics.get(topic_key)
        if topic is not None:
            topic.reaction_count += row["count"]


def rank_topics(
    topics: dict[TopicKey, CatchUpTopic],
    max_topics: int,
) -> list[CatchUpTopic]:
    """Score and rank topics by importance, returning the top N."""
    now = timezone_now()
    sorted_topics = sorted(topics.values(), key=lambda t: t.score(now), reverse=True)
    return sorted_topics[:max_topics]

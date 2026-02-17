"""Action layer for the "What Did I Miss?" catch-up feature.

This module orchestrates the catch-up data generation by coordinating
the various library functions in zerver.lib.catch_up.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.actions.message_summary import do_summarize_narrow
from zerver.lib.catch_up import (
    CatchUpTopic,
    annotate_mention_flags,
    annotate_reaction_counts,
    clamp_since_time,
    get_catch_up_messages,
    get_last_active_time,
    get_subscribed_stream_map,
    rank_topics,
)
from zerver.lib.catch_up_summarizer import extract_key_messages, extract_keywords
from zerver.lib.narrow import NarrowParameter
from zerver.models import Message, Recipient, UserProfile

logger = logging.getLogger(__name__)

# Default maximum number of topics to return in catch-up data.
DEFAULT_MAX_TOPICS = 20


def do_get_catch_up_data(
    user_profile: UserProfile,
    since: datetime | None = None,
    max_topics: int = DEFAULT_MAX_TOPICS,
    include_muted: bool = False,
    include_extractive_summary: bool = False,
) -> dict[str, Any]:
    """Main orchestrator for generating catch-up data.

    1. Determine the user's last active time (or use the provided 'since').
    2. Fetch and aggregate messages across subscribed streams.
    3. Annotate topics with mention flags and reaction counts.
    4. Score and rank topics by importance.
    5. Optionally generate extractive summaries (key messages + keywords).
    6. Return structured data ready for the API response.
    """
    now = timezone_now()

    # Step 1: Determine the catch-up period.
    if since is None:
        since = get_last_active_time(user_profile)

    # Clamp to MAX_ABSENCE_DAYS to prevent overwhelming queries.
    since = clamp_since_time(since)

    catch_up_period_hours = round((now - since).total_seconds() / 3600, 1)

    # Step 2: Get the user's subscribed streams.
    stream_map = get_subscribed_stream_map(user_profile, include_muted=include_muted)

    empty_response: dict[str, Any] = {
        "last_active_time": str(since),
        "catch_up_period_hours": catch_up_period_hours,
        "total_messages": 0,
        "total_topics": 0,
        "topics": [],
    }

    if not stream_map:
        return empty_response

    # Step 3: Aggregate messages by stream/topic.
    topics = get_catch_up_messages(
        user_profile=user_profile,
        since=since,
        stream_map=stream_map,
        include_muted=include_muted,
    )

    if not topics:
        return empty_response

    # Step 4: Annotate with mention flags and reaction counts.
    annotate_mention_flags(user_profile, topics, since)
    annotate_reaction_counts(topics, since, user_profile.realm_id)

    # Step 5: Calculate totals.
    total_messages = sum(t.message_count for t in topics.values())
    total_topics = len(topics)

    # Step 6: Rank and limit topics.
    ranked = rank_topics(topics, max_topics)

    # Step 7: Optionally generate extractive summaries for ranked topics.
    if include_extractive_summary:
        _annotate_extractive_summaries(user_profile, ranked, since)

    return {
        "last_active_time": str(since),
        "catch_up_period_hours": catch_up_period_hours,
        "total_messages": total_messages,
        "total_topics": total_topics,
        "topics": [t.to_dict(now) for t in ranked],
    }


def _annotate_extractive_summaries(
    user_profile: UserProfile,
    topics: list[CatchUpTopic],
    since: datetime,
) -> None:
    """Generate extractive summaries (key messages + keywords) for each topic.

    Modifies the CatchUpTopic objects in-place.
    """
    for topic in topics:
        # Extract key messages for this topic.
        topic.key_messages = extract_key_messages(
            user_profile=user_profile,
            stream_id=topic.stream_id,
            topic_name=topic.topic_name,
            since=since,
        )

        # Extract keywords from topic messages.
        try:
            recipient = Recipient.objects.get(
                type=Recipient.STREAM, type_id=topic.stream_id
            )
            messages = list(
                Message.objects.filter(
                    realm_id=user_profile.realm_id,
                    recipient=recipient,
                    subject__iexact=topic.topic_name,
                    date_sent__gt=since,
                    is_channel_message=True,
                )
                .order_by("id")
                .only("content")
            )
            topic.keywords = extract_keywords(messages)
        except Recipient.DoesNotExist:
            topic.keywords = []


def do_get_catch_up_summary(
    user_profile: UserProfile,
    stream_id: int,
    topic_name: str,
) -> str | None:
    """Generate an AI summary for a specific topic.

    Reuses the existing do_summarize_narrow() infrastructure from
    zerver.actions.message_summary.

    Returns the rendered HTML summary, or None if summarization is
    not available or there are no messages.
    """
    narrow = [
        NarrowParameter(operator="channel", operand=str(stream_id), negated=False),
        NarrowParameter(operator="topic", operand=topic_name, negated=False),
    ]
    return do_summarize_narrow(user_profile, narrow)

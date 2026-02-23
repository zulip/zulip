"""Extractive summarization for the "What Did I Miss?" catch-up feature.

This module selects the most representative messages from a topic
without requiring an AI model. It uses heuristic signals to identify
"key messages" that a returning user would most want to see.

The extractive approach:
- Always available (no AI model configuration required)
- Transparent: every summary point links directly to a real message
- Fast: no external API calls, just database queries and scoring

The AI summary endpoint (GET /json/catch-up/summary) is separate and
provides richer abstractive summaries when configured.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Q

from zerver.models import (
    Message,
    Reaction,
    Recipient,
    UserMessage,
    UserProfile,
)

# Maximum number of key messages to extract per topic.
MAX_KEY_MESSAGES = 5

# Scoring weights for individual message importance.
MSG_WEIGHT_MENTIONED = 10.0
MSG_WEIGHT_WILDCARD_MENTIONED = 5.0
MSG_WEIGHT_REACTION_COUNT = 2.0
MSG_WEIGHT_IS_FIRST = 3.0
MSG_WEIGHT_IS_LAST = 2.0
MSG_WEIGHT_QUESTION = 1.5
MSG_WEIGHT_ACTION_ITEM = 2.0
MSG_WEIGHT_UNIQUE_SENDER_BONUS = 1.0

# Patterns that suggest a message contains an action item or decision.
ACTION_ITEM_PATTERNS = [
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\baction item\b", re.IGNORECASE),
    re.compile(r"\bassigned to\b", re.IGNORECASE),
    re.compile(r"\bfollow up\b", re.IGNORECASE),
    re.compile(r"\bdeadline\b", re.IGNORECASE),
    re.compile(r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|EOD|end of day)\b", re.IGNORECASE),
    re.compile(r"\bplease\s+(do|handle|take care|review|check|update|fix|send|create|add)\b", re.IGNORECASE),
]

DECISION_PATTERNS = [
    re.compile(r"\b(decided|agreed|conclusion|resolved|going with|let'?s go with|final decision)\b", re.IGNORECASE),
    re.compile(r"\bwe('ll| will| should| are going to)\b", re.IGNORECASE),
    re.compile(r"\bapproved\b", re.IGNORECASE),
    re.compile(r"\bmerged\b", re.IGNORECASE),
]

QUESTION_PATTERNS = [
    re.compile(r"\?\s*$"),
    re.compile(r"\b(does anyone|can someone|who can|any thoughts|what do you think|opinions?|feedback)\b", re.IGNORECASE),
]


@dataclass
class ScoredMessage:
    """A message with an importance score for extractive selection."""

    message_id: int
    sender_full_name: str
    content: str
    date_sent: datetime
    score: float
    is_mentioned: bool = False
    is_action_item: bool = False
    is_decision: bool = False
    is_question: bool = False
    reaction_count: int = 0

    def to_dict(self) -> dict[str, object]:
        tags = []
        if self.is_mentioned:
            tags.append("mention")
        if self.is_action_item:
            tags.append("action_item")
        if self.is_decision:
            tags.append("decision")
        if self.is_question:
            tags.append("question")

        return {
            "id": self.message_id,
            "sender_full_name": self.sender_full_name,
            "content": self.content[:300],
            "date_sent": str(self.date_sent),
            "tags": tags,
            "reaction_count": self.reaction_count,
        }


def _has_pattern_match(text: str, patterns: list[re.Pattern[str]]) -> bool:
    """Check if text matches any pattern in the list."""
    return any(pattern.search(text) for pattern in patterns)


def _score_message(
    message: Message,
    is_first: bool,
    is_last: bool,
    is_mentioned: bool,
    is_wildcard_mentioned: bool,
    reaction_count: int,
    seen_senders: set[str],
) -> ScoredMessage:
    """Score a single message for extractive importance."""
    score = 0.0
    content = message.content

    # Mention signals.
    if is_mentioned:
        score += MSG_WEIGHT_MENTIONED
    if is_wildcard_mentioned:
        score += MSG_WEIGHT_WILDCARD_MENTIONED

    # Position signals.
    if is_first:
        score += MSG_WEIGHT_IS_FIRST
    if is_last:
        score += MSG_WEIGHT_IS_LAST

    # Reaction signals.
    score += reaction_count * MSG_WEIGHT_REACTION_COUNT

    # Content signals.
    is_question = _has_pattern_match(content, QUESTION_PATTERNS)
    is_action_item = _has_pattern_match(content, ACTION_ITEM_PATTERNS)
    is_decision = _has_pattern_match(content, DECISION_PATTERNS)

    if is_question:
        score += MSG_WEIGHT_QUESTION
    if is_action_item:
        score += MSG_WEIGHT_ACTION_ITEM
    if is_decision:
        score += MSG_WEIGHT_ACTION_ITEM

    # Sender diversity bonus: first message from a new sender gets a bonus.
    sender_name = message.sender.full_name
    if sender_name not in seen_senders:
        score += MSG_WEIGHT_UNIQUE_SENDER_BONUS
        seen_senders.add(sender_name)

    return ScoredMessage(
        message_id=message.id,
        sender_full_name=sender_name,
        content=content,
        date_sent=message.date_sent,
        score=score,
        is_mentioned=is_mentioned,
        is_action_item=is_action_item,
        is_decision=is_decision,
        is_question=is_question,
        reaction_count=reaction_count,
    )


def extract_key_messages(
    user_profile: UserProfile,
    stream_id: int,
    topic_name: str,
    since: datetime,
    max_messages: int = MAX_KEY_MESSAGES,
) -> list[dict[str, object]]:
    """Select the most important messages from a topic for extractive summary.

    This function:
    1. Fetches all messages in the topic since the given time
    2. Checks which messages mention the user
    3. Counts reactions per message
    4. Scores each message based on mentions, reactions, position,
       and content patterns (questions, action items, decisions)
    5. Returns the top N messages sorted by score

    Args:
        user_profile: The requesting user
        stream_id: The stream containing the topic
        topic_name: The topic to summarize
        since: Only consider messages after this time
        max_messages: Maximum number of key messages to return

    Returns:
        A list of message dicts with id, sender, content, date, tags,
        and reaction_count, sorted by score (highest first).
    """
    # Get the recipient ID for this stream.
    try:
        recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream_id)
    except Recipient.DoesNotExist:
        return []

    # Fetch messages in this topic since the cutoff.
    messages = list(
        Message.objects.filter(
            realm_id=user_profile.realm_id,
            recipient=recipient,
            subject__iexact=topic_name,
            date_sent__gt=since,
            is_channel_message=True,
        )
        .order_by("id")
        .select_related("sender")
    )

    if not messages:
        return []

    # Build sets of message IDs that have mention flags for this user.
    message_ids = [m.id for m in messages]
    mentioned_ids: set[int] = set()
    wildcard_mentioned_ids: set[int] = set()

    user_messages = UserMessage.objects.filter(
        user_profile=user_profile,
        message_id__in=message_ids,
    ).filter(
        Q(flags__andnz=UserMessage.flags.mentioned.mask)
        | Q(flags__andnz=UserMessage.flags.stream_wildcard_mentioned.mask)
        | Q(flags__andnz=UserMessage.flags.topic_wildcard_mentioned.mask)
    )

    for um in user_messages:
        if um.flags.mentioned:
            mentioned_ids.add(um.message_id)
        if um.flags.stream_wildcard_mentioned or um.flags.topic_wildcard_mentioned:
            wildcard_mentioned_ids.add(um.message_id)

    # Count reactions per message.
    reaction_counts: dict[int, int] = {}
    for row in (
        Reaction.objects.filter(message_id__in=message_ids)
        .values("message_id")
        .annotate(count=Count("id"))
    ):
        reaction_counts[row["message_id"]] = row["count"]

    # Score each message.
    first_id = messages[0].id
    last_id = messages[-1].id
    seen_senders: set[str] = set()

    scored: list[ScoredMessage] = []
    for message in messages:
        # Skip bot messages for summary purposes.
        if message.sender.is_bot:
            continue

        scored_msg = _score_message(
            message=message,
            is_first=(message.id == first_id),
            is_last=(message.id == last_id),
            is_mentioned=(message.id in mentioned_ids),
            is_wildcard_mentioned=(message.id in wildcard_mentioned_ids),
            reaction_count=reaction_counts.get(message.id, 0),
            seen_senders=seen_senders,
        )
        scored.append(scored_msg)

    # Select top N by score, then sort by chronological order for readability.
    top_messages = sorted(scored, key=lambda m: m.score, reverse=True)[:max_messages]
    top_messages.sort(key=lambda m: m.date_sent)

    return [msg.to_dict() for msg in top_messages]


def extract_keywords(messages: list[Message], max_keywords: int = 8) -> list[str]:
    """Extract the most frequent meaningful terms from a set of messages.

    A lightweight keyword extraction that identifies frequently-used
    non-stopword terms across the messages. Useful for giving users a
    quick sense of what a topic is about.

    Args:
        messages: The messages to extract keywords from
        max_keywords: Maximum number of keywords to return

    Returns:
        A list of keyword strings, most frequent first.
    """
    # Common English stopwords to filter out.
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "it", "that", "this",
        "was", "are", "be", "has", "have", "had", "not", "we", "you",
        "they", "he", "she", "its", "my", "your", "our", "their",
        "can", "will", "do", "does", "did", "should", "would", "could",
        "i", "me", "him", "her", "us", "them", "what", "which", "who",
        "when", "where", "how", "all", "each", "every", "both", "few",
        "more", "most", "other", "some", "such", "no", "nor", "only",
        "own", "same", "so", "than", "too", "very", "just", "if",
        "about", "up", "out", "as", "into", "through", "then", "here",
        "there", "been", "being", "were", "am", "also", "get", "got",
        "think", "like", "know", "yeah", "yes", "ok", "okay", "sure",
        "one", "two", "new", "see", "way", "make", "go", "going",
    }

    word_counts: dict[str, int] = {}
    word_pattern = re.compile(r"[a-zA-Z]{3,}")

    for message in messages:
        # Use raw content (Markdown), strip code blocks.
        content = re.sub(r"```.*?```", "", message.content, flags=re.DOTALL)
        content = re.sub(r"`[^`]+`", "", content)

        words = word_pattern.findall(content.lower())
        for word in words:
            if word not in stopwords and len(word) <= 30:
                word_counts[word] = word_counts.get(word, 0) + 1

    # Sort by frequency, take top N.
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _count in sorted_words[:max_keywords]]

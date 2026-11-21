"""
Prototype digest variants for the /digest page, for comparing ways to
put together a digest. Not used for sent emails.

Content variants:
  a: Everything, compactly: an index of all unread topics, by channel.
  b: Recents: the 10 most recently active topics.
  c: For you: topics ranked by personal signals, top few expanded.
  d: While you were away: a summary, resolved topics, busiest channels.

Presentations:
  single: the chosen variant.
  mixed: summary, then "For you", then highlights, then everything else.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from django.db.models import Max, Min
from django.db.models.functions import Lower
from django.utils.timezone import now as timezone_now

from zerver.lib.digest import (
    get_hot_topics,
    get_recent_topics,
    get_user_muted_topics_map,
    get_user_stream_map,
)
from zerver.lib.email_notifications import MessageListPayload, build_message_list
from zerver.lib.stream_color import StreamColors
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX, get_topic_display_name
from zerver.lib.url_encoding import stream_narrow_url, topic_narrow_url
from zerver.models import (
    Message,
    Reaction,
    Recipient,
    Stream,
    UserMessage,
    UserProfile,
    Subscription,
    UserTopic,
)

DIGEST_DEMO_STRATEGIES = {
    "current": "Current",
    "a": "All unread",
    "b": "Recents",
    "c": "For you",
    "d": "While away",
}
DIGEST_DEMO_PRESENTATIONS = {
    "single": "One format",
    "mixed": "Mixed",
}
DIGEST_DEMO_INTROS = {
    "default": "Default",
    "custom": "Custom",
    "none": "None",
}

# Email notification settings to preview the digest with, as
# (mention emails, followed topic emails, channel emails); None means
# the viewer's own settings.
DIGEST_DEMO_EMAIL_SETTINGS: dict[str, tuple[str, tuple[bool, bool, bool] | None]] = {
    "mine": ("My settings", None),
    "none": ("None", (False, False, False)),
    "mentions": ("Mentions", (True, False, False)),
    "default": ("Mentions + followed", (True, True, False)),
    "all": ("Everything", (True, True, True)),
}

# Example of an introduction an organization administrator might write
# to replace the default one.
DEMO_CUSTOM_INTRO = (
    "Welcome back to {realm_name}! Our community call is every Thursday at "
    "16:00 UTC, and new members are always welcome to say hi in #social."
)

EXPANDED_TOPICS = 4
RECENT_TOPICS = 10

ANY_MENTION_MASK = (
    UserMessage.flags.mentioned.mask
    | UserMessage.flags.stream_wildcard_mentioned.mask
    | UserMessage.flags.topic_wildcard_mentioned.mask
    | UserMessage.flags.group_mentioned.mask
)


@dataclass
class DemoTopic:
    stream: Stream
    topic_name: str
    messages: list[Message] = field(default_factory=list)
    unread_count: int = 0
    mentioned: bool = False
    starred: bool = False
    followed: bool = False
    replied_to_you: bool = False
    started_by_you: bool = False
    in_your_channel: bool = False
    channel_emails: bool = False
    reaction_count: int = 0

    @property
    def stream_id(self) -> int:
        return self.stream.id

    @property
    def resolved(self) -> bool:
        return self.topic_name.startswith(RESOLVED_TOPIC_PREFIX)

    @property
    def human_messages(self) -> list[Message]:
        return [message for message in self.messages if not message.sender.is_bot]

    @property
    def activity_score(self) -> int:
        # Tim's suggested weights (#12315): more people talking counts
        # for much more than more messages, so long back-and-forths
        # between two people don't take over.
        return 20 * len(self.participants) + 3 * len(self.human_messages) + 10 * self.reaction_count

    @property
    def participants(self) -> list[str]:
        return sorted({message.sender.full_name for message in self.human_messages})

    @property
    def last_active(self) -> datetime:
        return self.messages[-1].date_sent

    def emailed_about(
        self, user: UserProfile, email_settings: tuple[bool, bool, bool] | None
    ) -> bool:
        # Whether the person was already sent an email notification
        # for this topic, going by their notification settings: digests
        # only go to people who have been away, so those emails went out.
        if email_settings is None:
            mention_emails = user.enable_offline_email_notifications
            followed_emails = user.enable_followed_topic_email_notifications
            channel_emails = self.channel_emails
        else:
            mention_emails, followed_emails, channel_emails = email_settings
        return (
            channel_emails
            or (self.mentioned and mention_emails)
            or (self.followed and followed_emails)
        )

    @property
    def tier(self) -> int:
        if self.mentioned or self.starred:
            return 1
        if self.replied_to_you or self.followed:
            return 2
        if self.started_by_you or self.in_your_channel:
            return 3
        return 4

    @property
    def reasons(self) -> list[str]:
        reasons = []
        if self.mentioned:
            reasons.append("Mentions you")
        if self.starred:
            reasons.append("You starred")
        if self.replied_to_you:
            reasons.append("Replies to you")
        # Topics you start are followed by default, so "You started"
        # says more than "You follow".
        if self.started_by_you:
            reasons.append("You started")
        elif self.followed:
            reasons.append("You follow")
        if self.in_your_channel and not reasons:
            reasons.append("Channel you're active in")
        return reasons


@dataclass
class DemoConversation:
    """Same shape as DigestTeaserData, for the shared conversation card."""

    stream_id: int
    participants: list[str]
    count: int
    first_few_messages: MessageListPayload
    topic_url: str
    reasons: list[str]


@dataclass
class DemoIndexRow:
    topic: DemoTopic
    topic_display_name: str
    topic_url: str
    stream_url: str
    latest: Message

    @property
    def age(self) -> str:
        seconds = (timezone_now() - self.latest.date_sent).total_seconds()
        if seconds < 3600:
            return f"{max(1, int(seconds // 60))} min ago"
        if seconds < 86400:
            return f"{int(seconds // 3600)} h ago"
        days = int(seconds // 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"


def gather_demo_topics(
    user: UserProfile, cutoff_date: datetime
) -> tuple[list[DemoTopic], dict[int, StreamColors]]:
    stream_colors = get_user_stream_map([user.id], cutoff_date)[user.id]
    muted_topics = get_user_muted_topics_map([user.id])[user.id]
    stream_ids = set(stream_colors)
    streams = {stream.id: stream for stream in Stream.objects.filter(id__in=stream_ids)}

    messages = (
        Message.objects.filter(
            realm_id=user.realm_id,
            recipient__type=Recipient.STREAM,
            recipient__type_id__in=stream_ids,
            date_sent__gt=cutoff_date,
        )
        .select_related("sender", "recipient")
        .order_by("id")
    )

    topics: dict[tuple[int, str], DemoTopic] = {}
    for message in messages:
        stream_id = message.recipient.type_id
        key = (stream_id, message.topic_name().lower())
        if key in muted_topics:
            continue
        if key not in topics:
            topics[key] = DemoTopic(stream=streams[stream_id], topic_name=message.topic_name())
        topics[key].messages.append(message)

    message_topic = {
        message.id: key for key, topic in topics.items() for message in topic.messages
    }
    for message_id, flags in UserMessage.objects.filter(
        user_profile=user, message_id__in=message_topic
    ).values_list("message_id", "flags"):
        topic = topics[message_topic[message_id]]
        if not flags & UserMessage.flags.read.mask:
            topic.unread_count += 1
        if flags & ANY_MENTION_MASK:
            topic.mentioned = True
        if flags & UserMessage.flags.starred.mask:
            topic.starred = True

    for stream_id, topic_name in UserTopic.objects.filter(
        user_profile=user, visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED
    ).values_list("stream_id", "topic_name"):
        if (stream_id, topic_name.lower()) in topics:
            topics[(stream_id, topic_name.lower())].followed = True

    recipient_ids = {topic.messages[0].recipient_id for topic in topics.values()}
    stream_by_recipient = {
        topic.messages[0].recipient_id: topic.stream_id for topic in topics.values()
    }

    # Who started each topic, across all of its history.
    first_message_ids = [
        row["first_id"]
        for row in Message.objects.filter(recipient_id__in=recipient_ids)
        .values("recipient_id", topic_lower=Lower("subject"))
        .annotate(first_id=Min("id"))
        if (stream_by_recipient[row["recipient_id"]], row["topic_lower"]) in topics
    ]
    for message in Message.objects.filter(id__in=first_message_ids, sender=user).select_related(
        "recipient"
    ):
        topics[(message.recipient.type_id, message.topic_name().lower())].started_by_you = True

    # Topics where someone else posted after your latest message.
    for row in (
        Message.objects.filter(recipient_id__in=recipient_ids, sender=user)
        .values("recipient_id", topic_lower=Lower("subject"))
        .annotate(last_id=Max("id"))
    ):
        key = (stream_by_recipient[row["recipient_id"]], row["topic_lower"])
        if key in topics and any(
            message.id > row["last_id"] and message.sender_id != user.id
            for message in topics[key].human_messages
        ):
            topics[key].replied_to_you = True

    # The channels you've posted in most over the last 30 days.
    your_channel_counts = Counter(
        Message.objects.filter(
            recipient_id__in=recipient_ids,
            sender=user,
            date_sent__gt=timezone_now() - timedelta(days=30),
        ).values_list("recipient_id", flat=True)
    )
    your_channels = {
        stream_by_recipient[recipient_id] for recipient_id, _ in your_channel_counts.most_common(3)
    }
    for topic in topics.values():
        topic.in_your_channel = topic.stream_id in your_channels

    for message_id in Reaction.objects.filter(message_id__in=message_topic).values_list(
        "message_id", flat=True
    ):
        topics[message_topic[message_id]].reaction_count += 1

    # Channels whose messages are emailed to you.
    channel_email_settings = dict(
        Subscription.objects.filter(
            user_profile=user, recipient__type=Recipient.STREAM, recipient__type_id__in=stream_ids
        ).values_list("recipient__type_id", "email_notifications")
    )
    for topic in topics.values():
        setting = channel_email_settings.get(topic.stream_id)
        topic.channel_emails = (
            user.enable_stream_email_notifications if setting is None else setting
        )

    return list(topics.values()), stream_colors


def for_you_order(topics: list[DemoTopic]) -> list[DemoTopic]:
    # Tiers 1-2 are things waiting on you: oldest first. Tiers 3-4
    # are general activity: highest activity score first. Unread
    # before read.
    def key(topic: DemoTopic) -> tuple[int, int, int]:
        if topic.tier <= 2:
            return (topic.tier, topic.unread_count == 0, topic.messages[0].id)
        return (topic.tier, topic.unread_count == 0, -topic.activity_score)

    return sorted(topics, key=key)


def build_conversation(user: UserProfile, topic: DemoTopic, latest: bool) -> DemoConversation:
    # Show the latest two messages, where the outcome usually is, or the
    # first two, as the current digest does.
    shown = topic.messages[-2:] if latest else topic.messages[:2]
    return DemoConversation(
        stream_id=topic.stream_id,
        participants=topic.participants,
        count=len(topic.messages) - len(shown),
        first_few_messages=build_message_list(
            user,
            list(shown),
            stream_id_map={topic.stream_id: topic.stream},
            with_sender_avatars=True,
        ),
        topic_url=topic_narrow_url(realm=user.realm, stream=topic.stream, topic_name=topic.topic_name),
        reasons=topic.reasons,
    )


def build_index(user: UserProfile, topics: list[DemoTopic]) -> list[tuple[Stream, list[DemoIndexRow]]]:
    by_stream: dict[int, list[DemoIndexRow]] = defaultdict(list)
    streams = {}
    for topic in topics:
        streams[topic.stream_id] = topic.stream
        by_stream[topic.stream_id].append(
            DemoIndexRow(
                topic=topic,
                topic_display_name=get_topic_display_name(topic.topic_name, user.default_language),
                topic_url=topic_narrow_url(
                    realm=user.realm, stream=topic.stream, topic_name=topic.topic_name
                ),
                stream_url=stream_narrow_url(user.realm, topic.stream),
                latest=topic.messages[-1],
            )
        )
    return [
        (streams[stream_id], sorted(rows, key=lambda row: -row.topic.unread_count))
        for stream_id, rows in sorted(by_stream.items(), key=lambda item: streams[item[0]].name.lower())
    ]


def build_rows(user: UserProfile, topics: list[DemoTopic]) -> list[DemoIndexRow]:
    return [
        DemoIndexRow(
            topic=topic,
            topic_display_name=get_topic_display_name(topic.topic_name, user.default_language),
            topic_url=topic_narrow_url(
                realm=user.realm, stream=topic.stream, topic_name=topic.topic_name
            ),
            stream_url=stream_narrow_url(user.realm, topic.stream),
            latest=topic.messages[-1],
        )
        for topic in topics
    ]


def build_summary(
    user: UserProfile, topics: list[DemoTopic], away_since: datetime, new_channels_count: int
) -> dict[str, object]:
    window = [topic for topic in topics if topic.last_active > away_since]
    channel_counts = Counter(topic.stream for topic in window for _ in topic.messages)
    return {
        "days": max(1, (timezone_now() - away_since).days),
        "topics": len(window),
        "messages": sum(len(topic.messages) for topic in window),
        "channels": len({topic.stream_id for topic in window}),
        "new_channels": new_channels_count,
        "new_members": UserProfile.objects.filter(
            realm=user.realm, is_bot=False, is_active=True, date_joined__gt=away_since
        ).count(),
        "busiest": channel_counts.most_common(5),
        "resolved": build_rows(user, [topic for topic in window if topic.resolved]),
    }


def get_digest_demo_context(
    user: UserProfile,
    cutoff: float,
    strategy: str,
    presentation: str,
    intro: str,
    email_settings: str,
    new_channels_count: int,
) -> dict[str, object]:
    cutoff_date = datetime.fromtimestamp(int(cutoff), tz=timezone.utc)
    all_topics, stream_colors = gather_demo_topics(user, cutoff_date)
    # Leave out what the person was already emailed about.
    settings = DIGEST_DEMO_EMAIL_SETTINGS[email_settings][1]
    emailed = [topic for topic in all_topics if topic.emailed_about(user, settings)]
    topics = [topic for topic in all_topics if not topic.emailed_about(user, settings)]
    # Digests only go to people inactive since the cutoff, so the
    # cutoff is when they were last here.
    away_since = cutoff_date
    ranked = for_you_order(topics)
    unread = [topic for topic in ranked if topic.unread_count > 0]

    context: dict[str, object] = {
        "digest_demo": True,
        "digest_strategy": strategy,
        "digest_presentation": presentation,
        "digest_strategies": DIGEST_DEMO_STRATEGIES,
        "digest_intro": intro,
        "digest_custom_intro": DEMO_CUSTOM_INTRO.format(realm_name=user.realm.name),
        "channel_colors": {topic.stream_id: stream_colors[topic.stream_id] for topic in all_topics},
        "summary": build_summary(user, all_topics, away_since, new_channels_count),
        "emailed_topics": build_rows(user, emailed),
    }

    if presentation == "mixed":
        for_you = [topic for topic in ranked if topic.tier <= 2][:EXPANDED_TOPICS]
        # The current digest's pick, among topics not already shown.
        recent_topics = [
            digest_topic
            for stream_id in stream_colors
            for digest_topic in get_recent_topics(user.realm_id, stream_id, cutoff_date)
        ]
        shown_keys = {(topic.stream_id, topic.topic_name.lower()) for topic in for_you}
        hot_keys = [
            (digest_topic.stream_id(), digest_topic.topic_name().lower())
            for digest_topic in get_hot_topics(recent_topics, set(stream_colors))
        ]
        topics_by_key = {(topic.stream_id, topic.topic_name.lower()): topic for topic in topics}
        highlights = [
            topics_by_key[key]
            for key in hot_keys
            if key not in shown_keys and key in topics_by_key
        ]
        shown_keys |= {(topic.stream_id, topic.topic_name.lower()) for topic in highlights}
        context.update(
            for_you=[build_conversation(user, topic, latest=True) for topic in for_you],
            highlights=[build_conversation(user, topic, latest=False) for topic in highlights],
            index=build_index(
                user,
                [
                    topic
                    for topic in unread
                    if (topic.stream_id, topic.topic_name.lower()) not in shown_keys
                ],
            ),
        )
        return context

    if strategy == "a":
        context["index"] = build_index(user, unread)
        context["unread_total"] = sum(topic.unread_count for topic in unread)
    elif strategy == "b":
        recents = sorted(topics, key=lambda topic: topic.last_active, reverse=True)
        context["recents"] = build_rows(user, recents[:RECENT_TOPICS])
        context["recents_more"] = max(0, len(recents) - RECENT_TOPICS)
    elif strategy == "c":
        context["for_you"] = [
            build_conversation(user, topic, latest=True) for topic in ranked[:EXPANDED_TOPICS]
        ]
        context["for_you_rest"] = build_rows(user, ranked[EXPANDED_TOPICS:])
    return context

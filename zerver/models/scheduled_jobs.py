# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

from typing import List, TypedDict, Union

from django.conf import settings
from django.db import models
from django.db.models import CASCADE, Q
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.display_recipient import get_recipient_ids
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models.clients import Client
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.groups import NamedUserGroup
from zerver.models.messages import Message
from zerver.models.realms import Realm
from zerver.models.recipients import Recipient
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


class AbstractScheduledJob(models.Model):
    scheduled_timestamp = models.DateTimeField(db_index=True)
    # JSON representation of arguments to consumer
    data = models.TextField()
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    class Meta:
        abstract = True


class ScheduledEmail(AbstractScheduledJob):
    # Exactly one of users or address should be set. These are
    # duplicate values, used to efficiently filter the set of
    # ScheduledEmails for use in clear_scheduled_emails; the
    # recipients used for actually sending messages are stored in the
    # data field of AbstractScheduledJob.
    users = models.ManyToManyField(UserProfile)
    # Just the address part of a full "name <address>" email address
    address = models.EmailField(null=True, db_index=True)

    # Valid types are below
    WELCOME = 1
    DIGEST = 2
    INVITATION_REMINDER = 3
    type = models.PositiveSmallIntegerField()

    @override
    def __str__(self) -> str:
        return f"{self.type} {self.address or list(self.users.all())} {self.scheduled_timestamp}"


class MissedMessageEmailAddress(models.Model):
    message = models.ForeignKey(Message, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    email_token = models.CharField(max_length=34, unique=True, db_index=True)

    # Timestamp of when the missed message address generated.
    timestamp = models.DateTimeField(db_index=True, default=timezone_now)
    # Number of times the missed message address has been used.
    times_used = models.PositiveIntegerField(default=0, db_index=True)

    @override
    def __str__(self) -> str:
        return settings.EMAIL_GATEWAY_PATTERN % (self.email_token,)

    def increment_times_used(self) -> None:
        self.times_used += 1
        self.save(update_fields=["times_used"])


class NotificationTriggers:
    # "direct_message" is for 1:1 direct messages as well as huddles
    DIRECT_MESSAGE = "direct_message"
    MENTION = "mentioned"
    TOPIC_WILDCARD_MENTION = "topic_wildcard_mentioned"
    STREAM_WILDCARD_MENTION = "stream_wildcard_mentioned"
    STREAM_PUSH = "stream_push_notify"
    STREAM_EMAIL = "stream_email_notify"
    FOLLOWED_TOPIC_PUSH = "followed_topic_push_notify"
    FOLLOWED_TOPIC_EMAIL = "followed_topic_email_notify"
    TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC = "topic_wildcard_mentioned_in_followed_topic"
    STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC = "stream_wildcard_mentioned_in_followed_topic"


class ScheduledMessageNotificationEmail(models.Model):
    """Stores planned outgoing message notification emails. They may be
    processed earlier should Zulip choose to batch multiple messages
    in a single email, but typically will be processed just after
    scheduled_timestamp.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    message = models.ForeignKey(Message, on_delete=CASCADE)

    EMAIL_NOTIFICATION_TRIGGER_CHOICES = [
        (NotificationTriggers.DIRECT_MESSAGE, "Direct message"),
        (NotificationTriggers.MENTION, "Mention"),
        (NotificationTriggers.TOPIC_WILDCARD_MENTION, "Topic wildcard mention"),
        (NotificationTriggers.STREAM_WILDCARD_MENTION, "Stream wildcard mention"),
        (NotificationTriggers.STREAM_EMAIL, "Stream notifications enabled"),
        (NotificationTriggers.FOLLOWED_TOPIC_EMAIL, "Followed topic notifications enabled"),
        (
            NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
            "Topic wildcard mention in followed topic",
        ),
        (
            NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
            "Stream wildcard mention in followed topic",
        ),
    ]

    trigger = models.TextField(choices=EMAIL_NOTIFICATION_TRIGGER_CHOICES)
    mentioned_user_group = models.ForeignKey(NamedUserGroup, null=True, on_delete=CASCADE)

    # Timestamp for when the notification should be processed and sent.
    # Calculated from the time the event was received and the batching period.
    scheduled_timestamp = models.DateTimeField(db_index=True)


class APIScheduledStreamMessageDict(TypedDict):
    scheduled_message_id: int
    to: int
    type: str
    content: str
    rendered_content: str
    topic: str
    scheduled_delivery_timestamp: int
    failed: bool


class APIScheduledDirectMessageDict(TypedDict):
    scheduled_message_id: int
    to: List[int]
    type: str
    content: str
    rendered_content: str
    scheduled_delivery_timestamp: int
    failed: bool


class ScheduledMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    subject = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    content = models.TextField()
    rendered_content = models.TextField()
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    scheduled_timestamp = models.DateTimeField(db_index=True)
    read_by_sender = models.BooleanField()
    delivered = models.BooleanField(default=False)
    delivered_message = models.ForeignKey(Message, null=True, on_delete=CASCADE)
    has_attachment = models.BooleanField(default=False, db_index=True)

    # Metadata for messages that failed to send when their scheduled
    # moment arrived.
    failed = models.BooleanField(default=False)
    failure_message = models.TextField(null=True)

    SEND_LATER = 1
    REMIND = 2

    DELIVERY_TYPES = (
        (SEND_LATER, "send_later"),
        (REMIND, "remind"),
    )

    delivery_type = models.PositiveSmallIntegerField(
        choices=DELIVERY_TYPES,
        default=SEND_LATER,
    )

    class Meta:
        indexes = [
            # We expect a large number of delivered scheduled messages
            # to accumulate over time. This first index is for the
            # deliver_scheduled_messages worker.
            models.Index(
                name="zerver_unsent_scheduled_messages_by_time",
                fields=["scheduled_timestamp"],
                condition=Q(
                    delivered=False,
                    failed=False,
                ),
            ),
            # This index is for displaying scheduled messages to the
            # user themself via the API; we don't filter failed
            # messages since we will want to display those so that
            # failures don't just disappear into a black hole.
            models.Index(
                name="zerver_realm_unsent_scheduled_messages_by_user",
                fields=["realm_id", "sender", "delivery_type", "scheduled_timestamp"],
                condition=Q(
                    delivered=False,
                ),
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.recipient.label()} {self.subject} {self.sender!r} {self.scheduled_timestamp}"

    def topic_name(self) -> str:
        return self.subject

    def set_topic_name(self, topic_name: str) -> None:
        self.subject = topic_name

    def is_stream_message(self) -> bool:
        return self.recipient.type == Recipient.STREAM

    def to_dict(self) -> Union[APIScheduledStreamMessageDict, APIScheduledDirectMessageDict]:
        recipient, recipient_type_str = get_recipient_ids(self.recipient, self.sender.id)

        if recipient_type_str == "private":
            # The topic for direct messages should always be an empty string.
            assert self.topic_name() == ""

            return APIScheduledDirectMessageDict(
                scheduled_message_id=self.id,
                to=recipient,
                type=recipient_type_str,
                content=self.content,
                rendered_content=self.rendered_content,
                scheduled_delivery_timestamp=datetime_to_timestamp(self.scheduled_timestamp),
                failed=self.failed,
            )

        # The recipient for stream messages should always just be the unique stream ID.
        assert len(recipient) == 1

        return APIScheduledStreamMessageDict(
            scheduled_message_id=self.id,
            to=recipient[0],
            type=recipient_type_str,
            content=self.content,
            rendered_content=self.rendered_content,
            topic=self.topic_name(),
            scheduled_delivery_timestamp=datetime_to_timestamp(self.scheduled_timestamp),
            failed=self.failed,
        )


EMAIL_TYPES = {
    "account_registered": ScheduledEmail.WELCOME,
    "onboarding_zulip_topics": ScheduledEmail.WELCOME,
    "onboarding_zulip_guide": ScheduledEmail.WELCOME,
    "onboarding_team_to_zulip": ScheduledEmail.WELCOME,
    "digest": ScheduledEmail.DIGEST,
    "invitation_reminder": ScheduledEmail.INVITATION_REMINDER,
}

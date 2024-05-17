from datetime import datetime, timezone

from django.db import models
from django.db.models import CASCADE
from django.db.models.functions import Lower, Upper
from typing_extensions import override

from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.recipients import Recipient
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


class UserTopic(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    topic_name = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    # The default value for last_updated is a few weeks before tracking
    # of when topics were muted was first introduced.  It's designed
    # to be obviously incorrect so that one can tell it's backfilled data.
    last_updated = models.DateTimeField(default=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc))

    class VisibilityPolicy(models.IntegerChoices):
        # A normal muted topic. No notifications and unreads hidden.
        MUTED = 1, "Muted topic"

        # This topic will behave like an unmuted topic in an unmuted stream even if it
        # belongs to a muted stream.
        UNMUTED = 2, "Unmuted topic in muted stream"

        # This topic will behave like `UNMUTED`, plus some additional
        # display and/or notifications priority that is TBD and likely to
        # be configurable; see #6027. Not yet implemented.
        FOLLOWED = 3, "Followed topic"

        # Implicitly, if a UserTopic does not exist, the (user, topic)
        # pair should have normal behavior for that (user, stream) pair.

        # We use this in our code to represent the condition in the comment above.
        INHERIT = 0, "User's default policy for the stream."

    visibility_policy = models.SmallIntegerField(
        choices=VisibilityPolicy.choices, default=VisibilityPolicy.MUTED
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "user_profile",
                "stream",
                Lower("topic_name"),
                name="usertopic_case_insensitive_topic_uniq",
            ),
        ]

        indexes = [
            models.Index("stream", Upper("topic_name"), name="zerver_mutedtopic_stream_topic"),
            # This index is designed to optimize queries fetching the
            # set of users who have special policy for a stream,
            # e.g. for the send-message code paths.
            models.Index(
                fields=("stream", "topic_name", "visibility_policy", "user_profile"),
                name="zerver_usertopic_stream_topic_user_visibility_idx",
            ),
            # This index is useful for handling API requests fetching the
            # muted topics for a given user or user/stream pair.
            models.Index(
                fields=("user_profile", "visibility_policy", "stream", "topic_name"),
                name="zerver_usertopic_user_visibility_idx",
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"({self.user_profile.email}, {self.stream.name}, {self.topic_name}, {self.last_updated})"

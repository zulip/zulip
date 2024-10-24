from datetime import datetime, timezone

from django.db import models
from django.db.models import CASCADE
from django.db.models.functions import Lower
from typing_extensions import override

from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.realms import Realm
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


class TopicSettings(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)
    topic_name = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    is_locked = models.BooleanField(default=False)

    # Timestamp for when the settings were last updated
    last_updated = models.DateTimeField(default=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "realm",
                "user_profile",
                "stream",
                Lower("topic_name"),
                name="topicsettings_case_insensitive_topic_uniq",
            ),
        ]
        indexes = [
            models.Index(
                "realm", "stream", Lower("topic_name"), name="topicsettings_stream_topic_idx"
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"(Realm ID: {self.realm.id}, Stream: {self.stream.name}, Topic: {self.topic_name}, Locked: {self.is_locked})"

from django.db import models
from django.db.models import CASCADE, QuerySet
from django.db.models.functions import Lower, Upper

from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.realms import Realm
from zerver.models.streams import Stream


class Topic(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, db_index=True, on_delete=CASCADE)
    name = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    pinned = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "realm",
                "stream",
                Lower("name"),
                name="case_insensitive_topic_uniq",
            ),
        ]

        indexes = [
            models.Index("realm", "stream", Upper("name"), name="zerver_pinnedtopic_stream_topic"),
        ]


def get_topic_pins(realm: Realm) -> QuerySet[Topic]:
    return Topic.objects.filter(realm=realm, pinned=True)

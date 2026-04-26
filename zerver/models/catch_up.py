from django.db import models
from django.db.models import CASCADE

from zerver.models.clients import Client
from zerver.models.realms import Realm
from zerver.models.users import UserProfile


class CatchUpSession(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    client = models.ForeignKey(Client, on_delete=CASCADE)

    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(db_index=True)
    duration_ms = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index(
                fields=["realm", "ended_at"],
                name="zerver_catchupsess_realm_id_ended_at_9f5c0c3a_idx",
            ),
            models.Index(
                fields=["user_profile", "ended_at"],
                name="zerver_catchupsess_user_profile_id_ended_at_d2e8f3d0_idx",
            ),
        ]


class CatchUpSessionItem(models.Model):
    STREAM_TOPIC = 1
    DM_PERSONAL = 2
    DM_GROUP = 3

    ITEM_TYPE_CHOICES = [
        (STREAM_TOPIC, "stream_topic"),
        (DM_PERSONAL, "dm_personal"),
        (DM_GROUP, "dm_group"),
    ]

    session = models.ForeignKey(CatchUpSession, on_delete=CASCADE, related_name="items")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    item_type = models.PositiveSmallIntegerField(choices=ITEM_TYPE_CHOICES)

    # Stream topic fields.
    stream_id = models.IntegerField(null=True)
    topic_name = models.TextField(null=True)

    # 1:1 DM fields (incoming DMs grouped by sender).
    dm_sender_id = models.IntegerField(null=True)
    # Group DM fields (recipient.id for the DIRECT_MESSAGE_GROUP recipient).
    dm_recipient_id = models.IntegerField(null=True)

    first_message_id = models.PositiveIntegerField()
    last_message_id = models.PositiveIntegerField()
    message_count = models.PositiveIntegerField()
    unread_count_at_surface = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index(
                fields=["session", "created_at"],
                name="zerver_catchupsessitem_session_id_created_at_7bd85a6d_idx",
            ),
        ]

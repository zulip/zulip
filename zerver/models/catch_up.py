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

from datetime import timedelta

from django.db import models
from django.db.models import CASCADE

from zerver.models.clients import Client
from zerver.models.users import UserProfile


class UserActivity(models.Model):
    """Data table recording the last time each user hit Zulip endpoints
    via which Clients; unlike UserPresence, these data are not exposed
    to users via the Zulip API.

    Useful for debugging as well as to answer analytics questions like
    "How many users have accessed the Zulip mobile app in the last
    month?" or "Which users/organizations have recently used API
    endpoint X that is about to be desupported" for communications
    and database migration purposes.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    client = models.ForeignKey(Client, on_delete=CASCADE)
    query = models.CharField(max_length=50, db_index=True)

    count = models.IntegerField()
    last_visit = models.DateTimeField("last visit")

    class Meta:
        unique_together = ("user_profile", "client", "query")


class UserActivityInterval(models.Model):
    MIN_INTERVAL_LENGTH = timedelta(minutes=15)

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    start = models.DateTimeField("start time", db_index=True)
    end = models.DateTimeField("end time", db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user_profile", "end"],
                name="zerver_useractivityinterval_user_profile_id_end_bb3bfc37_idx",
            ),
        ]

from django.db import models
from django.db.models.functions import Now
from django.utils.timezone import now as timezone_now

from zerver.models.realms import Realm
from zerver.models.users import UserProfile


class IdempotentRequest(models.Model):
    """Ensure idempotency for Non-Idempotent (e.g. POST) requests.

    Currently, only used for message sending, but in the future it should be applied to
    any http request having the possibility of being wrongly replayed.
    """

    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # This is client-provided.
    idempotency_key = models.UUIDField(db_index=True)

    # We use both Now() and timezone_now to ensure timestamp is auto created
    # when inserting via raw SQL and Django, respectively.
    timestamp = models.DateTimeField(db_default=Now(), default=timezone_now, db_index=True)

    # This identifies the ID of the work for which we want to ensure idempotency (e.g. message.id).
    # Null: work not done.
    # Not Null: work is done and succeeded/failed.
    identifier = models.IntegerField(null=True, db_index=True)

    # Currently, this is the cached result of the work, not the json response itself.
    cached_response = models.JSONField(default=None, null=True)

    # Rows with timestamp later than this should be deleted.
    # TODO: Should be used by a cron job.
    EXPIRE_AFTER = 60 * 60  # Time in seconds.

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "user", "idempotency_key"],
                name="unique_realm_user_idempotency_key",
            ),
        ]

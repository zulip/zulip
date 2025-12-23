from django.db import models
from django.db.models.functions import Now
from django.utils.timezone import now as timezone_now

from zerver.models.realms import Realm
from zerver.models.users import UserProfile


class IdempotentRequest(models.Model):
    """Ensure idempotency for non-idempotent (e.g. POST) requests.

    Currently, only used for message sending, but in the future it should be applied to
    any non-idempotent http request having the possibility of being wrongly replayed.
    """

    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # Only client-provided.
    idempotency_key = models.UUIDField(db_index=True)

    # We use both Now() and timezone_now to ensure timestamp is auto created
    # when inserting via raw SQL and Django, respectively.
    timestamp = models.DateTimeField(db_default=Now(), default=timezone_now, db_index=True)

    # The cache of successful response or the json error.
    cached_result = models.JSONField(default=None, null=True)

    # None if the work has not yet been attempted.
    succeeded = models.BooleanField(default=None, null=True)

    # The retention period, in hours, after which rows are considered expired
    # and eligible for deletion by the cron job.
    RETENTION_DURATION_IN_HRS = 24

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "user", "idempotency_key"],
                name="unique_realm_user_idempotency_key",
            ),
        ]

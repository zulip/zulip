from datetime import timedelta

from django.db import models
from django.utils.timezone import now as timezone_now

from zerver.models.realms import Realm
from zerver.models.users import UserProfile


class IdempotentRequest(models.Model):
    """The result of a request sent with an Idempotency-Key header,
    which is returned for replays of that request instead of redoing
    its work.
    """

    realm = models.ForeignKey(Realm, on_delete=models.CASCADE, db_index=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    idempotency_key = models.UUIDField()
    timestamp = models.DateTimeField(default=timezone_now, db_index=True)
    # None until the request's work has succeeded.
    cached_result = models.JSONField(null=True)

    RETENTION_PERIOD = timedelta(hours=24)

    class Meta:
        constraints = [
            # Clients choose their own keys, so different users may
            # send the same one.
            models.UniqueConstraint(
                fields=["realm", "user", "idempotency_key"],
                name="zerver_idempotentrequest_uniq",
            ),
        ]

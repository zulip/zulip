from django.db import models
from django.db.models import CASCADE

from zerver.models.users import UserProfile


class AbstractPushDeviceToken(models.Model):
    APNS = 1
    FCM = 2

    KINDS = (
        (APNS, "apns"),
        # The string value in the database is "gcm" for legacy reasons.
        # TODO: We should migrate it.
        (FCM, "gcm"),
    )

    kind = models.PositiveSmallIntegerField(choices=KINDS)

    # The token is a unique device-specific token that is
    # sent to us from each device:
    #   - APNS token if kind == APNS
    #   - FCM registration id if kind == FCM
    token = models.CharField(max_length=4096, db_index=True)

    # TODO: last_updated should be renamed date_created, since it is
    # no longer maintained as a last_updated value.
    last_updated = models.DateTimeField(auto_now=True)

    # [optional] Contains the app id of the device if it is an iOS device
    ios_app_id = models.TextField(null=True)

    class Meta:
        abstract = True


class PushDeviceToken(AbstractPushDeviceToken):
    # The user whose device this is
    user = models.ForeignKey(UserProfile, db_index=True, on_delete=CASCADE)

    class Meta:
        unique_together = ("user", "kind", "token")

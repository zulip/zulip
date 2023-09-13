from typing import List, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from analytics.models import BaseCount
from zerver.lib.rate_limiter import RateLimitedObject
from zerver.lib.rate_limiter import rules as rate_limiter_rules
from zerver.models import AbstractPushDeviceToken, AbstractRealmAuditLog


def get_remote_server_by_uuid(uuid: str) -> "RemoteZulipServer":
    try:
        return RemoteZulipServer.objects.get(uuid=uuid)
    except ValidationError:
        raise RemoteZulipServer.DoesNotExist


class RemoteZulipServer(models.Model):
    """Each object corresponds to a single remote Zulip server that is
    registered for the Mobile Push Notifications Service via
    `manage.py register_server`.
    """

    UUID_LENGTH = 36
    API_KEY_LENGTH = 64
    HOSTNAME_MAX_LENGTH = 128

    # The unique UUID (`zulip_org_id`) and API key (`zulip_org_key`)
    # for this remote server registration.
    uuid = models.UUIDField(unique=True)
    api_key = models.CharField(max_length=API_KEY_LENGTH)

    # The hostname and contact details are not verified/trusted. Thus,
    # they primarily exist so that we can communicate with the
    # maintainer of a server about abuse problems.
    hostname = models.CharField(max_length=HOSTNAME_MAX_LENGTH)
    contact_email = models.EmailField(blank=True, null=False)
    last_updated = models.DateTimeField("last updated", auto_now=True)

    # Whether the server registration has been deactivated.
    deactivated = models.BooleanField(default=False)

    # Plan types for self-hosted customers
    PLAN_TYPE_SELF_HOSTED = 1
    PLAN_TYPE_STANDARD = 102

    # The current billing plan for the remote server, similar to Realm.plan_type.
    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_HOSTED)

    def __str__(self) -> str:
        return f"{self.hostname} {str(self.uuid)[0:12]}"

    def format_requester_for_logs(self) -> str:
        return "zulip-server:" + str(self.uuid)


class RemotePushDeviceToken(AbstractPushDeviceToken):
    """Like PushDeviceToken, but for a device connected to a remote server."""

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    # The user id on the remote server for this device
    user_id = models.BigIntegerField(null=True)
    user_uuid = models.UUIDField(null=True)

    class Meta:
        unique_together = [
            # These indexes rely on the property that in Postgres,
            # NULL != NULL in the context of unique indexes, so multiple
            # rows with the same values in these columns can exist
            # if one of them is NULL.
            ("server", "user_id", "kind", "token"),
            ("server", "user_uuid", "kind", "token"),
        ]

    def __str__(self) -> str:
        return f"{self.server!r} {self.user_id}"


class RemoteZulipServerAuditLog(AbstractRealmAuditLog):
    """Audit data associated with a remote Zulip server (not specific to a
    realm).  Used primarily for tracking registration and billing
    changes for self-hosted customers.

    In contrast with RemoteRealmAuditLog, which has a copy of data
    that is generated on the client Zulip server, this table is the
    authoritative storage location for the server's history.
    """

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f"{self.server!r} {self.event_type} {self.event_time} {self.id}"


class RemoteRealmAuditLog(AbstractRealmAuditLog):
    """Synced audit data from a remote Zulip server, used primarily for
    billing.  See RealmAuditLog and AbstractRealmAuditLog for details.
    """

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    realm_id = models.IntegerField()
    # The remote_id field lets us deduplicate data from the remote server
    remote_id = models.IntegerField()

    def __str__(self) -> str:
        return f"{self.server!r} {self.event_type} {self.event_time} {self.id}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["server", "remote_id"],
                name="zilencer_remoterealmauditlog_server_remote",
            ),
        ]
        indexes = [
            models.Index(
                fields=["server", "realm_id", "remote_id"],
                name="zilencer_remoterealmauditlog_server_realm_remote",
            ),
        ]


class RemoteInstallationCount(BaseCount):
    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    # The remote_id field lets us deduplicate data from the remote server
    remote_id = models.IntegerField(db_index=True)

    class Meta:
        unique_together = ("server", "property", "subgroup", "end_time")
        indexes = [
            models.Index(
                fields=["server", "remote_id"],
                name="zilencer_remoteinstallat_server_id_remote_id_f72e4c30_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.property} {self.subgroup} {self.value}"


# We can't subclass RealmCount because we only have a realm_id here, not a foreign key.
class RemoteRealmCount(BaseCount):
    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    realm_id = models.IntegerField()
    # The remote_id field lets us deduplicate data from the remote server
    remote_id = models.IntegerField()

    class Meta:
        unique_together = ("server", "realm_id", "property", "subgroup", "end_time")
        indexes = [
            models.Index(
                fields=["property", "end_time"],
                name="zilencer_remoterealmcount_property_end_time_506a0b38_idx",
            ),
            models.Index(
                fields=["server", "remote_id"],
                name="zilencer_remoterealmcount_server_id_remote_id_de1573d8_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.server!r} {self.realm_id} {self.property} {self.subgroup} {self.value}"


class RateLimitedRemoteZulipServer(RateLimitedObject):
    def __init__(
        self, remote_server: RemoteZulipServer, domain: str = "api_by_remote_server"
    ) -> None:
        # Remote servers can only make API requests regarding push notifications
        # which requires ZILENCER_ENABLED and of course can't happen on API endpoints
        # inside Tornado.
        assert not settings.RUNNING_INSIDE_TORNADO
        assert settings.ZILENCER_ENABLED

        self.uuid = str(remote_server.uuid)
        self.domain = domain
        super().__init__()

    def key(self) -> str:
        return f"{type(self).__name__}:<{self.uuid}>:{self.domain}"

    def rules(self) -> List[Tuple[int, int]]:
        return rate_limiter_rules[self.domain]

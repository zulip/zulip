import datetime
from typing import List, Tuple

from django.conf import settings
from django.db import models

from analytics.models import BaseCount
from zerver.lib.rate_limiter import RateLimitedObject
from zerver.lib.rate_limiter import rules as rate_limiter_rules
from zerver.models import AbstractPushDeviceToken, AbstractRealmAuditLog


def get_remote_server_by_uuid(uuid: str) -> "RemoteZulipServer":
    return RemoteZulipServer.objects.get(uuid=uuid)


class RemoteZulipServer(models.Model):
    UUID_LENGTH = 36
    API_KEY_LENGTH = 64
    HOSTNAME_MAX_LENGTH = 128

    uuid: str = models.CharField(max_length=UUID_LENGTH, unique=True)
    api_key: str = models.CharField(max_length=API_KEY_LENGTH)

    hostname: str = models.CharField(max_length=HOSTNAME_MAX_LENGTH)
    contact_email: str = models.EmailField(blank=True, null=False)
    last_updated: datetime.datetime = models.DateTimeField("last updated", auto_now=True)

    def __str__(self) -> str:
        return f"<RemoteZulipServer {self.hostname} {self.uuid[0:12]}>"

    def format_requestor_for_logs(self) -> str:
        return "zulip-server:" + self.uuid


# Variant of PushDeviceToken for a remote server.
class RemotePushDeviceToken(AbstractPushDeviceToken):
    server: RemoteZulipServer = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    # The user id on the remote server for this device device this is
    user_id: int = models.BigIntegerField(db_index=True)

    class Meta:
        unique_together = ("server", "user_id", "kind", "token")

    def __str__(self) -> str:
        return f"<RemotePushDeviceToken {self.server} {self.user_id}>"


class RemoteRealmAuditLog(AbstractRealmAuditLog):
    """Synced audit data from a remote Zulip server, used primarily for
    billing.  See RealmAuditLog and AbstractRealmAuditLog for details.
    """

    server: RemoteZulipServer = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    realm_id: int = models.IntegerField(db_index=True)
    # The remote_id field lets us deduplicate data from the remote server
    remote_id: int = models.IntegerField(db_index=True)

    def __str__(self) -> str:
        return f"<RemoteRealmAuditLog: {self.server} {self.event_type} {self.event_time} {self.id}>"


class RemoteInstallationCount(BaseCount):
    server: RemoteZulipServer = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    # The remote_id field lets us deduplicate data from the remote server
    remote_id: int = models.IntegerField(db_index=True)

    class Meta:
        unique_together = ("server", "property", "subgroup", "end_time")
        index_together = [
            ["server", "remote_id"],
        ]

    def __str__(self) -> str:
        return f"<InstallationCount: {self.property} {self.subgroup} {self.value}>"


# We can't subclass RealmCount because we only have a realm_id here, not a foreign key.
class RemoteRealmCount(BaseCount):
    server: RemoteZulipServer = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    realm_id: int = models.IntegerField(db_index=True)
    # The remote_id field lets us deduplicate data from the remote server
    remote_id: int = models.IntegerField(db_index=True)

    class Meta:
        unique_together = ("server", "realm_id", "property", "subgroup", "end_time")
        index_together = [
            ["property", "end_time"],
            ["server", "remote_id"],
        ]

    def __str__(self) -> str:
        return f"{self.server} {self.realm_id} {self.property} {self.subgroup} {self.value}"


class RateLimitedRemoteZulipServer(RateLimitedObject):
    def __init__(
        self, remote_server: RemoteZulipServer, domain: str = "api_by_remote_server"
    ) -> None:
        # Remote servers can only make API requests regarding push notifications
        # which requires ZILENCED_ENABLED and of course can't happen on API endpoints
        # inside Tornado.
        assert not settings.RUNNING_INSIDE_TORNADO
        assert settings.ZILENCER_ENABLED

        self.uuid = remote_server.uuid
        self.domain = domain
        super().__init__()

    def key(self) -> str:
        return f"{type(self).__name__}:<{self.uuid}>:{self.domain}"

    def rules(self) -> List[Tuple[int, int]]:
        return rate_limiter_rules[self.domain]

import datetime

from django.db import models

from analytics.models import BaseCount
from zerver.models import AbstractPushDeviceToken, AbstractRealmAuditLog


def get_remote_server_by_uuid(uuid: str) -> 'RemoteZulipServer':
    return RemoteZulipServer.objects.get(uuid=uuid)

class RemoteZulipServer(models.Model):
    UUID_LENGTH = 36
    API_KEY_LENGTH = 64
    HOSTNAME_MAX_LENGTH = 128

    uuid: str = models.CharField(max_length=UUID_LENGTH, unique=True)
    api_key: str = models.CharField(max_length=API_KEY_LENGTH)

    hostname: str = models.CharField(max_length=HOSTNAME_MAX_LENGTH)
    contact_email: str = models.EmailField(blank=True, null=False)
    last_updated: datetime.datetime = models.DateTimeField('last updated', auto_now=True)

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

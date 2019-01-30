import datetime

from django.db import models

from zerver.models import AbstractPushDeviceToken
from analytics.models import BaseCount

def get_remote_server_by_uuid(uuid: str) -> 'RemoteZulipServer':
    return RemoteZulipServer.objects.get(uuid=uuid)

class RemoteZulipServer(models.Model):
    UUID_LENGTH = 36
    API_KEY_LENGTH = 64
    HOSTNAME_MAX_LENGTH = 128

    uuid = models.CharField(max_length=UUID_LENGTH, unique=True)  # type: str
    api_key = models.CharField(max_length=API_KEY_LENGTH)  # type: str

    hostname = models.CharField(max_length=HOSTNAME_MAX_LENGTH)  # type: str
    contact_email = models.EmailField(blank=True, null=False)  # type: str
    last_updated = models.DateTimeField('last updated', auto_now=True)  # type: datetime.datetime

    def __str__(self) -> str:
        return "<RemoteZulipServer %s %s>" % (self.hostname, self.uuid[0:12])

# Variant of PushDeviceToken for a remote server.
class RemotePushDeviceToken(AbstractPushDeviceToken):
    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)  # type: RemoteZulipServer
    # The user id on the remote server for this device device this is
    user_id = models.BigIntegerField(db_index=True)  # type: int

    class Meta:
        unique_together = ("server", "user_id", "kind", "token")

    def __str__(self) -> str:
        return "<RemotePushDeviceToken %s %s>" % (self.server, self.user_id)

class RemoteInstallationCount(BaseCount):
    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)  # type: RemoteZulipServer
    # The remote_id field lets us deduplicate data from the remote server
    remote_id = models.IntegerField(db_index=True)  # type: int

    class Meta:
        unique_together = ("server", "property", "subgroup", "end_time")

    def __str__(self) -> str:
        return "<InstallationCount: %s %s %s>" % (self.property, self.subgroup, self.value)

# We can't subclass RealmCount because we only have a realm_id here, not a foreign key.
class RemoteRealmCount(BaseCount):
    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)  # type: RemoteZulipServer
    realm_id = models.IntegerField(db_index=True)  # type: int
    # The remote_id field lets us deduplicate data from the remote server
    remote_id = models.IntegerField(db_index=True)  # type: int

    class Meta:
        unique_together = ("server", "realm_id", "property", "subgroup", "end_time")
        index_together = ["property", "end_time"]

    def __str__(self) -> str:
        return "%s %s %s %s %s" % (self.server, self.realm_id, self.property, self.subgroup, self.value)

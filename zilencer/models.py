import datetime

from django.db import models

from zerver.models import AbstractPushDeviceToken, Realm, UserProfile

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
    token = models.CharField(max_length=4096, db_index=True)  # type: bytes

    class Meta:
        unique_together = ("server", "token")

    def __str__(self) -> str:
        return "<RemotePushDeviceToken %s %s>" % (self.server, self.user_id)

class Customer(models.Model):
    realm = models.OneToOneField(Realm, on_delete=models.CASCADE)  # type: Realm
    stripe_customer_id = models.CharField(max_length=255, unique=True)  # type: str
    billing_user = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)

    def __str__(self) -> str:
        return "<Customer %s %s>" % (self.realm, self.stripe_customer_id)

class Plan(models.Model):
    # The two possible values for nickname
    CLOUD_MONTHLY = 'monthly'
    CLOUD_ANNUAL = 'annual'
    nickname = models.CharField(max_length=40, unique=True)  # type: str

    stripe_plan_id = models.CharField(max_length=255, unique=True)  # type: str

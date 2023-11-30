# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

from typing import List, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from typing_extensions import override

from analytics.models import BaseCount
from zerver.lib.rate_limiter import RateLimitedObject
from zerver.lib.rate_limiter import rules as rate_limiter_rules
from zerver.models import AbstractPushDeviceToken, AbstractRealmAuditLog, Realm


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
    VERSION_MAX_LENGTH = 128

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
    last_version = models.CharField(max_length=VERSION_MAX_LENGTH, null=True)

    # Whether the server registration has been deactivated.
    deactivated = models.BooleanField(default=False)

    # Plan types for self-hosted customers
    PLAN_TYPE_SELF_HOSTED = 1
    PLAN_TYPE_COMMUNITY = 100
    PLAN_TYPE_BUSINESS = 101
    PLAN_TYPE_ENTERPRISE = 102

    # The current billing plan for the remote server, similar to Realm.plan_type.
    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_HOSTED)

    # This is not synced with the remote server, but only filled for sponsorship requests.
    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )

    @override
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

    @override
    def __str__(self) -> str:
        return f"{self.server!r} {self.user_id}"


class RemoteRealm(models.Model):
    """
    Each object corresponds to a single remote Realm that is using the
    Mobile Push Notifications Service via `manage.py register_server`.
    """

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)

    # The unique UUID and secret for this realm.
    uuid = models.UUIDField(unique=True)
    uuid_owner_secret = models.TextField()

    # Value obtained's from the remote server's realm.host.
    host = models.TextField()

    name = models.TextField(default="")

    authentication_methods = models.JSONField(default=dict)

    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )

    # The fields below are analogical to RemoteZulipServer fields.

    last_updated = models.DateTimeField("last updated", auto_now=True)

    # Whether the realm registration has been deactivated.
    registration_deactivated = models.BooleanField(default=False)
    # Whether the realm has been deactivated on the remote server.
    realm_deactivated = models.BooleanField(default=False)

    # When the realm was created on the remote server.
    realm_date_created = models.DateTimeField()

    # Plan types for self-hosted customers
    PLAN_TYPE_SELF_HOSTED = 1
    PLAN_TYPE_COMMUNITY = 100
    PLAN_TYPE_BUSINESS = 101
    PLAN_TYPE_ENTERPRISE = 102

    # The current billing plan for the remote server, similar to Realm.plan_type.
    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_HOSTED, db_index=True)

    @override
    def __str__(self) -> str:
        return f"{self.host} {str(self.uuid)[0:12]}"


class RemoteZulipServerAuditLog(AbstractRealmAuditLog):
    """Audit data associated with a remote Zulip server (not specific to a
    realm).  Used primarily for tracking registration and billing
    changes for self-hosted customers.

    In contrast with RemoteRealmAuditLog, which has a copy of data
    that is generated on the client Zulip server, this table is the
    authoritative storage location for the server's history.
    """

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)

    @override
    def __str__(self) -> str:
        return f"{self.server!r} {self.event_type} {self.event_time} {self.id}"


class RemoteRealmAuditLog(AbstractRealmAuditLog):
    """Synced audit data from a remote Zulip server, used primarily for
    billing.  See RealmAuditLog and AbstractRealmAuditLog for details.
    """

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)

    # With modern Zulip servers, we can link to the RemoteRealm object.
    remote_realm = models.ForeignKey(RemoteRealm, on_delete=models.CASCADE, null=True)
    # For pre-8.0 servers, we might only have the realm ID and thus no
    # RemoteRealm object yet. We will eventually be able to drop this
    # column once all self-hosted servers have upgraded in favor of
    # just using the foreign key everywhere.
    realm_id = models.IntegerField(null=True, blank=True)
    # The remote_id field lets us deduplicate data from the remote server
    remote_id = models.IntegerField(null=True)

    @override
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


class BaseRemoteCount(BaseCount):
    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    # The remote_id field is the id value of the corresponding *Count object
    # on the remote server.
    # It lets us deduplicate data from the remote server.
    # Note: Some counts don't come from the remote server, but rather
    # are stats we track on the bouncer server itself, pertaining to the remote server.
    # E.g. mobile_pushes_received::day. Such counts will set this field to None.
    remote_id = models.IntegerField(null=True)

    class Meta:
        abstract = True


class RemoteInstallationCount(BaseRemoteCount):
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["server", "property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name="unique_remote_installation_count",
            ),
            UniqueConstraint(
                fields=["server", "property", "end_time"],
                condition=Q(subgroup__isnull=True),
                name="unique_remote_installation_count_null_subgroup",
            ),
            UniqueConstraint(
                fields=["server", "remote_id"],
                # As noted above, remote_id may be null, so we only
                # enforce uniqueness if it isn't.  This is not
                # technically necessary, since null != null, but it
                # makes the property more explicit.
                condition=Q(remote_id__isnull=False),
                name="unique_remote_installation_count_server_id_remote_id",
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.property} {self.subgroup} {self.value}"


# We can't subclass RealmCount because we only have a realm_id here, not a foreign key.
class RemoteRealmCount(BaseRemoteCount):
    realm_id = models.IntegerField(null=True)
    # Certain RemoteRealmCount will be counts tracked on the bouncer server directly, about
    # stats pertaining to a realm on a remote server. For such objects, we will link to
    # the corresponding RemoteRealm object that the remote server registered with us.
    # In the future we may be able to link all RemoteRealmCount objects to a RemoteRealm,
    # including the RemoteRealmCount objects are results of just syncing the RealmCount
    # table from the remote server.
    remote_realm = models.ForeignKey(RemoteRealm, on_delete=models.CASCADE, null=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["server", "realm_id", "property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name="unique_remote_realm_installation_count",
            ),
            UniqueConstraint(
                fields=["server", "realm_id", "property", "end_time"],
                condition=Q(subgroup__isnull=True),
                name="unique_remote_realm_installation_count_null_subgroup",
            ),
            UniqueConstraint(
                fields=["server", "remote_id"],
                # As with RemoteInstallationCount above, remote_id may
                # be null; since null != null, this condition is not
                # strictly necessary, but serves to make the property
                # more explicit.
                condition=Q(remote_id__isnull=False),
                name="unique_remote_realm_installation_count_server_id_remote_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["property", "end_time"],
                name="zilencer_remoterealmcount_property_end_time_506a0b38_idx",
            ),
        ]

    @override
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

    @override
    def key(self) -> str:
        return f"{type(self).__name__}:<{self.uuid}>:{self.domain}"

    @override
    def rules(self) -> List[Tuple[int, int]]:
        return rate_limiter_rules[self.domain]

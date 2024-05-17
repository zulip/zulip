# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max, Q, QuerySet, UniqueConstraint
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from analytics.models import BaseCount
from zerver.lib.rate_limiter import RateLimitedObject
from zerver.lib.rate_limiter import rules as rate_limiter_rules
from zerver.models import AbstractPushDeviceToken, AbstractRealmAuditLog, Realm, UserProfile


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
    last_request_datetime = models.DateTimeField(null=True)
    last_version = models.CharField(max_length=VERSION_MAX_LENGTH, null=True)
    last_api_feature_level = models.PositiveIntegerField(null=True)

    # Whether the server registration has been deactivated.
    deactivated = models.BooleanField(default=False)

    # Plan types for self-hosted customers
    #
    # We reserve PLAN_TYPE_SELF_HOSTED=Realm.PLAN_TYPE_SELF_HOSTED for
    # self-hosted installations that aren't using the notifications
    # service.
    #
    # The other values align with, e.g., CustomerPlan.TIER_SELF_HOSTED_BASE
    PLAN_TYPE_SELF_HOSTED = 1
    PLAN_TYPE_SELF_MANAGED = 100
    PLAN_TYPE_SELF_MANAGED_LEGACY = 101
    PLAN_TYPE_COMMUNITY = 102
    PLAN_TYPE_BASIC = 103
    PLAN_TYPE_BUSINESS = 104
    PLAN_TYPE_ENTERPRISE = 105

    # The current billing plan for the remote server, similar to Realm.plan_type.
    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_MANAGED)

    # This is not synced with the remote server, but only filled for sponsorship requests.
    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )

    # The last time 'RemoteRealmAuditlog' was updated for this server.
    last_audit_log_update = models.DateTimeField(null=True)

    @override
    def __str__(self) -> str:
        return f"{self.hostname} {str(self.uuid)[0:12]}"

    def format_requester_for_logs(self) -> str:
        return "zulip-server:" + str(self.uuid)

    def get_remote_server_billing_users(self) -> QuerySet["RemoteServerBillingUser"]:
        return RemoteServerBillingUser.objects.filter(
            remote_server=self,
            is_active=True,
        )


class RemotePushDeviceToken(AbstractPushDeviceToken):
    """Like PushDeviceToken, but for a device connected to a remote server."""

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)
    # The user id on the remote server for this device
    user_id = models.BigIntegerField(null=True)
    user_uuid = models.UUIDField(null=True)

    remote_realm = models.ForeignKey("RemoteRealm", on_delete=models.SET_NULL, null=True)

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

    is_system_bot_realm = models.BooleanField(default=False)

    authentication_methods = models.JSONField(default=dict)

    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )

    # The fields below are analogical to RemoteZulipServer fields.

    last_updated = models.DateTimeField("last updated", auto_now=True)
    last_request_datetime = models.DateTimeField(null=True)

    # Whether the realm registration has been deactivated.
    registration_deactivated = models.BooleanField(default=False)
    # Whether the realm has been deactivated on the remote server.
    realm_deactivated = models.BooleanField(default=False)
    # Whether we believe the remote server deleted this realm
    # from the database.
    realm_locally_deleted = models.BooleanField(default=False)

    # When the realm was created on the remote server.
    realm_date_created = models.DateTimeField()

    # Plan types for self-hosted customers
    #
    # We reserve PLAN_TYPE_SELF_HOSTED=Realm.PLAN_TYPE_SELF_HOSTED for
    # self-hosted installations that aren't using the notifications
    # service.
    #
    # The other values align with, e.g., CustomerPlan.TIER_SELF_HOSTED_BASE
    PLAN_TYPE_SELF_HOSTED = 1
    PLAN_TYPE_SELF_MANAGED = 100
    PLAN_TYPE_SELF_MANAGED_LEGACY = 101
    PLAN_TYPE_COMMUNITY = 102
    PLAN_TYPE_BASIC = 103
    PLAN_TYPE_BUSINESS = 104
    PLAN_TYPE_ENTERPRISE = 105
    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_MANAGED, db_index=True)

    @override
    def __str__(self) -> str:
        return f"{self.host} {str(self.uuid)[0:12]}"

    def get_remote_realm_billing_users(self) -> QuerySet["RemoteRealmBillingUser"]:
        return RemoteRealmBillingUser.objects.filter(
            remote_realm=self,
            is_active=True,
        )


class AbstractRemoteRealmBillingUser(models.Model):
    remote_realm = models.ForeignKey(RemoteRealm, on_delete=models.CASCADE)

    # The .uuid of the UserProfile on the remote server
    user_uuid = models.UUIDField()
    email = models.EmailField()

    date_joined = models.DateTimeField(default=timezone_now)

    class Meta:
        abstract = True


class RemoteRealmBillingUser(AbstractRemoteRealmBillingUser):
    full_name = models.TextField(default="")

    last_login = models.DateTimeField(null=True)

    is_active = models.BooleanField(default=True)

    TOS_VERSION_BEFORE_FIRST_LOGIN = UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN
    tos_version = models.TextField(default=TOS_VERSION_BEFORE_FIRST_LOGIN)

    enable_major_release_emails = models.BooleanField(default=True)
    enable_maintenance_release_emails = models.BooleanField(default=True)

    class Meta:
        unique_together = [
            ("remote_realm", "user_uuid"),
        ]


class PreregistrationRemoteRealmBillingUser(AbstractRemoteRealmBillingUser):
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    # These are for carrying certain information that's originally
    # in an IdentityDict across the confirmation link flow. These
    # values will be restored in the final, fully authenticated IdentityDict.
    next_page = models.TextField(null=True)
    uri_scheme = models.TextField()

    created_user = models.ForeignKey(RemoteRealmBillingUser, null=True, on_delete=models.SET_NULL)


class AbstractRemoteServerBillingUser(models.Model):
    remote_server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)

    email = models.EmailField()

    date_joined = models.DateTimeField(default=timezone_now)

    class Meta:
        abstract = True


class RemoteServerBillingUser(AbstractRemoteServerBillingUser):
    full_name = models.TextField(default="")

    last_login = models.DateTimeField(null=True)

    is_active = models.BooleanField(default=True)

    TOS_VERSION_BEFORE_FIRST_LOGIN = UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN
    tos_version = models.TextField(default=TOS_VERSION_BEFORE_FIRST_LOGIN)

    enable_major_release_emails = models.BooleanField(default=True)
    enable_maintenance_release_emails = models.BooleanField(default=True)

    class Meta:
        unique_together = [
            ("remote_server", "email"),
        ]


class PreregistrationRemoteServerBillingUser(AbstractRemoteServerBillingUser):
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    next_page = models.TextField(null=True)

    created_user = models.ForeignKey(RemoteServerBillingUser, null=True, on_delete=models.SET_NULL)


class RemoteZulipServerAuditLog(AbstractRealmAuditLog):
    """Audit data associated with a remote Zulip server (not specific to a
    realm).  Used primarily for tracking registration and billing
    changes for self-hosted customers.

    In contrast with RemoteRealmAuditLog, which has a copy of data
    that is generated on the client Zulip server, this table is the
    authoritative storage location for the server's history.
    """

    server = models.ForeignKey(RemoteZulipServer, on_delete=models.CASCADE)

    acting_remote_user = models.ForeignKey(
        RemoteServerBillingUser, null=True, on_delete=models.SET_NULL
    )
    acting_support_user = models.ForeignKey(UserProfile, null=True, on_delete=models.SET_NULL)

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

    acting_remote_user = models.ForeignKey(
        RemoteRealmBillingUser, null=True, on_delete=models.SET_NULL
    )
    acting_support_user = models.ForeignKey(UserProfile, null=True, on_delete=models.SET_NULL)

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
            models.Index(
                fields=["server", "realm_id"],
                condition=Q(remote_realm__isnull=True),
                name="zilencer_remoterealmauditlog_server_realm",
            ),
            models.Index(
                fields=["server"],
                condition=Q(remote_realm__isnull=True),
                name="zilencer_remoterealmauditlog_server",
            ),
            models.Index(
                fields=["remote_realm_id", "id"],
                condition=Q(event_type__in=AbstractRealmAuditLog.SYNCED_BILLING_EVENTS),
                name="zilencer_remoterealmauditlog_synced_billing_events",
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
        indexes = [
            models.Index(
                fields=["server_id", "end_time"],
                condition=Q(property="mobile_pushes_forwarded::day"),
                name="zilencer_remoteinstallationcount_server_end_time_mobile_pushes_forwarded",
            )
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
            # These two constraints come from the information as
            # provided by the remote server, for rows they provide.
            UniqueConstraint(
                fields=["server", "realm_id", "property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name="unique_server_realm_installation_count",
            ),
            UniqueConstraint(
                fields=["server", "realm_id", "property", "end_time"],
                condition=Q(subgroup__isnull=True),
                name="unique_server_realm_installation_count_null_subgroup",
            ),
            # These two constraints come from our internal
            # record-keeping, which has a RemoteRealm object.
            UniqueConstraint(
                fields=["remote_realm_id", "property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name="unique_remote_realm_installation_count",
            ),
            UniqueConstraint(
                fields=["remote_realm_id", "property", "end_time"],
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
            models.Index(
                fields=["server", "realm_id"],
                condition=Q(remote_realm__isnull=True),
                name="zilencer_remoterealmcount_server_realm",
            ),
            models.Index(
                fields=["server"],
                condition=Q(remote_realm__isnull=True),
                name="zilencer_remoterealmcount_server",
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


@dataclass
class RemoteCustomerUserCount:
    guest_user_count: int
    non_guest_user_count: int


def get_remote_customer_user_count(
    audit_logs: List[RemoteRealmAuditLog],
) -> RemoteCustomerUserCount:
    guest_count = 0
    non_guest_count = 0
    for log in audit_logs:
        humans_count_dict = log.extra_data[RemoteRealmAuditLog.ROLE_COUNT][
            RemoteRealmAuditLog.ROLE_COUNT_HUMANS
        ]
        for role_type in UserProfile.ROLE_TYPES:
            if role_type == UserProfile.ROLE_GUEST:
                guest_count += humans_count_dict.get(str(role_type), 0)
            else:
                non_guest_count += humans_count_dict.get(str(role_type), 0)

    return RemoteCustomerUserCount(
        non_guest_user_count=non_guest_count, guest_user_count=guest_count
    )


def get_remote_server_guest_and_non_guest_count(
    server_id: int, event_time: datetime = timezone_now()
) -> RemoteCustomerUserCount:
    # For each realm hosted on the server, find the latest audit log
    # entry indicating the number of active users in that realm.
    realm_last_audit_log_ids = (
        RemoteRealmAuditLog.objects.filter(
            server_id=server_id,
            event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            event_time__lte=event_time,
        )
        # Important: extra_data is empty for some pre-2020 audit logs
        # prior to the introduction of realm_user_count_by_role
        # logging. Meanwhile, modern Zulip servers using
        # bulk_create_users to create the users in the system bot
        # realm also generate such audit logs. Such audit logs should
        # never be the latest in a normal realm.
        .exclude(extra_data={})
        .values("realm_id")
        .annotate(max_id=Max("id"))
        .values_list("max_id", flat=True)
    )

    realm_audit_logs = RemoteRealmAuditLog.objects.filter(id__in=list(realm_last_audit_log_ids))

    # Now we add up the user counts from the different realms.
    user_count = get_remote_customer_user_count(list(realm_audit_logs))
    return user_count


def get_remote_realm_guest_and_non_guest_count(
    remote_realm: RemoteRealm, event_time: datetime = timezone_now()
) -> RemoteCustomerUserCount:
    latest_audit_log = (
        RemoteRealmAuditLog.objects.filter(
            remote_realm=remote_realm,
            event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            event_time__lte=event_time,
        )
        # Important: extra_data is empty for some pre-2020 audit logs
        # prior to the introduction of realm_user_count_by_role
        # logging. Meanwhile, modern Zulip servers using
        # bulk_create_users to create the users in the system bot
        # realm also generate such audit logs. Such audit logs should
        # never be the latest in a normal realm.
        .exclude(extra_data={})
        .last()
    )

    if latest_audit_log is not None:
        assert latest_audit_log is not None
        user_count = get_remote_customer_user_count([latest_audit_log])
    else:
        user_count = RemoteCustomerUserCount(guest_user_count=0, non_guest_user_count=0)
    return user_count


def has_stale_audit_log(server: RemoteZulipServer) -> bool:
    if server.last_audit_log_update is None:
        return True

    if timezone_now() - server.last_audit_log_update > timedelta(days=2):
        return True

    return False

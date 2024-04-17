# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import CASCADE, Q
from typing_extensions import override

from zerver.models.groups import NamedUserGroup
from zerver.models.realms import Realm
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


class AbstractRealmAuditLog(models.Model):
    """Defines fields common to RealmAuditLog and RemoteRealmAuditLog."""

    event_time = models.DateTimeField(db_index=True)
    # If True, event_time is an overestimate of the true time. Can be used
    # by migrations when introducing a new event_type.
    backfilled = models.BooleanField(default=False)

    # Keys within extra_data, when extra_data is a json dict. Keys are strings because
    # json keys must always be strings.
    OLD_VALUE = "1"
    NEW_VALUE = "2"
    ROLE_COUNT = "10"
    ROLE_COUNT_HUMANS = "11"
    ROLE_COUNT_BOTS = "12"

    extra_data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    # Event types
    USER_CREATED = 101
    USER_ACTIVATED = 102
    USER_DEACTIVATED = 103
    USER_REACTIVATED = 104
    USER_ROLE_CHANGED = 105
    USER_DELETED = 106
    USER_DELETED_PRESERVING_MESSAGES = 107

    USER_SOFT_ACTIVATED = 120
    USER_SOFT_DEACTIVATED = 121
    USER_PASSWORD_CHANGED = 122
    USER_AVATAR_SOURCE_CHANGED = 123
    USER_FULL_NAME_CHANGED = 124
    USER_EMAIL_CHANGED = 125
    USER_TERMS_OF_SERVICE_VERSION_CHANGED = 126
    USER_API_KEY_CHANGED = 127
    USER_BOT_OWNER_CHANGED = 128
    USER_DEFAULT_SENDING_STREAM_CHANGED = 129
    USER_DEFAULT_REGISTER_STREAM_CHANGED = 130
    USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED = 131
    USER_SETTING_CHANGED = 132
    USER_DIGEST_EMAIL_CREATED = 133

    REALM_DEACTIVATED = 201
    REALM_REACTIVATED = 202
    REALM_SCRUBBED = 203
    REALM_PLAN_TYPE_CHANGED = 204
    REALM_LOGO_CHANGED = 205
    REALM_EXPORTED = 206
    REALM_PROPERTY_CHANGED = 207
    REALM_ICON_SOURCE_CHANGED = 208
    REALM_DISCOUNT_CHANGED = 209
    REALM_SPONSORSHIP_APPROVED = 210
    REALM_BILLING_MODALITY_CHANGED = 211
    REALM_REACTIVATION_EMAIL_SENT = 212
    REALM_SPONSORSHIP_PENDING_STATUS_CHANGED = 213
    REALM_SUBDOMAIN_CHANGED = 214
    REALM_CREATED = 215
    REALM_DEFAULT_USER_SETTINGS_CHANGED = 216
    REALM_ORG_TYPE_CHANGED = 217
    REALM_DOMAIN_ADDED = 218
    REALM_DOMAIN_CHANGED = 219
    REALM_DOMAIN_REMOVED = 220
    REALM_PLAYGROUND_ADDED = 221
    REALM_PLAYGROUND_REMOVED = 222
    REALM_LINKIFIER_ADDED = 223
    REALM_LINKIFIER_CHANGED = 224
    REALM_LINKIFIER_REMOVED = 225
    REALM_EMOJI_ADDED = 226
    REALM_EMOJI_REMOVED = 227
    REALM_LINKIFIERS_REORDERED = 228
    REALM_IMPORTED = 229

    SUBSCRIPTION_CREATED = 301
    SUBSCRIPTION_ACTIVATED = 302
    SUBSCRIPTION_DEACTIVATED = 303
    SUBSCRIPTION_PROPERTY_CHANGED = 304

    USER_MUTED = 350
    USER_UNMUTED = 351

    STRIPE_CUSTOMER_CREATED = 401
    STRIPE_CARD_CHANGED = 402
    STRIPE_PLAN_CHANGED = 403
    STRIPE_PLAN_QUANTITY_RESET = 404

    CUSTOMER_CREATED = 501
    CUSTOMER_PLAN_CREATED = 502
    CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN = 503
    CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN = 504
    CUSTOMER_PROPERTY_CHANGED = 505
    CUSTOMER_PLAN_PROPERTY_CHANGED = 506

    STREAM_CREATED = 601
    STREAM_DEACTIVATED = 602
    STREAM_NAME_CHANGED = 603
    STREAM_REACTIVATED = 604
    STREAM_MESSAGE_RETENTION_DAYS_CHANGED = 605
    STREAM_PROPERTY_CHANGED = 607
    STREAM_GROUP_BASED_SETTING_CHANGED = 608

    USER_GROUP_CREATED = 701
    USER_GROUP_DELETED = 702
    USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED = 703
    USER_GROUP_DIRECT_USER_MEMBERSHIP_REMOVED = 704
    USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED = 705
    USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_REMOVED = 706
    USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED = 707
    USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_REMOVED = 708
    # 709 to 719 reserved for membership changes
    USER_GROUP_NAME_CHANGED = 720
    USER_GROUP_DESCRIPTION_CHANGED = 721
    USER_GROUP_GROUP_BASED_SETTING_CHANGED = 722

    # The following values are only for RemoteZulipServerAuditLog
    # Values should be exactly 10000 greater than the corresponding
    # value used for the same purpose in RealmAuditLog (e.g.
    # REALM_DEACTIVATED = 201, and REMOTE_SERVER_DEACTIVATED = 10201).
    REMOTE_SERVER_DEACTIVATED = 10201
    REMOTE_SERVER_REACTIVATED = 10202
    REMOTE_SERVER_PLAN_TYPE_CHANGED = 10204
    REMOTE_SERVER_DISCOUNT_CHANGED = 10209
    REMOTE_SERVER_SPONSORSHIP_APPROVED = 10210
    REMOTE_SERVER_BILLING_MODALITY_CHANGED = 10211
    REMOTE_SERVER_SPONSORSHIP_PENDING_STATUS_CHANGED = 10213
    REMOTE_SERVER_CREATED = 10215

    # This value is for RemoteRealmAuditLog entries tracking changes to the
    # RemoteRealm model resulting from modified realm information sent to us
    # via send_server_data_to_push_bouncer.
    REMOTE_REALM_VALUE_UPDATED = 20001
    REMOTE_PLAN_TRANSFERRED_SERVER_TO_REALM = 20002
    REMOTE_REALM_LOCALLY_DELETED = 20003
    REMOTE_REALM_LOCALLY_DELETED_RESTORED = 20004

    event_type = models.PositiveSmallIntegerField()

    # event_types synced from on-prem installations to Zulip Cloud when
    # billing for mobile push notifications is enabled.  Every billing
    # event_type should have ROLE_COUNT populated in extra_data.
    SYNCED_BILLING_EVENTS = [
        USER_CREATED,
        USER_ACTIVATED,
        USER_DEACTIVATED,
        USER_REACTIVATED,
        USER_ROLE_CHANGED,
        REALM_DEACTIVATED,
        REALM_REACTIVATED,
        REALM_IMPORTED,
    ]

    HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS = {
        "existing_user": "At an organization that's using it",
        "search_engine": "Search engine",
        "review_site": "Review site",
        "personal_recommendation": "Personal recommendation",
        "hacker_news": "Hacker News",
        "ad": "Advertisement",
        "other": "Other",
        "forgot": "Don't remember",
        "refuse_to_answer": "Prefer not to say",
    }

    class Meta:
        abstract = True


class RealmAuditLog(AbstractRealmAuditLog):
    """
    RealmAuditLog tracks important changes to users, streams, and
    realms in Zulip.  It is intended to support both
    debugging/introspection (e.g. determining when a user's left a
    given stream?) as well as help with some database migrations where
    we might be able to do a better data backfill with it.  Here are a
    few key details about how this works:

    * acting_user is the user who initiated the state change
    * modified_user (if present) is the user being modified
    * modified_stream (if present) is the stream being modified
    * modified_user_group (if present) is the user group being modified

    For example:
    * When a user subscribes another user to a stream, modified_user,
      acting_user, and modified_stream will all be present and different.
    * When an administrator changes an organization's realm icon,
      acting_user is that administrator and modified_user,
      modified_stream and modified_user_group will be None.
    """

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    acting_user = models.ForeignKey(
        UserProfile,
        null=True,
        related_name="+",
        on_delete=CASCADE,
    )
    modified_user = models.ForeignKey(
        UserProfile,
        null=True,
        related_name="+",
        on_delete=CASCADE,
    )
    modified_stream = models.ForeignKey(
        Stream,
        null=True,
        on_delete=CASCADE,
    )
    modified_user_group = models.ForeignKey(
        NamedUserGroup,
        null=True,
        on_delete=CASCADE,
    )
    event_last_message_id = models.IntegerField(null=True)

    class Meta:
        indexes = [
            models.Index(
                name="zerver_realmauditlog_realm__event_type__event_time",
                fields=["realm", "event_type", "event_time"],
            ),
            models.Index(
                name="zerver_realmauditlog_user_subscriptions_idx",
                fields=["modified_user", "modified_stream"],
                condition=Q(
                    event_type__in=[
                        AbstractRealmAuditLog.SUBSCRIPTION_CREATED,
                        AbstractRealmAuditLog.SUBSCRIPTION_ACTIVATED,
                        AbstractRealmAuditLog.SUBSCRIPTION_DEACTIVATED,
                    ]
                ),
            ),
        ]

    @override
    def __str__(self) -> str:
        if self.modified_user is not None:
            return f"{self.modified_user!r} {self.event_type} {self.event_time} {self.id}"
        if self.modified_stream is not None:
            return f"{self.modified_stream!r} {self.event_type} {self.event_time} {self.id}"
        if self.modified_user_group is not None:
            return f"{self.modified_user_group!r} {self.event_type} {self.event_time} {self.id}"
        return f"{self.realm!r} {self.event_type} {self.event_time} {self.id}"

# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypedDict, TypeVar, Union

import orjson
from bitfield import BitField
from bitfield.types import Bit, BitHandler
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import CASCADE, Exists, F, OuterRef, Q, QuerySet
from django.db.models.functions import Lower, Upper
from django.db.models.signals import post_delete, post_save
from django.db.models.sql.compiler import SQLCompiler
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise, ValuesQuerySet
from typing_extensions import override

from confirmation import settings as confirmation_settings
from zerver.lib import cache
from zerver.lib.cache import (
    cache_delete,
    cache_with_key,
    flush_message,
    flush_muting_users_cache,
    flush_stream,
    flush_submessage,
    flush_used_upload_space_cache,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.lib.display_recipient import get_display_recipient, get_recipient_ids
from zerver.lib.exceptions import RateLimitedError
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import (
    DefaultStreamDict,
    ExtendedFieldElement,
    ExtendedValidator,
    FieldElement,
    GroupPermissionSetting,
    ProfileDataElementBase,
    ProfileDataElementValue,
    RealmUserValidator,
    UnspecifiedValue,
    UserFieldElement,
    Validator,
)
from zerver.lib.validator import (
    check_date,
    check_int,
    check_list,
    check_long_string,
    check_short_string,
    check_url,
    validate_select_field,
)
from zerver.models.constants import MAX_LANGUAGE_ID_LENGTH, MAX_TOPIC_NAME_LENGTH
from zerver.models.groups import GroupGroupMembership as GroupGroupMembership
from zerver.models.groups import SystemGroups
from zerver.models.groups import UserGroup as UserGroup
from zerver.models.groups import UserGroupMembership as UserGroupMembership
from zerver.models.linkifiers import RealmFilter as RealmFilter
from zerver.models.realm_emoji import RealmEmoji as RealmEmoji
from zerver.models.realm_playgrounds import RealmPlayground as RealmPlayground
from zerver.models.realms import Realm as Realm
from zerver.models.realms import RealmAuthenticationMethod as RealmAuthenticationMethod
from zerver.models.realms import RealmDomain as RealmDomain
from zerver.models.users import RealmUserDefault as RealmUserDefault
from zerver.models.users import UserBaseSettings as UserBaseSettings
from zerver.models.users import UserProfile as UserProfile
from zerver.models.users import get_user_profile_by_id_in_realm


@models.Field.register_lookup
class AndZero(models.Lookup[int]):
    lookup_name = "andz"

    @override
    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> Tuple[str, List[Union[str, int]]]:  # nocoverage # currently only used in migrations
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} & {rhs} = 0", lhs_params + rhs_params


@models.Field.register_lookup
class AndNonZero(models.Lookup[int]):
    lookup_name = "andnz"

    @override
    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> Tuple[str, List[Union[str, int]]]:  # nocoverage # currently only used in migrations
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} & {rhs} != 0", lhs_params + rhs_params


ModelT = TypeVar("ModelT", bound=models.Model)
RowT = TypeVar("RowT")


def query_for_ids(
    query: ValuesQuerySet[ModelT, RowT],
    user_ids: List[int],
    field: str,
) -> ValuesQuerySet[ModelT, RowT]:
    """
    This function optimizes searches of the form
    `user_profile_id in (1, 2, 3, 4)` by quickly
    building the where clauses.  Profiling shows significant
    speedups over the normal Django-based approach.

    Use this very carefully!  Also, the caller should
    guard against empty lists of user_ids.
    """
    assert user_ids
    clause = f"{field} IN %s"
    query = query.extra(
        where=[clause],
        params=(tuple(user_ids),),
    )
    return query


class Recipient(models.Model):
    """Represents an audience that can potentially receive messages in Zulip.

    This table essentially functions as a generic foreign key that
    allows Message.recipient_id to be a simple ForeignKey representing
    the audience for a message, while supporting the different types
    of audiences Zulip supports for a message.

    Recipient has just two attributes: The enum type, and a type_id,
    which is the ID of the UserProfile/Stream/Huddle object containing
    all the metadata for the audience. There are 3 recipient types:

    1. 1:1 direct message: The type_id is the ID of the UserProfile
       who will receive any message to this Recipient. The sender
       of such a message is represented separately.
    2. Stream message: The type_id is the ID of the associated Stream.
    3. Group direct message: In Zulip, group direct messages are
       represented by Huddle objects, which encode the set of users
       in the conversation. The type_id is the ID of the associated Huddle
       object; the set of users is usually retrieved via the Subscription
       table. See the Huddle model for details.

    See also the Subscription model, which stores which UserProfile
    objects are subscribed to which Recipient objects.
    """

    type_id = models.IntegerField(db_index=True)
    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types are {personal, stream, huddle}

    # The type for 1:1 direct messages.
    PERSONAL = 1
    # The type for stream messages.
    STREAM = 2
    # The type group direct messages.
    HUDDLE = 3

    class Meta:
        unique_together = ("type", "type_id")

    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _type_names = {PERSONAL: "personal", STREAM: "stream", HUDDLE: "huddle"}

    @override
    def __str__(self) -> str:
        return f"{self.label()} ({self.type_id}, {self.type})"

    def label(self) -> str:
        if self.type == Recipient.STREAM:
            return Stream.objects.get(id=self.type_id).name
        else:
            return str(get_display_recipient(self))

    def type_name(self) -> str:
        # Raises KeyError if invalid
        return self._type_names[self.type]


class PreregistrationRealm(models.Model):
    """Data on a partially created realm entered by a user who has
    completed the "new organization" form. Used to transfer the user's
    selections from the pre-confirmation "new organization" form to
    the post-confirmation user registration form.

    Note that the values stored here may not match those of the
    created realm (in the event the user creates a realm at all),
    because we allow the user to edit these values in the registration
    form (and in fact the user will be required to do so if the
    `string_id` is claimed by another realm before registraiton is
    completed).
    """

    name = models.CharField(max_length=Realm.MAX_REALM_NAME_LENGTH)
    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )
    default_language = models.CharField(
        default="en",
        max_length=MAX_LANGUAGE_ID_LENGTH,
    )
    string_id = models.CharField(max_length=Realm.MAX_REALM_SUBDOMAIN_LENGTH)
    email = models.EmailField()

    confirmation = GenericRelation("confirmation.Confirmation", related_query_name="prereg_realm")
    status = models.IntegerField(default=0)

    # The Realm created upon completion of the registration
    # for this PregistrationRealm
    created_realm = models.ForeignKey(Realm, null=True, related_name="+", on_delete=models.SET_NULL)

    # The UserProfile created upon completion of the registration
    # for this PregistrationRealm
    created_user = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=models.SET_NULL
    )


class PreregistrationUser(models.Model):
    # Data on a partially created user, before the completion of
    # registration.  This is used in at least three major code paths:
    # * Realm creation, in which case realm is None.
    #
    # * Invitations, in which case referred_by will always be set.
    #
    # * Social authentication signup, where it's used to store data
    #   from the authentication step and pass it to the registration
    #   form.

    email = models.EmailField()

    confirmation = GenericRelation("confirmation.Confirmation", related_query_name="prereg_user")
    # If the pre-registration process provides a suggested full name for this user,
    # store it here to use it to prepopulate the full name field in the registration form:
    full_name = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH, null=True)
    full_name_validated = models.BooleanField(default=False)
    referred_by = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)
    streams = models.ManyToManyField("zerver.Stream")
    invited_at = models.DateTimeField(auto_now=True)
    realm_creation = models.BooleanField(default=False)
    # Indicates whether the user needs a password.  Users who were
    # created via SSO style auth (e.g. GitHub/Google) generally do not.
    password_required = models.BooleanField(default=True)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    # The realm should only ever be None for PreregistrationUser
    # objects created as part of realm creation.
    realm = models.ForeignKey(Realm, null=True, on_delete=CASCADE)

    # These values should be consistent with the values
    # in settings_config.user_role_values.
    INVITE_AS = dict(
        REALM_OWNER=100,
        REALM_ADMIN=200,
        MODERATOR=300,
        MEMBER=400,
        GUEST_USER=600,
    )
    invited_as = models.PositiveSmallIntegerField(default=INVITE_AS["MEMBER"])

    multiuse_invite = models.ForeignKey("MultiuseInvite", null=True, on_delete=models.SET_NULL)

    # The UserProfile created upon completion of the registration
    # for this PregistrationUser
    created_user = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=models.SET_NULL
    )

    class Meta:
        indexes = [
            models.Index(Upper("email"), name="upper_preregistration_email_idx"),
        ]


def filter_to_valid_prereg_users(
    query: QuerySet[PreregistrationUser],
    invite_expires_in_minutes: Union[Optional[int], UnspecifiedValue] = UnspecifiedValue(),
) -> QuerySet[PreregistrationUser]:
    """
    If invite_expires_in_days is specified, we return only those PreregistrationUser
    objects that were created at most that many days in the past.
    """
    used_value = confirmation_settings.STATUS_USED
    revoked_value = confirmation_settings.STATUS_REVOKED

    query = query.exclude(status__in=[used_value, revoked_value])
    if invite_expires_in_minutes is None:
        # Since invite_expires_in_minutes is None, we're invitation will never
        # expire, we do not need to check anything else and can simply return
        # after excluding objects with active and revoked status.
        return query

    assert invite_expires_in_minutes is not None
    if not isinstance(invite_expires_in_minutes, UnspecifiedValue):
        lowest_datetime = timezone_now() - timedelta(minutes=invite_expires_in_minutes)
        return query.filter(invited_at__gte=lowest_datetime)
    else:
        return query.filter(
            Q(confirmation__expiry_date=None) | Q(confirmation__expiry_date__gte=timezone_now())
        )


class MultiuseInvite(models.Model):
    referred_by = models.ForeignKey(UserProfile, on_delete=CASCADE)
    streams = models.ManyToManyField("zerver.Stream")
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    invited_as = models.PositiveSmallIntegerField(default=PreregistrationUser.INVITE_AS["MEMBER"])

    # status for tracking whether the invite has been revoked.
    # If revoked, set to confirmation.settings.STATUS_REVOKED.
    # STATUS_USED is not supported, because these objects are supposed
    # to be usable multiple times.
    status = models.IntegerField(default=0)


class EmailChangeStatus(models.Model):
    new_email = models.EmailField()
    old_email = models.EmailField()
    updated_at = models.DateTimeField(auto_now=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)


class RealmReactivationStatus(models.Model):
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)


class AbstractPushDeviceToken(models.Model):
    APNS = 1
    GCM = 2

    KINDS = (
        (APNS, "apns"),
        (GCM, "gcm"),
    )

    kind = models.PositiveSmallIntegerField(choices=KINDS)

    # The token is a unique device-specific token that is
    # sent to us from each device:
    #   - APNS token if kind == APNS
    #   - GCM registration id if kind == GCM
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


def generate_email_token_for_stream() -> str:
    return secrets.token_hex(16)


class Stream(models.Model):
    MAX_NAME_LENGTH = 60
    MAX_DESCRIPTION_LENGTH = 1024

    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    date_created = models.DateTimeField(default=timezone_now)
    deactivated = models.BooleanField(default=False)
    description = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, default="")
    rendered_description = models.TextField(default="")

    # Foreign key to the Recipient object for STREAM type messages to this stream.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

    # Various permission policy configurations
    PERMISSION_POLICIES: Dict[str, Dict[str, Any]] = {
        "web_public": {
            "invite_only": False,
            "history_public_to_subscribers": True,
            "is_web_public": True,
            "policy_name": gettext_lazy("Web-public"),
        },
        "public": {
            "invite_only": False,
            "history_public_to_subscribers": True,
            "is_web_public": False,
            "policy_name": gettext_lazy("Public"),
        },
        "private_shared_history": {
            "invite_only": True,
            "history_public_to_subscribers": True,
            "is_web_public": False,
            "policy_name": gettext_lazy("Private, shared history"),
        },
        "private_protected_history": {
            "invite_only": True,
            "history_public_to_subscribers": False,
            "is_web_public": False,
            "policy_name": gettext_lazy("Private, protected history"),
        },
        # Public streams with protected history are currently only
        # available in Zephyr realms
        "public_protected_history": {
            "invite_only": False,
            "history_public_to_subscribers": False,
            "is_web_public": False,
            "policy_name": gettext_lazy("Public, protected history"),
        },
    }
    invite_only = models.BooleanField(default=False)
    history_public_to_subscribers = models.BooleanField(default=True)

    # Whether this stream's content should be published by the web-public archive features
    is_web_public = models.BooleanField(default=False)

    STREAM_POST_POLICY_EVERYONE = 1
    STREAM_POST_POLICY_ADMINS = 2
    STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS = 3
    STREAM_POST_POLICY_MODERATORS = 4
    # TODO: Implement policy to restrict posting to a user group or admins.

    # Who in the organization has permission to send messages to this stream.
    stream_post_policy = models.PositiveSmallIntegerField(default=STREAM_POST_POLICY_EVERYONE)
    POST_POLICIES: Dict[int, StrPromise] = {
        # These strings should match the strings in the
        # stream_post_policy_values object in stream_data.js.
        STREAM_POST_POLICY_EVERYONE: gettext_lazy("All stream members can post"),
        STREAM_POST_POLICY_ADMINS: gettext_lazy("Only organization administrators can post"),
        STREAM_POST_POLICY_MODERATORS: gettext_lazy(
            "Only organization administrators and moderators can post"
        ),
        STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS: gettext_lazy(
            "Only organization full members can post"
        ),
    }
    STREAM_POST_POLICY_TYPES = list(POST_POLICIES.keys())

    # The unique thing about Zephyr public streams is that we never list their
    # users.  We may try to generalize this concept later, but for now
    # we just use a concrete field.  (Zephyr public streams aren't exactly like
    # invite-only streams--while both are private in terms of listing users,
    # for Zephyr we don't even list users to stream members, yet membership
    # is more public in the sense that you don't need a Zulip invite to join.
    # This field is populated directly from UserProfile.is_zephyr_mirror_realm,
    # and the reason for denormalizing field is performance.
    is_in_zephyr_realm = models.BooleanField(default=False)

    # Used by the e-mail forwarder. The e-mail RFC specifies a maximum
    # e-mail length of 254, and our max stream length is 30, so we
    # have plenty of room for the token.
    email_token = models.CharField(
        max_length=32,
        default=generate_email_token_for_stream,
        unique=True,
    )

    # For old messages being automatically deleted.
    # Value NULL means "use retention policy of the realm".
    # Value -1 means "disable retention policy for this stream unconditionally".
    # Non-negative values have the natural meaning of "archive messages older than <value> days".
    MESSAGE_RETENTION_SPECIAL_VALUES_MAP = {
        "unlimited": -1,
        "realm_default": None,
    }
    message_retention_days = models.IntegerField(null=True, default=None)

    # on_delete field here is set to RESTRICT because we don't want to allow
    # deleting a user group in case it is referenced by this setting.
    # We are not using PROTECT since we want to allow deletion of user groups
    # when realm itself is deleted.
    can_remove_subscribers_group = models.ForeignKey(UserGroup, on_delete=models.RESTRICT)

    # The very first message ID in the stream.  Used to help clients
    # determine whether they might need to display "more topics" for a
    # stream based on what messages they have cached.
    first_message_id = models.IntegerField(null=True, db_index=True)

    stream_permission_group_settings = {
        "can_remove_subscribers_group": GroupPermissionSetting(
            require_system_group=True,
            allow_internet_group=False,
            allow_owners_group=False,
            allow_nobody_group=False,
            allow_everyone_group=True,
            default_group_name=SystemGroups.ADMINISTRATORS,
            id_field_name="can_remove_subscribers_group_id",
        ),
    }

    class Meta:
        indexes = [
            models.Index(Upper("name"), name="upper_stream_name_idx"),
        ]

    @override
    def __str__(self) -> str:
        return self.name

    def is_public(self) -> bool:
        # All streams are private in Zephyr mirroring realms.
        return not self.invite_only and not self.is_in_zephyr_realm

    def is_history_realm_public(self) -> bool:
        return self.is_public()

    def is_history_public_to_subscribers(self) -> bool:
        return self.history_public_to_subscribers

    # Stream fields included whenever a Stream object is provided to
    # Zulip clients via the API.  A few details worth noting:
    # * "id" is represented as "stream_id" in most API interfaces.
    # * "email_token" is not realm-public and thus is not included here.
    # * is_in_zephyr_realm is a backend-only optimization.
    # * "deactivated" streams are filtered from the API entirely.
    # * "realm" and "recipient" are not exposed to clients via the API.
    API_FIELDS = [
        "date_created",
        "description",
        "first_message_id",
        "history_public_to_subscribers",
        "id",
        "invite_only",
        "is_web_public",
        "message_retention_days",
        "name",
        "rendered_description",
        "stream_post_policy",
        "can_remove_subscribers_group_id",
    ]

    def to_dict(self) -> DefaultStreamDict:
        return DefaultStreamDict(
            can_remove_subscribers_group=self.can_remove_subscribers_group_id,
            date_created=datetime_to_timestamp(self.date_created),
            description=self.description,
            first_message_id=self.first_message_id,
            history_public_to_subscribers=self.history_public_to_subscribers,
            invite_only=self.invite_only,
            is_web_public=self.is_web_public,
            message_retention_days=self.message_retention_days,
            name=self.name,
            rendered_description=self.rendered_description,
            stream_id=self.id,
            stream_post_policy=self.stream_post_policy,
            is_announcement_only=self.stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS,
        )


post_save.connect(flush_stream, sender=Stream)
post_delete.connect(flush_stream, sender=Stream)


class UserTopic(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    topic_name = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    # The default value for last_updated is a few weeks before tracking
    # of when topics were muted was first introduced.  It's designed
    # to be obviously incorrect so that one can tell it's backfilled data.
    last_updated = models.DateTimeField(default=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc))

    class VisibilityPolicy(models.IntegerChoices):
        # A normal muted topic. No notifications and unreads hidden.
        MUTED = 1, "Muted topic"

        # This topic will behave like an unmuted topic in an unmuted stream even if it
        # belongs to a muted stream.
        UNMUTED = 2, "Unmuted topic in muted stream"

        # This topic will behave like `UNMUTED`, plus some additional
        # display and/or notifications priority that is TBD and likely to
        # be configurable; see #6027. Not yet implemented.
        FOLLOWED = 3, "Followed topic"

        # Implicitly, if a UserTopic does not exist, the (user, topic)
        # pair should have normal behavior for that (user, stream) pair.

        # We use this in our code to represent the condition in the comment above.
        INHERIT = 0, "User's default policy for the stream."

    visibility_policy = models.SmallIntegerField(
        choices=VisibilityPolicy.choices, default=VisibilityPolicy.MUTED
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "user_profile",
                "stream",
                Lower("topic_name"),
                name="usertopic_case_insensitive_topic_uniq",
            ),
        ]

        indexes = [
            models.Index("stream", Upper("topic_name"), name="zerver_mutedtopic_stream_topic"),
            # This index is designed to optimize queries fetching the
            # set of users who have special policy for a stream,
            # e.g. for the send-message code paths.
            models.Index(
                fields=("stream", "topic_name", "visibility_policy", "user_profile"),
                name="zerver_usertopic_stream_topic_user_visibility_idx",
            ),
            # This index is useful for handling API requests fetching the
            # muted topics for a given user or user/stream pair.
            models.Index(
                fields=("user_profile", "visibility_policy", "stream", "topic_name"),
                name="zerver_usertopic_user_visibility_idx",
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"({self.user_profile.email}, {self.stream.name}, {self.topic_name}, {self.last_updated})"


class MutedUser(models.Model):
    user_profile = models.ForeignKey(UserProfile, related_name="muter", on_delete=CASCADE)
    muted_user = models.ForeignKey(UserProfile, related_name="muted", on_delete=CASCADE)
    date_muted = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user_profile", "muted_user")

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.email} -> {self.muted_user.email}"


post_save.connect(flush_muting_users_cache, sender=MutedUser)
post_delete.connect(flush_muting_users_cache, sender=MutedUser)


class Client(models.Model):
    MAX_NAME_LENGTH = 30
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True, unique=True)

    @override
    def __str__(self) -> str:
        return self.name

    def default_read_by_sender(self) -> bool:
        """Used to determine whether a message was sent by a full Zulip UI
        style client (and thus whether the message should be treated
        as sent by a human and automatically marked as read for the
        sender).  The purpose of this distinction is to ensure that
        message sent to the user by e.g. a Google Calendar integration
        using the user's own API key don't get marked as read
        automatically.
        """
        sending_client = self.name.lower()

        return (
            sending_client
            in (
                "zulipandroid",
                "zulipios",
                "zulipdesktop",
                "zulipmobile",
                "zulipelectron",
                "zulipterminal",
                "snipe",
                "website",
                "ios",
                "android",
            )
            or "desktop app" in sending_client
            # Since the vast majority of messages are sent by humans
            # in Zulip, treat test suite messages as such.
            or (sending_client == "test suite" and settings.TEST_SUITE)
        )


get_client_cache: Dict[str, Client] = {}


def clear_client_cache() -> None:  # nocoverage
    global get_client_cache
    get_client_cache = {}


def get_client(name: str) -> Client:
    # Accessing KEY_PREFIX through the module is necessary
    # because we need the updated value of the variable.
    cache_name = cache.KEY_PREFIX + name[0 : Client.MAX_NAME_LENGTH]
    if cache_name not in get_client_cache:
        result = get_client_remote_cache(name)
        get_client_cache[cache_name] = result
    return get_client_cache[cache_name]


def get_client_cache_key(name: str) -> str:
    return f"get_client:{hashlib.sha1(name.encode()).hexdigest()}"


@cache_with_key(get_client_cache_key, timeout=3600 * 24 * 7)
def get_client_remote_cache(name: str) -> Client:
    (client, _) = Client.objects.get_or_create(name=name[0 : Client.MAX_NAME_LENGTH])
    return client


def get_realm_stream(stream_name: str, realm_id: int) -> Stream:
    return Stream.objects.get(name__iexact=stream_name.strip(), realm_id=realm_id)


def get_active_streams(realm: Realm) -> QuerySet[Stream]:
    """
    Return all streams (including invite-only streams) that have not been deactivated.
    """
    return Stream.objects.filter(realm=realm, deactivated=False)


def get_linkable_streams(realm_id: int) -> QuerySet[Stream]:
    """
    This returns the streams that we are allowed to linkify using
    something like "#frontend" in our markup. For now the business
    rule is that you can link any stream in the realm that hasn't
    been deactivated (similar to how get_active_streams works).
    """
    return Stream.objects.filter(realm_id=realm_id, deactivated=False)


def get_stream(stream_name: str, realm: Realm) -> Stream:
    """
    Callers that don't have a Realm object already available should use
    get_realm_stream directly, to avoid unnecessarily fetching the
    Realm object.
    """
    return get_realm_stream(stream_name, realm.id)


def get_stream_by_id_in_realm(stream_id: int, realm: Realm) -> Stream:
    return Stream.objects.select_related("realm", "recipient").get(id=stream_id, realm=realm)


def bulk_get_streams(realm: Realm, stream_names: Set[str]) -> Dict[str, Any]:
    def fetch_streams_by_name(stream_names: Set[str]) -> QuerySet[Stream]:
        #
        # This should be just
        #
        # Stream.objects.select_related().filter(name__iexact__in=stream_names,
        #                                        realm_id=realm_id)
        #
        # But chaining __in and __iexact doesn't work with Django's
        # ORM, so we have the following hack to construct the relevant where clause
        where_clause = (
            "upper(zerver_stream.name::text) IN (SELECT upper(name) FROM unnest(%s) AS name)"
        )
        return get_active_streams(realm).extra(where=[where_clause], params=(list(stream_names),))

    if not stream_names:
        return {}
    streams = list(fetch_streams_by_name(stream_names))
    return {stream.name.lower(): stream for stream in streams}


def get_huddle_user_ids(recipient: Recipient) -> ValuesQuerySet["Subscription", int]:
    assert recipient.type == Recipient.HUDDLE

    return (
        Subscription.objects.filter(
            recipient=recipient,
        )
        .order_by("user_profile_id")
        .values_list("user_profile_id", flat=True)
    )


def bulk_get_huddle_user_ids(recipient_ids: List[int]) -> Dict[int, Set[int]]:
    """
    Takes a list of huddle-type recipient_ids, returns a dict
    mapping recipient id to list of user ids in the huddle.

    We rely on our caller to pass us recipient_ids that correspond
    to huddles, but technically this function is valid for any type
    of subscription.
    """
    if not recipient_ids:
        return {}

    subscriptions = Subscription.objects.filter(
        recipient_id__in=recipient_ids,
    ).only("user_profile_id", "recipient_id")

    result_dict: Dict[int, Set[int]] = defaultdict(set)
    for subscription in subscriptions:
        result_dict[subscription.recipient_id].add(subscription.user_profile_id)

    return result_dict


class AbstractMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # The target of the message is signified by the Recipient object.
    # See the Recipient class for details.
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)

    # The realm containing the message. Usually this will be the same
    # as the realm of the messages's sender; the exception to that is
    # cross-realm bot users.
    #
    # Important for efficient indexes and sharding in multi-realm servers.
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    # The message's topic.
    #
    # Early versions of Zulip called this concept a "subject", as in an email
    # "subject line", before changing to "topic" in 2013 (commit dac5a46fa).
    # UI and user documentation now consistently say "topic".  New APIs and
    # new code should generally also say "topic".
    #
    # See also the `topic_name` method on `Message`.
    subject = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH, db_index=True)

    # The raw Markdown-format text (E.g., what the user typed into the compose box).
    content = models.TextField()

    # The HTML rendered content resulting from rendering the content
    # with the Markdown processor.
    rendered_content = models.TextField(null=True)
    # A rarely-incremented version number, theoretically useful for
    # tracking which messages have been already rerendered when making
    # major changes to the markup rendering process.
    rendered_content_version = models.IntegerField(null=True)

    date_sent = models.DateTimeField("date sent", db_index=True)

    # A Client object indicating what type of Zulip client sent this message.
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)

    # The last time the message was modified by message editing or moving.
    last_edit_time = models.DateTimeField(null=True)

    # A JSON-encoded list of objects describing any past edits to this
    # message, oldest first.
    edit_history = models.TextField(null=True)

    # Whether the message contains a (link to) an uploaded file.
    has_attachment = models.BooleanField(default=False, db_index=True)
    # Whether the message contains a visible image element.
    has_image = models.BooleanField(default=False, db_index=True)
    # Whether the message contains a link.
    has_link = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True

    @override
    def __str__(self) -> str:
        return f"{self.recipient.label()} / {self.subject} / {self.sender!r}"


class ArchiveTransaction(models.Model):
    timestamp = models.DateTimeField(default=timezone_now, db_index=True)
    # Marks if the data archived in this transaction has been restored:
    restored = models.BooleanField(default=False, db_index=True)

    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types:
    RETENTION_POLICY_BASED = 1  # Archiving was executed due to automated retention policies
    MANUAL = 2  # Archiving was run manually, via move_messages_to_archive function

    # ForeignKey to the realm with which objects archived in this transaction are associated.
    # If type is set to MANUAL, this should be null.
    realm = models.ForeignKey(Realm, null=True, on_delete=CASCADE)

    @override
    def __str__(self) -> str:
        return "id: {id}, type: {type}, realm: {realm}, timestamp: {timestamp}".format(
            id=self.id,
            type="MANUAL" if self.type == self.MANUAL else "RETENTION_POLICY_BASED",
            realm=self.realm.string_id if self.realm else None,
            timestamp=self.timestamp,
        )


class ArchivedMessage(AbstractMessage):
    """Used as a temporary holding place for deleted messages before they
    are permanently deleted.  This is an important part of a robust
    'message retention' feature.
    """

    archive_transaction = models.ForeignKey(ArchiveTransaction, on_delete=CASCADE)


class Message(AbstractMessage):
    # Recipient types used when a Message object is provided to
    # Zulip clients via the API.
    #
    # A detail worth noting:
    # * "direct" was introduced in 2023 with the goal of
    #   deprecating the original "private" and becoming the
    #   preferred way to indicate a personal or huddle
    #   Recipient type via the API.
    API_RECIPIENT_TYPES = ["direct", "private", "stream"]

    search_tsvector = SearchVectorField(null=True)

    DEFAULT_SELECT_RELATED = ["sender", "realm", "recipient", "sending_client"]

    def topic_name(self) -> str:
        """
        Please start using this helper to facilitate an
        eventual switch over to a separate topic table.
        """
        return self.subject

    def set_topic_name(self, topic_name: str) -> None:
        self.subject = topic_name

    def is_stream_message(self) -> bool:
        """
        Find out whether a message is a stream message by
        looking up its recipient.type.  TODO: Make this
        an easier operation by denormalizing the message
        type onto Message, either explicitly (message.type)
        or implicitly (message.stream_id is not None).
        """
        return self.recipient.type == Recipient.STREAM

    def get_realm(self) -> Realm:
        return self.realm

    def save_rendered_content(self) -> None:
        self.save(update_fields=["rendered_content", "rendered_content_version"])

    @staticmethod
    def need_to_render_content(
        rendered_content: Optional[str],
        rendered_content_version: Optional[int],
        markdown_version: int,
    ) -> bool:
        return (
            rendered_content is None
            or rendered_content_version is None
            or rendered_content_version < markdown_version
        )

    @staticmethod
    def is_status_message(content: str, rendered_content: str) -> bool:
        """
        "status messages" start with /me and have special rendering:
            /me loves chocolate -> Full Name loves chocolate
        """
        if content.startswith("/me "):
            return True
        return False

    class Meta:
        indexes = [
            GinIndex("search_tsvector", fastupdate=False, name="zerver_message_search_tsvector"),
            models.Index(
                # For moving messages between streams or marking
                # streams as read.  The "id" at the end makes it easy
                # to scan the resulting messages in order, and perform
                # batching.
                "realm_id",
                "recipient_id",
                "id",
                name="zerver_message_realm_recipient_id",
            ),
            models.Index(
                # For generating digest emails and message archiving,
                # which both group by stream.
                "realm_id",
                "recipient_id",
                "date_sent",
                name="zerver_message_realm_recipient_date_sent",
            ),
            models.Index(
                # For exports, which want to limit both sender and
                # receiver.  The prefix of this index (realm_id,
                # sender_id) can be used for scrubbing users and/or
                # deleting users' messages.
                "realm_id",
                "sender_id",
                "recipient_id",
                name="zerver_message_realm_sender_recipient",
            ),
            models.Index(
                # For analytics queries
                "realm_id",
                "date_sent",
                name="zerver_message_realm_date_sent",
            ),
            models.Index(
                # For users searching by topic (but not stream), which
                # is done case-insensitively
                "realm_id",
                Upper("subject"),
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_upper_subject",
            ),
            models.Index(
                # Most stream/topic searches are case-insensitive by
                # topic name (e.g. messages_for_topic).  The "id" at
                # the end makes it easy to scan the resulting messages
                # in order, and perform batching.
                "realm_id",
                "recipient_id",
                Upper("subject"),
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_recipient_upper_subject",
            ),
            models.Index(
                # Used by already_sent_mirrored_message_id, and when
                # determining recent topics (we post-process to merge
                # and show the most recent case)
                "realm_id",
                "recipient_id",
                "subject",
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_recipient_subject",
            ),
            models.Index(
                # Only used by update_first_visible_message_id
                "realm_id",
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_id",
            ),
        ]


def get_context_for_message(message: Message) -> QuerySet[Message]:
    return Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_upper_subject
        realm_id=message.realm_id,
        recipient_id=message.recipient_id,
        subject__iexact=message.subject,
        id__lt=message.id,
        date_sent__gt=message.date_sent - timedelta(minutes=15),
    ).order_by("-id")[:10]


post_save.connect(flush_message, sender=Message)


class AbstractSubMessage(models.Model):
    # We can send little text messages that are associated with a regular
    # Zulip message.  These can be used for experimental widgets like embedded
    # games, surveys, mini threads, etc.  These are designed to be pretty
    # generic in purpose.

    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)
    msg_type = models.TextField()
    content = models.TextField()

    class Meta:
        abstract = True


class SubMessage(AbstractSubMessage):
    message = models.ForeignKey(Message, on_delete=CASCADE)

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = ["id", "message_id", "sender_id", "msg_type", "content"]
        query = SubMessage.objects.filter(message_id__in=needed_ids).values(*fields)
        query = query.order_by("message_id", "id")
        return list(query)


class ArchivedSubMessage(AbstractSubMessage):
    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)


post_save.connect(flush_submessage, sender=SubMessage)


class Draft(models.Model):
    """Server-side storage model for storing drafts so that drafts can be synced across
    multiple clients/devices.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)
    topic = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH, db_index=True)
    content = models.TextField()  # Length should not exceed MAX_MESSAGE_LENGTH
    last_edit_time = models.DateTimeField(db_index=True)

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.email} / {self.id} / {self.last_edit_time}"

    def to_dict(self) -> Dict[str, Any]:
        to, recipient_type_str = get_recipient_ids(self.recipient, self.user_profile_id)
        return {
            "id": self.id,
            "type": recipient_type_str,
            "to": to,
            "topic": self.topic,
            "content": self.content,
            "timestamp": int(self.last_edit_time.timestamp()),
        }


class AbstractEmoji(models.Model):
    """For emoji reactions to messages (and potentially future reaction types).

    Emoji are surprisingly complicated to implement correctly.  For details
    on how this subsystem works, see:
      https://zulip.readthedocs.io/en/latest/subsystems/emoji.html
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # The user-facing name for an emoji reaction.  With emoji aliases,
    # there may be multiple accepted names for a given emoji; this
    # field encodes which one the user selected.
    emoji_name = models.TextField()

    UNICODE_EMOJI = "unicode_emoji"
    REALM_EMOJI = "realm_emoji"
    ZULIP_EXTRA_EMOJI = "zulip_extra_emoji"
    REACTION_TYPES = (
        (UNICODE_EMOJI, gettext_lazy("Unicode emoji")),
        (REALM_EMOJI, gettext_lazy("Custom emoji")),
        (ZULIP_EXTRA_EMOJI, gettext_lazy("Zulip extra emoji")),
    )
    reaction_type = models.CharField(default=UNICODE_EMOJI, choices=REACTION_TYPES, max_length=30)

    # A string with the property that (realm, reaction_type,
    # emoji_code) uniquely determines the emoji glyph.
    #
    # We cannot use `emoji_name` for this purpose, since the
    # name-to-glyph mappings for unicode emoji change with time as we
    # update our emoji database, and multiple custom emoji can have
    # the same `emoji_name` in a realm (at most one can have
    # `deactivated=False`). The format for `emoji_code` varies by
    # `reaction_type`:
    #
    # * For Unicode emoji, a dash-separated hex encoding of the sequence of
    #   Unicode codepoints that define this emoji in the Unicode
    #   specification.  For examples, see "non_qualified" or "unified" in the
    #   following data, with "non_qualified" taking precedence when both present:
    #     https://raw.githubusercontent.com/iamcal/emoji-data/master/emoji_pretty.json
    #
    # * For user uploaded custom emoji (`reaction_type="realm_emoji"`), the stringified ID
    #   of the RealmEmoji object, computed as `str(realm_emoji.id)`.
    #
    # * For "Zulip extra emoji" (like :zulip:), the name of the emoji (e.g. "zulip").
    emoji_code = models.TextField()

    class Meta:
        abstract = True


class AbstractReaction(AbstractEmoji):
    class Meta:
        abstract = True
        unique_together = ("user_profile", "message", "reaction_type", "emoji_code")


class Reaction(AbstractReaction):
    message = models.ForeignKey(Message, on_delete=CASCADE)

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = [
            "message_id",
            "emoji_name",
            "emoji_code",
            "reaction_type",
            "user_profile__email",
            "user_profile_id",
            "user_profile__full_name",
        ]
        # The ordering is important here, as it makes it convenient
        # for clients to display reactions in order without
        # client-side sorting code.
        return Reaction.objects.filter(message_id__in=needed_ids).values(*fields).order_by("id")

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.email} / {self.message.id} / {self.emoji_name}"


class ArchivedReaction(AbstractReaction):
    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)


# Whenever a message is sent, for each user subscribed to the
# corresponding Recipient object (that is not long-term idle), we add
# a row to the UserMessage table indicating that that user received
# that message.  This table allows us to quickly query any user's last
# 1000 messages to generate the home view and search exactly the
# user's message history.
#
# The long-term idle optimization is extremely important for large,
# open organizations, and is described in detail here:
# https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#soft-deactivation
#
# In particular, new messages to public streams will only generate
# UserMessage rows for Members who are long_term_idle if they would
# have nonzero flags for the message (E.g. a mention, alert word, or
# mobile push notification).
#
# The flags field stores metadata like whether the user has read the
# message, starred or collapsed the message, was mentioned in the
# message, etc. We use of postgres partial indexes on flags to make
# queries for "User X's messages with flag Y" extremely fast without
# consuming much storage space.
#
# UserMessage is the largest table in many Zulip installations, even
# though each row is only 4 integers.
class AbstractUserMessage(models.Model):
    id = models.BigAutoField(primary_key=True)

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # The order here is important!  It's the order of fields in the bitfield.
    ALL_FLAGS = [
        "read",
        "starred",
        "collapsed",
        "mentioned",
        "stream_wildcard_mentioned",
        "topic_wildcard_mentioned",
        "group_mentioned",
        # These next 2 flags are from features that have since been removed.
        # We've cleared these 2 flags in migration 0486.
        "force_expand",
        "force_collapse",
        # Whether the message contains any of the user's alert words.
        "has_alert_word",
        # The historical flag is used to mark messages which the user
        # did not receive when they were sent, but later added to
        # their history via e.g. starring the message.  This is
        # important accounting for the "Subscribed to stream" dividers.
        "historical",
        # Whether the message is a direct message; this flag is a
        # denormalization of message.recipient.type to support an
        # efficient index on UserMessage for a user's direct messages.
        "is_private",
        # Whether we've sent a push notification to the user's mobile
        # devices for this message that has not been revoked.
        "active_mobile_push_notification",
    ]
    # Certain flags are used only for internal accounting within the
    # Zulip backend, and don't make sense to expose to the API.
    NON_API_FLAGS = {"is_private", "active_mobile_push_notification"}
    # Certain additional flags are just set once when the UserMessage
    # row is created.
    NON_EDITABLE_FLAGS = {
        # These flags are bookkeeping and don't make sense to edit.
        "has_alert_word",
        "mentioned",
        "stream_wildcard_mentioned",
        "topic_wildcard_mentioned",
        "group_mentioned",
        "historical",
        # Unused flags can't be edited.
        "force_expand",
        "force_collapse",
    }
    flags: BitHandler = BitField(flags=ALL_FLAGS, default=0)

    class Meta:
        abstract = True
        unique_together = ("user_profile", "message")

    @staticmethod
    def where_flag_is_present(flagattr: Bit) -> str:
        # Use this for Django ORM queries to access starred messages.
        # This custom SQL plays nice with our partial indexes.  Grep
        # the code for example usage.
        #
        # The key detail is that e.g.
        #   UserMessage.objects.filter(user_profile=user_profile, flags=UserMessage.flags.starred)
        # will generate a query involving `flags & 2 = 2`, which doesn't match our index.
        return f"flags & {1 << flagattr.number} <> 0"

    @staticmethod
    def where_flag_is_absent(flagattr: Bit) -> str:
        return f"flags & {1 << flagattr.number} = 0"

    @staticmethod
    def where_unread() -> str:
        return AbstractUserMessage.where_flag_is_absent(AbstractUserMessage.flags.read)

    @staticmethod
    def where_read() -> str:
        return AbstractUserMessage.where_flag_is_present(AbstractUserMessage.flags.read)

    @staticmethod
    def where_starred() -> str:
        return AbstractUserMessage.where_flag_is_present(AbstractUserMessage.flags.starred)

    @staticmethod
    def where_active_push_notification() -> str:
        return AbstractUserMessage.where_flag_is_present(
            AbstractUserMessage.flags.active_mobile_push_notification
        )

    def flags_list(self) -> List[str]:
        flags = int(self.flags)
        return self.flags_list_for_flags(flags)

    @staticmethod
    def flags_list_for_flags(val: int) -> List[str]:
        """
        This function is highly optimized, because it actually slows down
        sending messages in a naive implementation.
        """
        flags = []
        mask = 1
        for flag in UserMessage.ALL_FLAGS:
            if (val & mask) and flag not in AbstractUserMessage.NON_API_FLAGS:
                flags.append(flag)
            mask <<= 1
        return flags


class UserMessage(AbstractUserMessage):
    message = models.ForeignKey(Message, on_delete=CASCADE)

    class Meta(AbstractUserMessage.Meta):
        indexes = [
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.starred.mask),
                name="zerver_usermessage_starred_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.mentioned.mask),
                name="zerver_usermessage_mentioned_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andz=AbstractUserMessage.flags.read.mask),
                name="zerver_usermessage_unread_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.has_alert_word.mask),
                name="zerver_usermessage_has_alert_word_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.mentioned.mask)
                | Q(flags__andnz=AbstractUserMessage.flags.stream_wildcard_mentioned.mask),
                name="zerver_usermessage_wildcard_mentioned_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(
                    flags__andnz=AbstractUserMessage.flags.mentioned.mask
                    | AbstractUserMessage.flags.stream_wildcard_mentioned.mask
                    | AbstractUserMessage.flags.topic_wildcard_mentioned.mask
                    | AbstractUserMessage.flags.group_mentioned.mask
                ),
                name="zerver_usermessage_any_mentioned_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.is_private.mask),
                name="zerver_usermessage_is_private_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(
                    flags__andnz=AbstractUserMessage.flags.active_mobile_push_notification.mask
                ),
                name="zerver_usermessage_active_mobile_push_notification_id",
            ),
        ]

    @override
    def __str__(self) -> str:
        recipient_string = self.message.recipient.label()
        return f"{recipient_string} / {self.user_profile.email} ({self.flags_list()})"

    @staticmethod
    def select_for_update_query() -> QuerySet["UserMessage"]:
        """This SELECT FOR UPDATE query ensures consistent ordering on
        the row locks acquired by a bulk update operation to modify
        message flags using bitand/bitor.

        This consistent ordering is important to prevent deadlocks when
        2 or more bulk updates to the same rows in the UserMessage table
        race against each other (For example, if a client submits
        simultaneous duplicate API requests to mark a certain set of
        messages as read).
        """
        return UserMessage.objects.select_for_update().order_by("message_id")

    @staticmethod
    def has_any_mentions(user_profile_id: int, message_id: int) -> bool:
        # The query uses the 'zerver_usermessage_any_mentioned_message_id' index.
        return UserMessage.objects.filter(
            Q(
                flags__andnz=UserMessage.flags.mentioned.mask
                | UserMessage.flags.stream_wildcard_mentioned.mask
                | UserMessage.flags.topic_wildcard_mentioned.mask
                | UserMessage.flags.group_mentioned.mask
            ),
            user_profile_id=user_profile_id,
            message_id=message_id,
        ).exists()


def get_usermessage_by_message_id(
    user_profile: UserProfile, message_id: int
) -> Optional[UserMessage]:
    try:
        return UserMessage.objects.select_related().get(
            user_profile=user_profile, message_id=message_id
        )
    except UserMessage.DoesNotExist:
        return None


class ArchivedUserMessage(AbstractUserMessage):
    """Used as a temporary holding place for deleted UserMessages objects
    before they are permanently deleted.  This is an important part of
    a robust 'message retention' feature.
    """

    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)

    @override
    def __str__(self) -> str:
        recipient_string = self.message.recipient.label()
        return f"{recipient_string} / {self.user_profile.email} ({self.flags_list()})"


class AbstractAttachment(models.Model):
    file_name = models.TextField(db_index=True)

    # path_id is a storage location agnostic representation of the path of the file.
    # If the path of a file is http://localhost:9991/user_uploads/a/b/abc/temp_file.py
    # then its path_id will be a/b/abc/temp_file.py.
    path_id = models.TextField(db_index=True, unique=True)
    owner = models.ForeignKey(UserProfile, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    create_time = models.DateTimeField(
        default=timezone_now,
        db_index=True,
    )
    # Size of the uploaded file, in bytes
    size = models.IntegerField()

    # The two fields below serve as caches to let us avoid looking up
    # the corresponding messages/streams to check permissions before
    # serving these files.
    #
    # For both fields, the `null` state is used when a change in
    # message permissions mean that we need to determine their proper
    # value.

    # Whether this attachment has been posted to a public stream, and
    # thus should be available to all non-guest users in the
    # organization (even if they weren't a recipient of a message
    # linking to it).
    is_realm_public = models.BooleanField(default=False, null=True)
    # Whether this attachment has been posted to a web-public stream,
    # and thus should be available to everyone on the internet, even
    # if the person isn't logged in.
    is_web_public = models.BooleanField(default=False, null=True)

    class Meta:
        abstract = True

    @override
    def __str__(self) -> str:
        return self.file_name


class ArchivedAttachment(AbstractAttachment):
    """Used as a temporary holding place for deleted Attachment objects
    before they are permanently deleted.  This is an important part of
    a robust 'message retention' feature.

    Unlike the similar archive tables, ArchivedAttachment does not
    have an ArchiveTransaction foreign key, and thus will not be
    directly deleted by clean_archived_data. Instead, attachments that
    were only referenced by now fully deleted messages will leave
    ArchivedAttachment objects with empty `.messages`.

    A second step, delete_old_unclaimed_attachments, will delete the
    resulting orphaned ArchivedAttachment objects, along with removing
    the associated uploaded files from storage.
    """

    messages = models.ManyToManyField(
        ArchivedMessage, related_name="attachment_set", related_query_name="attachment"
    )


class Attachment(AbstractAttachment):
    messages = models.ManyToManyField(Message)

    # This is only present for Attachment and not ArchiveAttachment.
    # because ScheduledMessage is not subject to archiving.
    scheduled_messages = models.ManyToManyField("zerver.ScheduledMessage")

    def is_claimed(self) -> bool:
        return self.messages.exists() or self.scheduled_messages.exists()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.file_name,
            "path_id": self.path_id,
            "size": self.size,
            # convert to JavaScript-style UNIX timestamp so we can take
            # advantage of client time zones.
            "create_time": int(time.mktime(self.create_time.timetuple()) * 1000),
            "messages": [
                {
                    "id": m.id,
                    "date_sent": int(time.mktime(m.date_sent.timetuple()) * 1000),
                }
                for m in self.messages.all()
            ],
        }


post_save.connect(flush_used_upload_space_cache, sender=Attachment)
post_delete.connect(flush_used_upload_space_cache, sender=Attachment)


def validate_attachment_request_for_spectator_access(
    realm: Realm, attachment: Attachment
) -> Optional[bool]:
    if attachment.realm != realm:
        return False

    # Update cached is_web_public property, if necessary.
    if attachment.is_web_public is None:
        # Fill the cache in a single query. This is important to avoid
        # a potential race condition between checking and setting,
        # where the attachment could have been moved again.
        Attachment.objects.filter(id=attachment.id, is_web_public__isnull=True).update(
            is_web_public=Exists(
                Message.objects.filter(
                    # Uses index: zerver_attachment_messages_attachment_id_message_id_key
                    realm_id=realm.id,
                    attachment=OuterRef("id"),
                    recipient__stream__invite_only=False,
                    recipient__stream__is_web_public=True,
                ),
            ),
        )
        attachment.refresh_from_db()

    if not attachment.is_web_public:
        return False

    if settings.RATE_LIMITING:
        try:
            from zerver.lib.rate_limiter import rate_limit_spectator_attachment_access_by_file

            rate_limit_spectator_attachment_access_by_file(attachment.path_id)
        except RateLimitedError:
            return False

    return True


def validate_attachment_request(
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    path_id: str,
    realm: Optional[Realm] = None,
) -> Optional[bool]:
    try:
        attachment = Attachment.objects.get(path_id=path_id)
    except Attachment.DoesNotExist:
        return None

    if isinstance(maybe_user_profile, AnonymousUser):
        assert realm is not None
        return validate_attachment_request_for_spectator_access(realm, attachment)

    user_profile = maybe_user_profile
    assert isinstance(user_profile, UserProfile)

    # Update cached is_realm_public property, if necessary.
    if attachment.is_realm_public is None:
        # Fill the cache in a single query. This is important to avoid
        # a potential race condition between checking and setting,
        # where the attachment could have been moved again.
        Attachment.objects.filter(id=attachment.id, is_realm_public__isnull=True).update(
            is_realm_public=Exists(
                Message.objects.filter(
                    # Uses index: zerver_attachment_messages_attachment_id_message_id_key
                    realm_id=user_profile.realm_id,
                    attachment=OuterRef("id"),
                    recipient__stream__invite_only=False,
                ),
            ),
        )
        attachment.refresh_from_db()

    if user_profile == attachment.owner:
        # If you own the file, you can access it.
        return True
    if (
        attachment.is_realm_public
        and attachment.realm == user_profile.realm
        and user_profile.can_access_public_streams()
    ):
        # Any user in the realm can access realm-public files
        return True

    messages = attachment.messages.all()
    if UserMessage.objects.filter(user_profile=user_profile, message__in=messages).exists():
        # If it was sent in a direct message or private stream
        # message, then anyone who received that message can access it.
        return True

    # The user didn't receive any of the messages that included this
    # attachment.  But they might still have access to it, if it was
    # sent to a stream they are on where history is public to
    # subscribers.

    # These are subscriptions to a stream one of the messages was sent to
    relevant_stream_ids = Subscription.objects.filter(
        user_profile=user_profile,
        active=True,
        recipient__type=Recipient.STREAM,
        recipient__in=[m.recipient_id for m in messages],
    ).values_list("recipient__type_id", flat=True)
    if len(relevant_stream_ids) == 0:
        return False

    return Stream.objects.filter(
        id__in=relevant_stream_ids, history_public_to_subscribers=True
    ).exists()


def get_old_unclaimed_attachments(
    weeks_ago: int,
) -> Tuple[QuerySet[Attachment], QuerySet[ArchivedAttachment]]:
    """
    The logic in this function is fairly tricky. The essence is that
    a file should be cleaned up if and only if it not referenced by any
    Message, ScheduledMessage or ArchivedMessage. The way to find that out is through the
    Attachment and ArchivedAttachment tables.
    The queries are complicated by the fact that an uploaded file
    may have either only an Attachment row, only an ArchivedAttachment row,
    or both - depending on whether some, all or none of the messages
    linking to it have been archived.
    """
    delta_weeks_ago = timezone_now() - timedelta(weeks=weeks_ago)

    # The Attachment vs ArchivedAttachment queries are asymmetric because only
    # Attachment has the scheduled_messages relation.
    old_attachments = Attachment.objects.annotate(
        has_other_messages=Exists(
            ArchivedAttachment.objects.filter(id=OuterRef("id")).exclude(messages=None)
        )
    ).filter(
        messages=None,
        scheduled_messages=None,
        create_time__lt=delta_weeks_ago,
        has_other_messages=False,
    )
    old_archived_attachments = ArchivedAttachment.objects.annotate(
        has_other_messages=Exists(
            Attachment.objects.filter(id=OuterRef("id")).exclude(
                messages=None, scheduled_messages=None
            )
        )
    ).filter(messages=None, create_time__lt=delta_weeks_ago, has_other_messages=False)

    return old_attachments, old_archived_attachments


class Subscription(models.Model):
    """Keeps track of which users are part of the
    audience for a given Recipient object.

    For 1:1 and group direct message Recipient objects, only the
    user_profile and recipient fields have any meaning, defining the
    immutable set of users who are in the audience for that Recipient.

    For Recipient objects associated with a Stream, the remaining
    fields in this model describe the user's subscription to that stream.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)

    # Whether the user has since unsubscribed.  We mark Subscription
    # objects as inactive, rather than deleting them, when a user
    # unsubscribes, so we can preserve user customizations like
    # notification settings, stream color, etc., if the user later
    # resubscribes.
    active = models.BooleanField(default=True)
    # This is a denormalization designed to improve the performance of
    # bulk queries of Subscription objects, Whether the subscribed user
    # is active tends to be a key condition in those queries.
    # We intentionally don't specify a default value to promote thinking
    # about this explicitly, as in some special cases, such as data import,
    # we may be creating Subscription objects for a user that's deactivated.
    is_user_active = models.BooleanField()

    # Whether this user had muted this stream.
    is_muted = models.BooleanField(default=False)

    DEFAULT_STREAM_COLOR = "#c2c2c2"
    color = models.CharField(max_length=10, default=DEFAULT_STREAM_COLOR)
    pin_to_top = models.BooleanField(default=False)

    # These fields are stream-level overrides for the user's default
    # configuration for notification, configured in UserProfile.  The
    # default, None, means we just inherit the user-level default.
    desktop_notifications = models.BooleanField(null=True, default=None)
    audible_notifications = models.BooleanField(null=True, default=None)
    push_notifications = models.BooleanField(null=True, default=None)
    email_notifications = models.BooleanField(null=True, default=None)
    wildcard_mentions_notify = models.BooleanField(null=True, default=None)

    class Meta:
        unique_together = ("user_profile", "recipient")
        indexes = [
            models.Index(
                fields=("recipient", "user_profile"),
                name="zerver_subscription_recipient_id_user_profile_id_idx",
                condition=Q(active=True, is_user_active=True),
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.user_profile!r} -> {self.recipient!r}"

    # Subscription fields included whenever a Subscription object is provided to
    # Zulip clients via the API.  A few details worth noting:
    # * These fields will generally be merged with Stream.API_FIELDS
    #   data about the stream.
    # * "user_profile" is usually implied as full API access to Subscription
    #   is primarily done for the current user; API access to other users'
    #   subscriptions is generally limited to boolean yes/no.
    # * "id" and "recipient_id" are not included as they are not used
    #   in the Zulip API; it's an internal implementation detail.
    #   Subscription objects are always looked up in the API via
    #   (user_profile, stream) pairs.
    # * "active" is often excluded in API use cases where it is implied.
    # * "is_muted" often needs to be copied to not "in_home_view" for
    #   backwards-compatibility.
    API_FIELDS = [
        "audible_notifications",
        "color",
        "desktop_notifications",
        "email_notifications",
        "is_muted",
        "pin_to_top",
        "push_notifications",
        "wildcard_mentions_notify",
    ]


class Huddle(models.Model):
    """
    Represents a group of individuals who may have a
    group direct message conversation together.

    The membership of the Huddle is stored in the Subscription table just like with
    Streams - for each user in the Huddle, there is a Subscription object
    tied to the UserProfile and the Huddle's recipient object.

    A hash of the list of user IDs is stored in the huddle_hash field
    below, to support efficiently mapping from a set of users to the
    corresponding Huddle object.
    """

    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)
    # Foreign key to the Recipient object for this Huddle.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)


def get_huddle_hash(id_list: List[int]) -> str:
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return hashlib.sha1(hash_key.encode()).hexdigest()


def get_or_create_huddle(id_list: List[int]) -> Huddle:
    """
    Takes a list of user IDs and returns the Huddle object for the
    group consisting of these users. If the Huddle object does not
    yet exist, it will be transparently created.
    """
    huddle_hash = get_huddle_hash(id_list)
    with transaction.atomic():
        (huddle, created) = Huddle.objects.get_or_create(huddle_hash=huddle_hash)
        if created:
            recipient = Recipient.objects.create(type_id=huddle.id, type=Recipient.HUDDLE)
            huddle.recipient = recipient
            huddle.save(update_fields=["recipient"])
            subs_to_create = [
                Subscription(
                    recipient=recipient,
                    user_profile_id=user_profile_id,
                    is_user_active=is_active,
                )
                for user_profile_id, is_active in UserProfile.objects.filter(id__in=id_list)
                .distinct("id")
                .values_list("id", "is_active")
            ]
            Subscription.objects.bulk_create(subs_to_create)
        return huddle


class UserActivity(models.Model):
    """Data table recording the last time each user hit Zulip endpoints
    via which Clients; unlike UserPresence, these data are not exposed
    to users via the Zulip API.

    Useful for debugging as well as to answer analytics questions like
    "How many users have accessed the Zulip mobile app in the last
    month?" or "Which users/organizations have recently used API
    endpoint X that is about to be desupported" for communications
    and database migration purposes.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    client = models.ForeignKey(Client, on_delete=CASCADE)
    query = models.CharField(max_length=50, db_index=True)

    count = models.IntegerField()
    last_visit = models.DateTimeField("last visit")

    class Meta:
        unique_together = ("user_profile", "client", "query")


class UserActivityInterval(models.Model):
    MIN_INTERVAL_LENGTH = timedelta(minutes=15)

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    start = models.DateTimeField("start time", db_index=True)
    end = models.DateTimeField("end time", db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user_profile", "end"],
                name="zerver_useractivityinterval_user_profile_id_end_bb3bfc37_idx",
            ),
        ]


class UserPresence(models.Model):
    """A record from the last time we heard from a given user on a given client.

    NOTE: Users can disable updates to this table (see UserProfile.presence_enabled),
    so this cannot be used to determine if a user was recently active on Zulip.
    The UserActivity table is recommended for that purpose.

    This is a tricky subsystem, because it is highly optimized.  See the docs:
      https://zulip.readthedocs.io/en/latest/subsystems/presence.html
    """

    user_profile = models.OneToOneField(UserProfile, on_delete=CASCADE, unique=True)

    # Realm is just here as denormalization to optimize database
    # queries to fetch all presence data for a given realm.
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    # The last time the user had a client connected to Zulip,
    # including idle clients where the user hasn't interacted with the
    # system recently (and thus might be AFK).
    last_connected_time = models.DateTimeField(default=timezone_now, db_index=True, null=True)
    # The last time a client connected to Zulip reported that the user
    # was actually present (E.g. via focusing a browser window or
    # interacting with a computer running the desktop app)
    last_active_time = models.DateTimeField(default=timezone_now, db_index=True, null=True)

    # The following constants are used in the presence API for
    # communicating whether a user is active (last_active_time recent)
    # or idle (last_connected_time recent) or offline (neither
    # recent).  They're no longer part of the data model.
    LEGACY_STATUS_ACTIVE = "active"
    LEGACY_STATUS_IDLE = "idle"
    LEGACY_STATUS_ACTIVE_INT = 1
    LEGACY_STATUS_IDLE_INT = 2

    class Meta:
        indexes = [
            models.Index(
                fields=["realm", "last_active_time"],
                name="zerver_userpresence_realm_id_last_active_time_1c5aa9a2_idx",
            ),
            models.Index(
                fields=["realm", "last_connected_time"],
                name="zerver_userpresence_realm_id_last_connected_time_98d2fc9f_idx",
            ),
        ]

    @staticmethod
    def status_from_string(status: str) -> Optional[int]:
        if status == "active":
            return UserPresence.LEGACY_STATUS_ACTIVE_INT
        elif status == "idle":
            return UserPresence.LEGACY_STATUS_IDLE_INT

        return None


class UserStatus(AbstractEmoji):
    user_profile = models.OneToOneField(UserProfile, on_delete=CASCADE)

    timestamp = models.DateTimeField()
    client = models.ForeignKey(Client, on_delete=CASCADE)

    # Override emoji_name and emoji_code field of (AbstractReaction model) to accept
    # default value.
    emoji_name = models.TextField(default="")
    emoji_code = models.TextField(default="")

    status_text = models.CharField(max_length=255, default="")


class DefaultStream(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)

    class Meta:
        unique_together = ("realm", "stream")


class DefaultStreamGroup(models.Model):
    MAX_NAME_LENGTH = 60

    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    streams = models.ManyToManyField("zerver.Stream")
    description = models.CharField(max_length=1024, default="")

    class Meta:
        unique_together = ("realm", "name")

    def to_dict(self) -> Dict[str, Any]:
        return dict(
            name=self.name,
            id=self.id,
            description=self.description,
            streams=[stream.to_dict() for stream in self.streams.all().order_by("name")],
        )


def get_default_stream_groups(realm: Realm) -> QuerySet[DefaultStreamGroup]:
    return DefaultStreamGroup.objects.filter(realm=realm)


class AbstractScheduledJob(models.Model):
    scheduled_timestamp = models.DateTimeField(db_index=True)
    # JSON representation of arguments to consumer
    data = models.TextField()
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    class Meta:
        abstract = True


class ScheduledEmail(AbstractScheduledJob):
    # Exactly one of users or address should be set. These are
    # duplicate values, used to efficiently filter the set of
    # ScheduledEmails for use in clear_scheduled_emails; the
    # recipients used for actually sending messages are stored in the
    # data field of AbstractScheduledJob.
    users = models.ManyToManyField(UserProfile)
    # Just the address part of a full "name <address>" email address
    address = models.EmailField(null=True, db_index=True)

    # Valid types are below
    WELCOME = 1
    DIGEST = 2
    INVITATION_REMINDER = 3
    type = models.PositiveSmallIntegerField()

    @override
    def __str__(self) -> str:
        return f"{self.type} {self.address or list(self.users.all())} {self.scheduled_timestamp}"


class MissedMessageEmailAddress(models.Model):
    message = models.ForeignKey(Message, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    email_token = models.CharField(max_length=34, unique=True, db_index=True)

    # Timestamp of when the missed message address generated.
    timestamp = models.DateTimeField(db_index=True, default=timezone_now)
    # Number of times the missed message address has been used.
    times_used = models.PositiveIntegerField(default=0, db_index=True)

    @override
    def __str__(self) -> str:
        return settings.EMAIL_GATEWAY_PATTERN % (self.email_token,)

    def increment_times_used(self) -> None:
        self.times_used += 1
        self.save(update_fields=["times_used"])


class NotificationTriggers:
    # "direct_message" is for 1:1 direct messages as well as huddles
    DIRECT_MESSAGE = "direct_message"
    MENTION = "mentioned"
    TOPIC_WILDCARD_MENTION = "topic_wildcard_mentioned"
    STREAM_WILDCARD_MENTION = "stream_wildcard_mentioned"
    STREAM_PUSH = "stream_push_notify"
    STREAM_EMAIL = "stream_email_notify"
    FOLLOWED_TOPIC_PUSH = "followed_topic_push_notify"
    FOLLOWED_TOPIC_EMAIL = "followed_topic_email_notify"
    TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC = "topic_wildcard_mentioned_in_followed_topic"
    STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC = "stream_wildcard_mentioned_in_followed_topic"


class ScheduledMessageNotificationEmail(models.Model):
    """Stores planned outgoing message notification emails. They may be
    processed earlier should Zulip choose to batch multiple messages
    in a single email, but typically will be processed just after
    scheduled_timestamp.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    message = models.ForeignKey(Message, on_delete=CASCADE)

    EMAIL_NOTIFICATION_TRIGGER_CHOICES = [
        (NotificationTriggers.DIRECT_MESSAGE, "Direct message"),
        (NotificationTriggers.MENTION, "Mention"),
        (NotificationTriggers.TOPIC_WILDCARD_MENTION, "Topic wildcard mention"),
        (NotificationTriggers.STREAM_WILDCARD_MENTION, "Stream wildcard mention"),
        (NotificationTriggers.STREAM_EMAIL, "Stream notifications enabled"),
        (NotificationTriggers.FOLLOWED_TOPIC_EMAIL, "Followed topic notifications enabled"),
        (
            NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
            "Topic wildcard mention in followed topic",
        ),
        (
            NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
            "Stream wildcard mention in followed topic",
        ),
    ]

    trigger = models.TextField(choices=EMAIL_NOTIFICATION_TRIGGER_CHOICES)
    mentioned_user_group = models.ForeignKey(UserGroup, null=True, on_delete=CASCADE)

    # Timestamp for when the notification should be processed and sent.
    # Calculated from the time the event was received and the batching period.
    scheduled_timestamp = models.DateTimeField(db_index=True)


class APIScheduledStreamMessageDict(TypedDict):
    scheduled_message_id: int
    to: int
    type: str
    content: str
    rendered_content: str
    topic: str
    scheduled_delivery_timestamp: int
    failed: bool


class APIScheduledDirectMessageDict(TypedDict):
    scheduled_message_id: int
    to: List[int]
    type: str
    content: str
    rendered_content: str
    scheduled_delivery_timestamp: int
    failed: bool


class ScheduledMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    subject = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    content = models.TextField()
    rendered_content = models.TextField()
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    scheduled_timestamp = models.DateTimeField(db_index=True)
    read_by_sender = models.BooleanField()
    delivered = models.BooleanField(default=False)
    delivered_message = models.ForeignKey(Message, null=True, on_delete=CASCADE)
    has_attachment = models.BooleanField(default=False, db_index=True)

    # Metadata for messages that failed to send when their scheduled
    # moment arrived.
    failed = models.BooleanField(default=False)
    failure_message = models.TextField(null=True)

    SEND_LATER = 1
    REMIND = 2

    DELIVERY_TYPES = (
        (SEND_LATER, "send_later"),
        (REMIND, "remind"),
    )

    delivery_type = models.PositiveSmallIntegerField(
        choices=DELIVERY_TYPES,
        default=SEND_LATER,
    )

    class Meta:
        indexes = [
            # We expect a large number of delivered scheduled messages
            # to accumulate over time. This first index is for the
            # deliver_scheduled_messages worker.
            models.Index(
                name="zerver_unsent_scheduled_messages_by_time",
                fields=["scheduled_timestamp"],
                condition=Q(
                    delivered=False,
                    failed=False,
                ),
            ),
            # This index is for displaying scheduled messages to the
            # user themself via the API; we don't filter failed
            # messages since we will want to display those so that
            # failures don't just disappear into a black hole.
            models.Index(
                name="zerver_realm_unsent_scheduled_messages_by_user",
                fields=["realm_id", "sender", "delivery_type", "scheduled_timestamp"],
                condition=Q(
                    delivered=False,
                ),
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.recipient.label()} {self.subject} {self.sender!r} {self.scheduled_timestamp}"

    def topic_name(self) -> str:
        return self.subject

    def set_topic_name(self, topic_name: str) -> None:
        self.subject = topic_name

    def is_stream_message(self) -> bool:
        return self.recipient.type == Recipient.STREAM

    def to_dict(self) -> Union[APIScheduledStreamMessageDict, APIScheduledDirectMessageDict]:
        recipient, recipient_type_str = get_recipient_ids(self.recipient, self.sender.id)

        if recipient_type_str == "private":
            # The topic for direct messages should always be an empty string.
            assert self.topic_name() == ""

            return APIScheduledDirectMessageDict(
                scheduled_message_id=self.id,
                to=recipient,
                type=recipient_type_str,
                content=self.content,
                rendered_content=self.rendered_content,
                scheduled_delivery_timestamp=datetime_to_timestamp(self.scheduled_timestamp),
                failed=self.failed,
            )

        # The recipient for stream messages should always just be the unique stream ID.
        assert len(recipient) == 1

        return APIScheduledStreamMessageDict(
            scheduled_message_id=self.id,
            to=recipient[0],
            type=recipient_type_str,
            content=self.content,
            rendered_content=self.rendered_content,
            topic=self.topic_name(),
            scheduled_delivery_timestamp=datetime_to_timestamp(self.scheduled_timestamp),
            failed=self.failed,
        )


EMAIL_TYPES = {
    "account_registered": ScheduledEmail.WELCOME,
    "onboarding_zulip_topics": ScheduledEmail.WELCOME,
    "onboarding_zulip_guide": ScheduledEmail.WELCOME,
    "onboarding_team_to_zulip": ScheduledEmail.WELCOME,
    "digest": ScheduledEmail.DIGEST,
    "invitation_reminder": ScheduledEmail.INVITATION_REMINDER,
}


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
        UserGroup,
        null=True,
        on_delete=CASCADE,
    )
    event_last_message_id = models.IntegerField(null=True)

    @override
    def __str__(self) -> str:
        if self.modified_user is not None:
            return f"{self.modified_user!r} {self.event_type} {self.event_time} {self.id}"
        if self.modified_stream is not None:
            return f"{self.modified_stream!r} {self.event_type} {self.event_time} {self.id}"
        if self.modified_user_group is not None:
            return f"{self.modified_user_group!r} {self.event_type} {self.event_time} {self.id}"
        return f"{self.realm!r} {self.event_type} {self.event_time} {self.id}"

    class Meta:
        indexes = [
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
            )
        ]


class OnboardingStep(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)
    onboarding_step = models.CharField(max_length=30)
    timestamp = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user", "onboarding_step")


def check_valid_user_ids(realm_id: int, val: object, allow_deactivated: bool = False) -> List[int]:
    user_ids = check_list(check_int)("User IDs", val)
    realm = Realm.objects.get(id=realm_id)
    for user_id in user_ids:
        # TODO: Structurally, we should be doing a bulk fetch query to
        # get the users here, not doing these in a loop.  But because
        # this is a rarely used feature and likely to never have more
        # than a handful of users, it's probably mostly OK.
        try:
            user_profile = get_user_profile_by_id_in_realm(user_id, realm)
        except UserProfile.DoesNotExist:
            raise ValidationError(_("Invalid user ID: {user_id}").format(user_id=user_id))

        if not allow_deactivated and not user_profile.is_active:
            raise ValidationError(
                _("User with ID {user_id} is deactivated").format(user_id=user_id)
            )

        if user_profile.is_bot:
            raise ValidationError(_("User with ID {user_id} is a bot").format(user_id=user_id))

    return user_ids


class CustomProfileField(models.Model):
    """Defines a form field for the per-realm custom profile fields feature.

    See CustomProfileFieldValue for an individual user's values for one of
    these fields.
    """

    HINT_MAX_LENGTH = 80
    NAME_MAX_LENGTH = 40
    MAX_DISPLAY_IN_PROFILE_SUMMARY_FIELDS = 2

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    name = models.CharField(max_length=NAME_MAX_LENGTH)
    hint = models.CharField(max_length=HINT_MAX_LENGTH, default="")

    # Sort order for display of custom profile fields.
    order = models.IntegerField(default=0)

    # Whether the field should be displayed in smaller summary
    # sections of a page displaying custom profile fields.
    display_in_profile_summary = models.BooleanField(default=False)

    SHORT_TEXT = 1
    LONG_TEXT = 2
    SELECT = 3
    DATE = 4
    URL = 5
    USER = 6
    EXTERNAL_ACCOUNT = 7
    PRONOUNS = 8

    # These are the fields whose validators require more than var_name
    # and value argument. i.e. SELECT require field_data, USER require
    # realm as argument.
    SELECT_FIELD_TYPE_DATA: List[ExtendedFieldElement] = [
        (SELECT, gettext_lazy("List of options"), validate_select_field, str, "SELECT"),
    ]
    USER_FIELD_TYPE_DATA: List[UserFieldElement] = [
        (USER, gettext_lazy("Person picker"), check_valid_user_ids, orjson.loads, "USER"),
    ]

    SELECT_FIELD_VALIDATORS: Dict[int, ExtendedValidator] = {
        item[0]: item[2] for item in SELECT_FIELD_TYPE_DATA
    }
    USER_FIELD_VALIDATORS: Dict[int, RealmUserValidator] = {
        item[0]: item[2] for item in USER_FIELD_TYPE_DATA
    }

    FIELD_TYPE_DATA: List[FieldElement] = [
        # Type, display name, validator, converter, keyword
        (SHORT_TEXT, gettext_lazy("Short text"), check_short_string, str, "SHORT_TEXT"),
        (LONG_TEXT, gettext_lazy("Long text"), check_long_string, str, "LONG_TEXT"),
        (DATE, gettext_lazy("Date picker"), check_date, str, "DATE"),
        (URL, gettext_lazy("Link"), check_url, str, "URL"),
        (
            EXTERNAL_ACCOUNT,
            gettext_lazy("External account"),
            check_short_string,
            str,
            "EXTERNAL_ACCOUNT",
        ),
        (PRONOUNS, gettext_lazy("Pronouns"), check_short_string, str, "PRONOUNS"),
    ]

    ALL_FIELD_TYPES = [*FIELD_TYPE_DATA, *SELECT_FIELD_TYPE_DATA, *USER_FIELD_TYPE_DATA]

    FIELD_VALIDATORS: Dict[int, Validator[ProfileDataElementValue]] = {
        item[0]: item[2] for item in FIELD_TYPE_DATA
    }
    FIELD_CONVERTERS: Dict[int, Callable[[Any], Any]] = {
        item[0]: item[3] for item in ALL_FIELD_TYPES
    }
    FIELD_TYPE_CHOICES: List[Tuple[int, StrPromise]] = [
        (item[0], item[1]) for item in ALL_FIELD_TYPES
    ]

    field_type = models.PositiveSmallIntegerField(
        choices=FIELD_TYPE_CHOICES,
        default=SHORT_TEXT,
    )

    # A JSON blob of any additional data needed to define the field beyond
    # type/name/hint.
    #
    # The format depends on the type.  Field types SHORT_TEXT, LONG_TEXT,
    # DATE, URL, and USER leave this empty.  Fields of type SELECT store the
    # choices' descriptions.
    #
    # Note: There is no performance overhead of using TextField in PostgreSQL.
    # See https://www.postgresql.org/docs/9.0/static/datatype-character.html
    field_data = models.TextField(default="")

    class Meta:
        unique_together = ("realm", "name")

    @override
    def __str__(self) -> str:
        return f"{self.realm!r} {self.name} {self.field_type} {self.order}"

    def as_dict(self) -> ProfileDataElementBase:
        data_as_dict: ProfileDataElementBase = {
            "id": self.id,
            "name": self.name,
            "type": self.field_type,
            "hint": self.hint,
            "field_data": self.field_data,
            "order": self.order,
        }
        if self.display_in_profile_summary:
            data_as_dict["display_in_profile_summary"] = True

        return data_as_dict

    def is_renderable(self) -> bool:
        if self.field_type in [CustomProfileField.SHORT_TEXT, CustomProfileField.LONG_TEXT]:
            return True
        return False


def custom_profile_fields_for_realm(realm_id: int) -> QuerySet[CustomProfileField]:
    return CustomProfileField.objects.filter(realm=realm_id).order_by("order")


class CustomProfileFieldValue(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    field = models.ForeignKey(CustomProfileField, on_delete=CASCADE)
    value = models.TextField()
    rendered_value = models.TextField(null=True, default=None)

    class Meta:
        unique_together = ("user_profile", "field")

    @override
    def __str__(self) -> str:
        return f"{self.user_profile!r} {self.field!r} {self.value}"


# Interfaces for services
# They provide additional functionality like parsing message to obtain query URL, data to be sent to URL,
# and parsing the response.
GENERIC_INTERFACE = "GenericService"
SLACK_INTERFACE = "SlackOutgoingWebhookService"


# A Service corresponds to either an outgoing webhook bot or an embedded bot.
# The type of Service is determined by the bot_type field of the referenced
# UserProfile.
#
# If the Service is an outgoing webhook bot:
# - name is any human-readable identifier for the Service
# - base_url is the address of the third-party site
# - token is used for authentication with the third-party site
#
# If the Service is an embedded bot:
# - name is the canonical name for the type of bot (e.g. 'xkcd' for an instance
#   of the xkcd bot); multiple embedded bots can have the same name, but all
#   embedded bots with the same name will run the same code
# - base_url and token are currently unused
class Service(models.Model):
    name = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH)
    # Bot user corresponding to the Service.  The bot_type of this user
    # determines the type of service.  If non-bot services are added later,
    # user_profile can also represent the owner of the Service.
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    base_url = models.TextField()
    token = models.TextField()
    # Interface / API version of the service.
    interface = models.PositiveSmallIntegerField(default=1)

    # Valid interfaces are {generic, zulip_bot_service, slack}
    GENERIC = 1
    SLACK = 2

    ALLOWED_INTERFACE_TYPES = [
        GENERIC,
        SLACK,
    ]
    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _interfaces: Dict[int, str] = {
        GENERIC: GENERIC_INTERFACE,
        SLACK: SLACK_INTERFACE,
    }

    def interface_name(self) -> str:
        # Raises KeyError if invalid
        return self._interfaces[self.interface]


def get_bot_services(user_profile_id: int) -> List[Service]:
    return list(Service.objects.filter(user_profile_id=user_profile_id))


def get_service_profile(user_profile_id: int, service_name: str) -> Service:
    return Service.objects.get(user_profile_id=user_profile_id, name=service_name)


class BotStorageData(models.Model):
    bot_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    key = models.TextField(db_index=True)
    value = models.TextField()

    class Meta:
        unique_together = ("bot_profile", "key")


class BotConfigData(models.Model):
    bot_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    key = models.TextField(db_index=True)
    value = models.TextField()

    class Meta:
        unique_together = ("bot_profile", "key")


class AlertWord(models.Model):
    # Realm isn't necessary, but it's a nice denormalization.  Users
    # never move to another realm, so it's static, and having Realm
    # here optimizes the main query on this table, which is fetching
    # all the alert words in a realm.
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # Case-insensitive name for the alert word.
    word = models.TextField()

    class Meta:
        unique_together = ("user_profile", "word")


def flush_realm_alert_words(realm_id: int) -> None:
    cache_delete(realm_alert_words_cache_key(realm_id))
    cache_delete(realm_alert_words_automaton_cache_key(realm_id))


def flush_alert_word(*, instance: AlertWord, **kwargs: object) -> None:
    realm_id = instance.realm_id
    flush_realm_alert_words(realm_id)


post_save.connect(flush_alert_word, sender=AlertWord)
post_delete.connect(flush_alert_word, sender=AlertWord)

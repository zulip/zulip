import secrets
from typing import Any, Dict, Set

from django.db import models
from django.db.models import CASCADE, Q, QuerySet
from django.db.models.functions import Upper
from django.db.models.signals import post_delete, post_save
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise
from typing_extensions import override

from zerver.lib.cache import flush_stream
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import DefaultStreamDict, GroupPermissionSetting
from zerver.models.groups import SystemGroups, UserGroup
from zerver.models.realms import Realm
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


def generate_email_token_for_stream() -> str:
    return secrets.token_hex(16)


class Stream(models.Model):
    MAX_NAME_LENGTH = 60
    MAX_DESCRIPTION_LENGTH = 1024

    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    date_created = models.DateTimeField(default=timezone_now)
    creator = models.ForeignKey(UserProfile, null=True, on_delete=models.SET_NULL)
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
        STREAM_POST_POLICY_EVERYONE: gettext_lazy("All channel members can post"),
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
        "creator_id",
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
            creator_id=self.creator_id,
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

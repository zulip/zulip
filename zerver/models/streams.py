import secrets
from enum import Enum
from typing import Any

from django.db import models
from django.db.models import CASCADE, Q, QuerySet
from django.db.models.functions import Upper
from django.db.models.signals import post_delete, post_save
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy
from typing_extensions import override

from zerver.lib.cache import flush_stream
from zerver.lib.types import GroupPermissionSetting
from zerver.models.channel_folders import ChannelFolder
from zerver.models.groups import SystemGroups, UserGroup
from zerver.models.realms import Realm
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


def generate_email_token_for_stream() -> str:
    return secrets.token_hex(16)


class StreamTopicsPolicyEnum(Enum):
    inherit = 1
    allow_empty_topic = 2
    disable_empty_topic = 3
    empty_topic_only = 4


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

    # Total number of non-deactivated users who are subscribed to the channel.
    # It's obvious to be a positive field but also in case it becomes negative
    # we know immediately that something is wrong as it raises IntegrityError.
    subscriber_count = models.PositiveIntegerField(default=0, db_default=0)

    # Foreign key to the Recipient object for STREAM type messages to this stream.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

    folder = models.ForeignKey(ChannelFolder, null=True, on_delete=models.SET_NULL)

    # Various permission policy configurations
    PERMISSION_POLICIES: dict[str, dict[str, Any]] = {
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
    }
    invite_only = models.BooleanField(default=False)
    history_public_to_subscribers = models.BooleanField(default=True)

    # Whether this stream's content should be published by the web-public archive features
    is_web_public = models.BooleanField(default=False)

    # These values are used to map the can_send_message_group setting value
    # to the corresponding stream_post_policy value for legacy API clients
    # in get_stream_post_policy_value_based_on_group_setting defined in
    # zerver/lib/streams.py.
    STREAM_POST_POLICY_EVERYONE = 1
    STREAM_POST_POLICY_ADMINS = 2
    STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS = 3
    STREAM_POST_POLICY_MODERATORS = 4

    STREAM_POST_POLICY_TYPES = [
        STREAM_POST_POLICY_EVERYONE,
        STREAM_POST_POLICY_ADMINS,
        STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS,
        STREAM_POST_POLICY_MODERATORS,
    ]

    SYSTEM_GROUPS_ENUM_MAP = {
        SystemGroups.EVERYONE: STREAM_POST_POLICY_EVERYONE,
        SystemGroups.ADMINISTRATORS: STREAM_POST_POLICY_ADMINS,
        SystemGroups.FULL_MEMBERS: STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS,
        SystemGroups.MODERATORS: STREAM_POST_POLICY_MODERATORS,
    }

    # For old messages being automatically deleted.
    # Value NULL means "use retention policy of the realm".
    # Value -1 means "disable retention policy for this stream unconditionally".
    # Non-negative values have the natural meaning of "archive messages older than <value> days".
    MESSAGE_RETENTION_SPECIAL_VALUES_MAP = {
        "unlimited": -1,
        "realm_default": None,
    }
    message_retention_days = models.IntegerField(null=True, default=None)

    # on_delete field for group value settings is set to RESTRICT
    # because we don't want to allow deleting a user group in case it
    # is referenced by the respective setting. We are not using PROTECT
    # since we want to allow deletion of user groups when the realm
    # itself is deleted.
    can_add_subscribers_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_administer_channel_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_create_topic_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_delete_any_message_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_delete_own_message_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_move_messages_out_of_channel_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_move_messages_within_channel_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_remove_subscribers_group = models.ForeignKey(UserGroup, on_delete=models.RESTRICT)
    can_send_message_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_subscribe_group = models.ForeignKey(UserGroup, on_delete=models.RESTRICT, related_name="+")
    can_resolve_topics_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )

    # The very first message ID in the stream.  Used to help clients
    # determine whether they might need to display "show all topics" for a
    # stream based on what messages they have cached.
    first_message_id = models.IntegerField(null=True, db_index=True)

    LAST_ACTIVITY_DAYS_BEFORE_FOR_ACTIVE = 180

    # Whether a message has been sent to this stream in the last X days.
    is_recently_active = models.BooleanField(default=True, db_default=True)

    topics_policy = models.PositiveSmallIntegerField(default=StreamTopicsPolicyEnum.inherit.value)

    stream_permission_group_settings = {
        "can_add_subscribers_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name=SystemGroups.NOBODY,
        ),
        "can_administer_channel_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name="channel_creator",
        ),
        "can_create_topic_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.EVERYONE,
        ),
        "can_delete_any_message_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.NOBODY,
        ),
        "can_delete_own_message_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.NOBODY,
        ),
        "can_move_messages_out_of_channel_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.NOBODY,
        ),
        "can_move_messages_within_channel_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.NOBODY,
        ),
        "can_remove_subscribers_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.ADMINISTRATORS,
        ),
        "can_send_message_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.EVERYONE,
        ),
        "can_subscribe_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name=SystemGroups.NOBODY,
        ),
        "can_resolve_topics_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.NOBODY,
        ),
    }

    stream_permission_group_settings_requiring_content_access = [
        "can_add_subscribers_group",
        "can_subscribe_group",
    ]
    assert set(stream_permission_group_settings_requiring_content_access).issubset(
        stream_permission_group_settings.keys()
    )

    stream_permission_group_settings_granting_metadata_access = [
        "can_add_subscribers_group",
        "can_administer_channel_group",
        "can_subscribe_group",
    ]
    assert set(stream_permission_group_settings_granting_metadata_access).issubset(
        stream_permission_group_settings.keys()
    )

    class Meta:
        indexes = [
            models.Index(Upper("name"), name="upper_stream_name_idx"),
        ]

    @override
    def __str__(self) -> str:
        return self.name

    def is_public(self) -> bool:
        return not self.invite_only

    def is_history_realm_public(self) -> bool:
        return self.is_public()

    def is_history_public_to_subscribers(self) -> bool:
        return self.history_public_to_subscribers

    # Stream fields included whenever a Stream object is provided to
    # Zulip clients via the API.  A few details worth noting:
    # * "id" is represented as "stream_id" in most API interfaces.
    # * "deactivated" streams are filtered from the API entirely.
    # * "realm" and "recipient" are not exposed to clients via the API.
    API_FIELDS = [
        "creator_id",
        "date_created",
        "deactivated",
        "description",
        "first_message_id",
        "folder_id",
        "history_public_to_subscribers",
        "id",
        "invite_only",
        "is_web_public",
        "message_retention_days",
        "name",
        "rendered_description",
        "subscriber_count",
        "can_add_subscribers_group_id",
        "can_administer_channel_group_id",
        "can_create_topic_group_id",
        "can_delete_any_message_group_id",
        "can_delete_own_message_group_id",
        "can_move_messages_out_of_channel_group_id",
        "can_move_messages_within_channel_group_id",
        "can_send_message_group_id",
        "can_remove_subscribers_group_id",
        "can_subscribe_group_id",
        "can_resolve_topics_group_id",
        "is_recently_active",
        "topics_policy",
    ]


post_save.connect(flush_stream, sender=Stream)
post_delete.connect(flush_stream, sender=Stream)


def get_realm_stream(stream_name: str, realm_id: int) -> Stream:
    return Stream.objects.get(name__iexact=stream_name.strip(), realm_id=realm_id)


def get_active_streams(realm: Realm) -> QuerySet[Stream]:
    """
    Return all streams (including invite-only streams) that have not been deactivated.
    """
    return Stream.objects.filter(realm=realm, deactivated=False)


def get_all_streams(realm: Realm, include_archived_channels: bool = True) -> QuerySet[Stream]:
    """
    Return all streams for `include_archived_channels`= true (including invite-only and deactivated streams).
    """
    if not include_archived_channels:
        return get_active_streams(realm)

    return Stream.objects.filter(realm=realm)


def get_stream(stream_name: str, realm: Realm) -> Stream:
    """
    Callers that don't have a Realm object already available should use
    get_realm_stream directly, to avoid unnecessarily fetching the
    Realm object.
    """
    return get_realm_stream(stream_name, realm.id)


def get_stream_by_id_in_realm(stream_id: int, realm: Realm) -> Stream:
    return Stream.objects.select_related("realm", "recipient").get(id=stream_id, realm=realm)


def get_stream_by_name_for_sending_message(stream_name: str, realm: Realm) -> Stream:
    return Stream.objects.select_related(
        "can_send_message_group",
        "can_send_message_group__named_user_group",
        "can_create_topic_group",
        "can_create_topic_group__named_user_group",
    ).get(name__iexact=stream_name.strip(), realm_id=realm.id)


def get_stream_by_id_for_sending_message(stream_id: int, realm: Realm) -> Stream:
    return Stream.objects.select_related(
        "realm",
        "recipient",
        "can_send_message_group",
        "can_send_message_group__named_user_group",
        "can_create_topic_group",
        "can_create_topic_group__named_user_group",
    ).get(id=stream_id, realm=realm)


def bulk_get_streams(realm: Realm, stream_names: set[str]) -> dict[str, Any]:
    def fetch_streams_by_name(stream_names: set[str]) -> QuerySet[Stream]:
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
        return (
            get_all_streams(realm, include_archived_channels=True)
            .select_related("can_send_message_group", "can_send_message_group__named_user_group")
            .extra(where=[where_clause], params=(list(stream_names),))  # noqa: S610
        )

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

    def to_dict(self) -> dict[str, Any]:
        return dict(
            name=self.name,
            id=self.id,
            description=self.description,
            streams=[stream.id for stream in self.streams.all().order_by("name")],
        )


def get_default_stream_groups(realm: Realm) -> QuerySet[DefaultStreamGroup]:
    return DefaultStreamGroup.objects.filter(realm=realm)


class ChannelEmailAddress(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    channel = models.ForeignKey(Stream, on_delete=CASCADE)
    creator = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE, related_name="+")
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE, related_name="+")

    # Used by the e-mail forwarder. The e-mail RFC specifies a maximum
    # e-mail length of 254, and our max stream length is 30, so we
    # have plenty of room for the token.
    email_token = models.CharField(
        max_length=32,
        default=generate_email_token_for_stream,
        unique=True,
        db_index=True,
    )

    date_created = models.DateTimeField(default=timezone_now)
    deactivated = models.BooleanField(default=False)

    class Meta:
        unique_together = ("channel", "creator", "sender")
        indexes = [
            models.Index(
                fields=("realm", "channel"),
                name="zerver_channelemailaddress_realm_id_channel_id_idx",
            ),
        ]

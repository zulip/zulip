from collections.abc import Collection
from datetime import datetime, timedelta
from typing import TypedDict

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet, Value
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.default_streams import get_default_stream_ids_for_realm
from zerver.lib.exceptions import (
    CannotAdministerChannelError,
    IncompatibleParametersError,
    JsonableError,
    OrganizationOwnerRequiredError,
)
from zerver.lib.markdown import markdown_convert
from zerver.lib.stream_subscription import (
    get_active_subscriptions_for_stream_id,
    get_subscribed_stream_ids_for_user,
)
from zerver.lib.stream_traffic import get_average_weekly_stream_traffic, get_streams_traffic
from zerver.lib.string_validation import check_stream_name
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import AnonymousSettingGroupDict, APIStreamDict
from zerver.lib.user_groups import (
    get_group_setting_value_for_api,
    get_role_based_system_groups_dict,
    user_has_permission_for_group_setting,
)
from zerver.models import (
    DefaultStreamGroup,
    GroupGroupMembership,
    Message,
    NamedUserGroup,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserGroup,
    UserGroupMembership,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.streams import (
    bulk_get_streams,
    get_realm_stream,
    get_stream,
    get_stream_by_id_for_sending_message,
    get_stream_by_id_in_realm,
)
from zerver.models.users import active_non_guest_user_ids, active_user_ids, is_cross_realm_bot_email
from zerver.tornado.django_api import send_event_on_commit


class StreamDict(TypedDict, total=False):
    """
    This type ultimately gets used in two places:

        - we use it to create a stream
        - we use it to specify a stream


    It's possible we want a smaller type to use
    for removing streams, but it would complicate
    how we write the types for list_to_stream.

    Note that these fields are just a subset of
    the fields in the Stream model.
    """

    name: str
    description: str
    invite_only: bool
    is_web_public: bool
    stream_post_policy: int
    history_public_to_subscribers: bool | None
    message_retention_days: int | None
    can_administer_channel_group: UserGroup | None
    can_send_message_group: UserGroup | None
    can_remove_subscribers_group: UserGroup | None


def get_stream_permission_policy_name(
    *,
    invite_only: bool | None = None,
    history_public_to_subscribers: bool | None = None,
    is_web_public: bool | None = None,
) -> str:
    policy_name = None
    for permission_dict in Stream.PERMISSION_POLICIES.values():
        if (
            permission_dict["invite_only"] == invite_only
            and permission_dict["history_public_to_subscribers"] == history_public_to_subscribers
            and permission_dict["is_web_public"] == is_web_public
        ):
            policy_name = permission_dict["policy_name"]
            break

    assert policy_name is not None
    return policy_name


def get_default_value_for_history_public_to_subscribers(
    realm: Realm,
    invite_only: bool,
    history_public_to_subscribers: bool | None,
) -> bool:
    if invite_only:
        if history_public_to_subscribers is None:
            # A private stream's history is non-public by default
            history_public_to_subscribers = False
    else:
        # If we later decide to support public streams without
        # history, we can remove this code path.
        history_public_to_subscribers = True

    if realm.is_zephyr_mirror_realm:
        # In the Zephyr mirroring model, history is unconditionally
        # not public to subscribers, even for public streams.
        history_public_to_subscribers = False

    return history_public_to_subscribers


def render_stream_description(text: str, realm: Realm) -> str:
    return markdown_convert(text, message_realm=realm, no_previews=True).rendered_content


def send_stream_creation_event(
    realm: Realm,
    stream: Stream,
    user_ids: list[int],
    recent_traffic: dict[int, int] | None = None,
    setting_groups_dict: dict[int, int | AnonymousSettingGroupDict] | None = None,
) -> None:
    event = dict(
        type="stream",
        op="create",
        streams=[stream_to_dict(stream, recent_traffic, setting_groups_dict)],
    )
    send_event_on_commit(realm, event, user_ids)


def get_stream_permission_default_group(
    setting_name: str,
    system_groups_name_dict: dict[str, NamedUserGroup],
    creator: UserProfile | None = None,
) -> UserGroup:
    setting_default_name = Stream.stream_permission_group_settings[setting_name].default_group_name
    if setting_default_name == "stream_creator_or_nobody":
        if creator:
            default_group = UserGroup(
                realm=creator.realm,
            )
            default_group.save()
            UserGroupMembership.objects.create(user_profile=creator, user_group=default_group)
            return default_group
        else:
            return system_groups_name_dict[SystemGroups.NOBODY]
    return system_groups_name_dict[setting_default_name]


def get_default_values_for_stream_permission_group_settings(
    realm: Realm, creator: UserProfile | None = None
) -> dict[str, UserGroup]:
    group_setting_values = {}
    system_groups_name_dict = get_role_based_system_groups_dict(realm)
    for setting_name in Stream.stream_permission_group_settings:
        group_setting_values[setting_name] = get_stream_permission_default_group(
            setting_name, system_groups_name_dict, creator
        )

    return group_setting_values


@transaction.atomic(savepoint=False)
def create_stream_if_needed(
    realm: Realm,
    stream_name: str,
    *,
    invite_only: bool = False,
    is_web_public: bool = False,
    history_public_to_subscribers: bool | None = None,
    stream_description: str = "",
    message_retention_days: int | None = None,
    can_administer_channel_group: UserGroup | None = None,
    can_send_message_group: UserGroup | None = None,
    can_remove_subscribers_group: UserGroup | None = None,
    acting_user: UserProfile | None = None,
    setting_groups_dict: dict[int, int | AnonymousSettingGroupDict] | None = None,
) -> tuple[Stream, bool]:
    history_public_to_subscribers = get_default_value_for_history_public_to_subscribers(
        realm, invite_only, history_public_to_subscribers
    )

    group_setting_values = {}
    request_settings_dict = locals()
    # We don't want to calculate this value if no default values are
    # needed.
    system_groups_name_dict = None
    for setting_name in Stream.stream_permission_group_settings:
        if setting_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_name] is None:
            if system_groups_name_dict is None:
                system_groups_name_dict = get_role_based_system_groups_dict(realm)
            group_setting_values[setting_name] = get_stream_permission_default_group(
                setting_name, system_groups_name_dict, creator=acting_user
            )
        else:
            group_setting_values[setting_name] = request_settings_dict[setting_name]

    stream_name = stream_name.strip()

    (stream, created) = Stream.objects.get_or_create(
        realm=realm,
        name__iexact=stream_name,
        defaults=dict(
            name=stream_name,
            creator=acting_user,
            description=stream_description,
            invite_only=invite_only,
            is_web_public=is_web_public,
            history_public_to_subscribers=history_public_to_subscribers,
            is_in_zephyr_realm=realm.is_zephyr_mirror_realm,
            message_retention_days=message_retention_days,
            **group_setting_values,
        ),
    )

    if created:
        recipient = Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)

        stream.recipient = recipient
        stream.rendered_description = render_stream_description(stream_description, realm)
        stream.save(update_fields=["recipient", "rendered_description"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=AuditLogEventType.CHANNEL_CREATED,
            event_time=event_time,
        )

        if setting_groups_dict is None:
            setting_groups_dict = get_group_setting_value_dict_for_streams([stream])

        if stream.is_public():
            if stream.is_web_public:
                notify_user_ids = active_user_ids(stream.realm_id)
            else:
                notify_user_ids = active_non_guest_user_ids(stream.realm_id)
            send_stream_creation_event(
                realm, stream, notify_user_ids, setting_groups_dict=setting_groups_dict
            )
        else:
            realm_admin_ids = [user.id for user in stream.realm.get_admin_users_and_bots()]
            send_stream_creation_event(
                realm, stream, realm_admin_ids, setting_groups_dict=setting_groups_dict
            )

    return stream, created


def create_streams_if_needed(
    realm: Realm,
    stream_dicts: list[StreamDict],
    acting_user: UserProfile | None = None,
    setting_groups_dict: dict[int, int | AnonymousSettingGroupDict] | None = None,
) -> tuple[list[Stream], list[Stream]]:
    """Note that stream_dict["name"] is assumed to already be stripped of
    whitespace"""
    added_streams: list[Stream] = []
    existing_streams: list[Stream] = []
    for stream_dict in stream_dicts:
        invite_only = stream_dict.get("invite_only", False)
        stream, created = create_stream_if_needed(
            realm,
            stream_dict["name"],
            invite_only=invite_only,
            is_web_public=stream_dict.get("is_web_public", False),
            history_public_to_subscribers=stream_dict.get("history_public_to_subscribers"),
            stream_description=stream_dict.get("description", ""),
            message_retention_days=stream_dict.get("message_retention_days", None),
            can_administer_channel_group=stream_dict.get("can_administer_channel_group", None),
            can_send_message_group=stream_dict.get("can_send_message_group", None),
            can_remove_subscribers_group=stream_dict.get("can_remove_subscribers_group", None),
            acting_user=acting_user,
            setting_groups_dict=setting_groups_dict,
        )

        if created:
            added_streams.append(stream)
        else:
            existing_streams.append(stream)

    return added_streams, existing_streams


def subscribed_to_stream(user_profile: UserProfile, stream_id: int) -> bool:
    return Subscription.objects.filter(
        user_profile=user_profile,
        active=True,
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream_id,
    ).exists()


def check_stream_access_based_on_can_send_message_group(
    sender: UserProfile, stream: Stream
) -> None:
    if is_cross_realm_bot_email(sender.delivery_email):
        return

    can_send_message_group = stream.can_send_message_group
    if hasattr(can_send_message_group, "named_user_group"):
        if can_send_message_group.named_user_group.name == SystemGroups.EVERYONE:
            return

        if can_send_message_group.named_user_group.name == SystemGroups.NOBODY:
            raise JsonableError(_("You do not have permission to post in this channel."))

    if not user_has_permission_for_group_setting(
        stream.can_send_message_group,
        sender,
        Stream.stream_permission_group_settings["can_send_message_group"],
        direct_member_only=False,
    ):
        raise JsonableError(_("You do not have permission to post in this channel."))


def access_stream_for_send_message(
    sender: UserProfile,
    stream: Stream,
    forwarder_user_profile: UserProfile | None,
    archived_channel_notice: bool = False,
) -> None:
    # Our caller is responsible for making sure that `stream` actually
    # matches the realm of the sender.
    try:
        check_stream_access_based_on_can_send_message_group(sender, stream)
    except JsonableError as e:
        if sender.is_bot and sender.bot_owner is not None:
            check_stream_access_based_on_can_send_message_group(sender.bot_owner, stream)
        else:
            raise JsonableError(e.msg)

    # forwarder_user_profile cases should be analyzed first, as incorrect
    # message forging is cause for denying access regardless of any other factors.
    if forwarder_user_profile is not None and forwarder_user_profile != sender:
        if (
            forwarder_user_profile.can_forge_sender
            and forwarder_user_profile.realm_id == sender.realm_id
            and sender.realm_id == stream.realm_id
        ):
            return
        else:
            raise JsonableError(_("User not authorized for this query"))

    # Deactivated streams are not accessible.
    if stream.deactivated:
        if archived_channel_notice:
            return
        raise JsonableError(
            _("Not authorized to send to channel '{channel_name}'").format(channel_name=stream.name)
        )

    if is_cross_realm_bot_email(sender.delivery_email):
        return

    if stream.realm_id != sender.realm_id:
        # Sending to other realm's streams is always disallowed,
        # with the exception of cross-realm bots.
        raise JsonableError(_("User not authorized for this query"))

    if stream.is_web_public:
        # Even guest users can write to web-public streams.
        return

    if not (stream.invite_only or sender.is_guest):
        # This is a public stream and sender is not a guest user
        return

    if subscribed_to_stream(sender, stream.id):
        # It is private, but your are subscribed
        return

    if sender.can_forge_sender:
        # can_forge_sender allows sending to any stream in the realm.
        return

    if sender.is_bot and (
        sender.bot_owner is not None and subscribed_to_stream(sender.bot_owner, stream.id)
    ):
        # Bots can send to any stream their owner can.
        return

    # All other cases are an error.
    raise JsonableError(
        _("Not authorized to send to channel '{channel_name}'").format(channel_name=stream.name)
    )


def check_for_exactly_one_stream_arg(stream_id: int | None, stream: str | None) -> None:
    if stream_id is None and stream is None:
        # Uses the same translated string as RequestVariableMissingError
        # with the stream_id parameter, which is the more common use case.
        error = _("Missing '{var_name}' argument").format(var_name="stream_id")
        raise JsonableError(error)

    if stream_id is not None and stream is not None:
        raise IncompatibleParametersError(["stream_id", "stream"])


def check_stream_access_for_delete_or_update(
    user_profile: UserProfile, stream: Stream, sub: Subscription | None = None
) -> None:
    error = _("Invalid channel ID")
    if stream.realm_id != user_profile.realm_id:
        raise JsonableError(error)

    if user_profile.is_realm_admin:
        return

    if sub is None and stream.invite_only:
        raise JsonableError(error)

    if can_administer_channel(stream, user_profile):
        return

    raise CannotAdministerChannelError


def access_stream_for_delete_or_update(
    user_profile: UserProfile, stream_id: int
) -> tuple[Stream, Subscription | None]:
    try:
        stream = Stream.objects.get(id=stream_id)
    except Stream.DoesNotExist:
        raise JsonableError(_("Invalid channel ID"))

    try:
        sub = Subscription.objects.get(
            user_profile=user_profile, recipient=stream.recipient, active=True
        )
    except Subscription.DoesNotExist:
        sub = None

    check_stream_access_for_delete_or_update(user_profile, stream, sub)
    return (stream, sub)


def check_basic_stream_access(
    user_profile: UserProfile,
    stream: Stream,
    sub: Subscription | None,
    allow_realm_admin: bool = False,
) -> bool:
    # Any realm user, even guests, can access web_public streams.
    if stream.is_web_public:
        return True

    # If the stream is in your realm and public, you can access it.
    if stream.is_public() and not user_profile.is_guest:
        return True

    # Or if you are subscribed to the stream, you can access it.
    if sub is not None:
        return True

    # For some specific callers (e.g. getting list of subscribers,
    # removing other users from a stream, and updating stream name and
    # description), we allow realm admins to access stream even if
    # they are not subscribed to a private stream.
    if user_profile.is_realm_admin and allow_realm_admin:
        return True

    return False


# Only set allow_realm_admin flag to True when you want to allow realm admin to
# access unsubscribed private stream content.
def access_stream_common(
    user_profile: UserProfile,
    stream: Stream,
    error: str,
    require_active: bool = True,
    allow_realm_admin: bool = False,
) -> Subscription | None:
    """Common function for backend code where the target use attempts to
    access the target stream, returning all the data fetched along the
    way.  If that user does not have permission to access that stream,
    we throw an exception.  A design goal is that the error message is
    the same for streams you can't access and streams that don't exist."""

    # First, we don't allow any access to streams in other realms.
    if stream.realm_id != user_profile.realm_id:
        # Callers should verify this on their own, so this functions as defensive code.
        raise AssertionError("user_profile and stream realms don't match")

    try:
        assert stream.recipient_id is not None
        sub = Subscription.objects.get(
            user_profile=user_profile, recipient_id=stream.recipient_id, active=require_active
        )
    except Subscription.DoesNotExist:
        sub = None

    if not stream.deactivated and check_basic_stream_access(
        user_profile, stream, sub, allow_realm_admin=allow_realm_admin
    ):
        return sub

    # Otherwise it is a private stream and you're not on it, so throw
    # an error.
    raise JsonableError(error)


def access_stream_by_id(
    user_profile: UserProfile,
    stream_id: int,
    require_active: bool = True,
    allow_realm_admin: bool = False,
) -> tuple[Stream, Subscription | None]:
    error = _("Invalid channel ID")
    try:
        stream = get_stream_by_id_in_realm(stream_id, user_profile.realm)
    except Stream.DoesNotExist:
        raise JsonableError(error)

    sub = access_stream_common(
        user_profile,
        stream,
        error,
        require_active=require_active,
        allow_realm_admin=allow_realm_admin,
    )
    return (stream, sub)


def access_stream_by_id_for_message(
    user_profile: UserProfile,
    stream_id: int,
    require_active: bool = True,
    allow_realm_admin: bool = False,
) -> tuple[Stream, Subscription | None]:
    """
    Variant of access_stream_by_id that uses get_stream_by_id_for_sending_message
    to ensure we do a select_related("can_send_message_group").
    """
    error = _("Invalid channel ID")
    try:
        stream = get_stream_by_id_for_sending_message(stream_id, user_profile.realm)
    except Stream.DoesNotExist:
        raise JsonableError(error)

    sub = access_stream_common(
        user_profile,
        stream,
        error,
        require_active=require_active,
        allow_realm_admin=allow_realm_admin,
    )
    return (stream, sub)


def get_public_streams_queryset(realm: Realm) -> QuerySet[Stream]:
    return Stream.objects.filter(realm=realm, invite_only=False, history_public_to_subscribers=True)


def get_web_public_streams_queryset(realm: Realm) -> QuerySet[Stream]:
    # This should match the include_web_public code path in do_get_streams.
    return Stream.objects.filter(
        realm=realm,
        is_web_public=True,
        # In theory, nothing conflicts with allowing web-public access
        # to deactivated streams.  However, we should offer a way to
        # review archived streams and adjust their settings before
        # allowing that configuration to exist.
        deactivated=False,
        # In theory, is_web_public=True implies invite_only=False and
        # history_public_to_subscribers=True, but it's safer to include
        # these in the query.
        invite_only=False,
        history_public_to_subscribers=True,
    ).select_related("can_send_message_group", "can_send_message_group__named_user_group")


def check_stream_name_available(realm: Realm, name: str) -> None:
    check_stream_name(name)
    try:
        get_stream(name, realm)
        raise JsonableError(_("Channel name already in use."))
    except Stream.DoesNotExist:
        pass


def access_stream_by_name(
    user_profile: UserProfile, stream_name: str, allow_realm_admin: bool = False
) -> tuple[Stream, Subscription | None]:
    error = _("Invalid channel name '{channel_name}'").format(channel_name=stream_name)
    try:
        stream = get_realm_stream(stream_name, user_profile.realm_id)
    except Stream.DoesNotExist:
        raise JsonableError(error)

    sub = access_stream_common(
        user_profile,
        stream,
        error,
        allow_realm_admin=allow_realm_admin,
    )
    return (stream, sub)


def access_web_public_stream(stream_id: int, realm: Realm) -> Stream:
    error = _("Invalid channel ID")
    try:
        stream = get_stream_by_id_in_realm(stream_id, realm)
    except Stream.DoesNotExist:
        raise JsonableError(error)

    if not stream.is_web_public:
        raise JsonableError(error)
    return stream


def access_stream_to_remove_visibility_policy_by_name(
    user_profile: UserProfile, stream_name: str, error: str
) -> Stream:
    """
    It may seem a little silly to have this helper function for unmuting
    topics, but it gets around a linter warning, and it helps to be able
    to review all security-related stuff in one place.

    Our policy for accessing streams when you unmute a topic is that you
    don't necessarily need to have an active subscription or even "legal"
    access to the stream.  Instead, we just verify the stream_id has been
    muted in the past (not here, but in the caller).

    Long term, we'll probably have folks just pass us in the id of the
    UserTopic row to unmute topics.
    """
    try:
        stream = get_stream(stream_name, user_profile.realm)
    except Stream.DoesNotExist:
        raise JsonableError(error)
    return stream


def access_stream_to_remove_visibility_policy_by_id(
    user_profile: UserProfile, stream_id: int, error: str
) -> Stream:
    try:
        stream = Stream.objects.get(id=stream_id, realm_id=user_profile.realm_id)
    except Stream.DoesNotExist:
        raise JsonableError(error)
    return stream


def private_stream_user_ids(stream_id: int) -> set[int]:
    subscriptions = get_active_subscriptions_for_stream_id(
        stream_id, include_deactivated_users=False
    )
    return {sub["user_profile_id"] for sub in subscriptions.values("user_profile_id")}


def public_stream_user_ids(stream: Stream) -> set[int]:
    guest_subscriptions = get_active_subscriptions_for_stream_id(
        stream.id, include_deactivated_users=False
    ).filter(user_profile__role=UserProfile.ROLE_GUEST)
    guest_subscriptions_ids = {
        sub["user_profile_id"] for sub in guest_subscriptions.values("user_profile_id")
    }
    return set(active_non_guest_user_ids(stream.realm_id)) | guest_subscriptions_ids


def can_access_stream_user_ids(stream: Stream) -> set[int]:
    # return user ids of users who can access the attributes of a
    # stream, such as its name/description.  Useful for sending events
    # to all users with access to a stream's attributes.
    if stream.is_public():
        # For a public stream, this is everyone in the realm
        # except unsubscribed guest users
        return public_stream_user_ids(stream)
    else:
        # for a private stream, it's subscribers plus realm admins.
        return private_stream_user_ids(stream.id) | {
            user.id for user in stream.realm.get_admin_users_and_bots()
        }


def can_access_stream_history(user_profile: UserProfile, stream: Stream) -> bool:
    """Determine whether the provided user is allowed to access the
    history of the target stream.

    This is used by the caller to determine whether this user can get
    historical messages before they joined for a narrowing search.

    Because of the way our search is currently structured,
    we may be passed an invalid stream here.  We return
    False in that situation, and subsequent code will do
    validation and raise the appropriate JsonableError.

    Note that this function should only be used in contexts where
    access_stream is being called elsewhere to confirm that the user
    can actually see this stream.
    """

    if user_profile.realm_id != stream.realm_id:
        raise AssertionError("user_profile and stream realms don't match")

    if stream.is_web_public:
        return True

    if stream.is_history_realm_public() and not user_profile.is_guest:
        return True

    if stream.is_history_public_to_subscribers():
        # In this case, we check if the user is subscribed.
        error = _("Invalid channel name '{channel_name}'").format(channel_name=stream.name)
        try:
            access_stream_common(user_profile, stream, error)
        except JsonableError:
            return False
        return True
    return False


def can_access_stream_history_by_name(user_profile: UserProfile, stream_name: str) -> bool:
    try:
        stream = get_stream(stream_name, user_profile.realm)
    except Stream.DoesNotExist:
        return False
    return can_access_stream_history(user_profile, stream)


def can_access_stream_history_by_id(user_profile: UserProfile, stream_id: int) -> bool:
    try:
        stream = get_stream_by_id_in_realm(stream_id, user_profile.realm)
    except Stream.DoesNotExist:
        return False
    return can_access_stream_history(user_profile, stream)


def can_remove_subscribers_from_stream(
    stream: Stream, user_profile: UserProfile, sub: Subscription | None
) -> bool:
    if not check_basic_stream_access(user_profile, stream, sub, allow_realm_admin=True):
        return False

    if user_profile.is_realm_admin:
        return True

    group_allowed_to_remove_subscribers = stream.can_remove_subscribers_group
    assert group_allowed_to_remove_subscribers is not None
    return user_has_permission_for_group_setting(
        group_allowed_to_remove_subscribers,
        user_profile,
        Stream.stream_permission_group_settings["can_remove_subscribers_group"],
    )


def can_administer_channel(channel: Stream, user_profile: UserProfile) -> bool:
    group_allowed_to_administer_channel = channel.can_administer_channel_group
    assert group_allowed_to_administer_channel is not None
    return user_has_permission_for_group_setting(
        group_allowed_to_administer_channel,
        user_profile,
        Stream.stream_permission_group_settings["can_administer_channel_group"],
    )


def filter_stream_authorization(
    user_profile: UserProfile, streams: Collection[Stream]
) -> tuple[list[Stream], list[Stream]]:
    recipient_ids = [stream.recipient_id for stream in streams]
    subscribed_recipient_ids = set(
        Subscription.objects.filter(
            user_profile=user_profile, recipient_id__in=recipient_ids, active=True
        ).values_list("recipient_id", flat=True)
    )

    unauthorized_streams: list[Stream] = []
    for stream in streams:
        # Deactivated streams are not accessible
        if stream.deactivated:
            unauthorized_streams.append(stream)
            continue

        # The user is authorized for their own streams
        if stream.recipient_id in subscribed_recipient_ids:
            continue

        # Web-public streams are accessible even to guests
        if stream.is_web_public:
            continue

        # Members and administrators are authorized for public streams
        if not stream.invite_only and not user_profile.is_guest:
            continue

        unauthorized_streams.append(stream)

    authorized_streams = [
        stream
        for stream in streams
        if stream.id not in {stream.id for stream in unauthorized_streams}
    ]
    return authorized_streams, unauthorized_streams


def list_to_streams(
    streams_raw: Collection[StreamDict],
    user_profile: UserProfile,
    autocreate: bool = False,
    unsubscribing_others: bool = False,
    is_default_stream: bool = False,
    setting_groups_dict: dict[int, int | AnonymousSettingGroupDict] | None = None,
) -> tuple[list[Stream], list[Stream]]:
    """Converts list of dicts to a list of Streams, validating input in the process

    For each stream name, we validate it to ensure it meets our
    requirements for a proper stream name using check_stream_name.

    This function in autocreate mode should be atomic: either an exception will be raised
    during a precheck, or all the streams specified will have been created if applicable.

    @param streams_raw The list of stream dictionaries to process;
      names should already be stripped of whitespace by the caller.
    @param user_profile The user for whom we are retrieving the streams
    @param autocreate Whether we should create streams if they don't already exist
    """
    # Validate all streams, getting extant ones, then get-or-creating the rest.

    stream_set = {stream_dict["name"] for stream_dict in streams_raw}

    for stream_name in stream_set:
        # Stream names should already have been stripped by the
        # caller, but it makes sense to verify anyway.
        assert stream_name == stream_name.strip()
        check_stream_name(stream_name)

    existing_streams: list[Stream] = []
    missing_stream_dicts: list[StreamDict] = []
    existing_stream_map = bulk_get_streams(user_profile.realm, stream_set)

    if unsubscribing_others:
        existing_recipient_ids = [stream.recipient_id for stream in existing_stream_map.values()]
        subs = Subscription.objects.filter(
            user_profile=user_profile, recipient_id__in=existing_recipient_ids, active=True
        )
        sub_map = {sub.recipient_id: sub for sub in subs}
        for stream in existing_stream_map.values():
            sub = sub_map.get(stream.recipient_id, None)
            if not can_remove_subscribers_from_stream(stream, user_profile, sub):
                raise JsonableError(_("Insufficient permission"))

    message_retention_days_not_none = False
    web_public_stream_requested = False
    for stream_dict in streams_raw:
        stream_name = stream_dict["name"]
        stream = existing_stream_map.get(stream_name.lower())
        if stream is None:
            if stream_dict.get("message_retention_days", None) is not None:
                message_retention_days_not_none = True
            missing_stream_dicts.append(stream_dict)

            if autocreate and stream_dict["is_web_public"]:
                web_public_stream_requested = True
        else:
            existing_streams.append(stream)

    if len(missing_stream_dicts) == 0:
        # This is the happy path for callers who expected all of these
        # streams to exist already.
        created_streams: list[Stream] = []
    else:
        # autocreate=True path starts here
        for stream_dict in missing_stream_dicts:
            invite_only = stream_dict.get("invite_only", False)
            if invite_only and not user_profile.can_create_private_streams():
                raise JsonableError(_("Insufficient permission"))
            if not invite_only and not user_profile.can_create_public_streams():
                raise JsonableError(_("Insufficient permission"))
            if is_default_stream and not user_profile.is_realm_admin:
                raise JsonableError(_("Insufficient permission"))
            if invite_only and is_default_stream:
                raise JsonableError(_("A default channel cannot be private."))

        if not autocreate:
            raise JsonableError(
                _("Channel(s) ({channel_names}) do not exist").format(
                    channel_names=", ".join(
                        stream_dict["name"] for stream_dict in missing_stream_dicts
                    ),
                )
            )

        if web_public_stream_requested:
            if not user_profile.realm.web_public_streams_enabled():
                raise JsonableError(_("Web-public channels are not enabled."))
            if not user_profile.can_create_web_public_streams():
                # We set can_create_web_public_channel_group to allow only organization
                # owners to create web-public streams, because of their sensitive nature.
                raise JsonableError(_("Insufficient permission"))

        if message_retention_days_not_none:
            if not user_profile.is_realm_owner:
                raise OrganizationOwnerRequiredError

            user_profile.realm.ensure_not_on_limited_plan()

        # We already filtered out existing streams, so dup_streams
        # will normally be an empty list below, but we protect against somebody
        # else racing to create the same stream.  (This is not an entirely
        # paranoid approach, since often on Zulip two people will discuss
        # creating a new stream, and both people eagerly do it.)
        created_streams, dup_streams = create_streams_if_needed(
            realm=user_profile.realm,
            stream_dicts=missing_stream_dicts,
            acting_user=user_profile,
            setting_groups_dict=setting_groups_dict,
        )
        existing_streams += dup_streams

    return existing_streams, created_streams


def access_default_stream_group_by_id(realm: Realm, group_id: int) -> DefaultStreamGroup:
    try:
        return DefaultStreamGroup.objects.get(realm=realm, id=group_id)
    except DefaultStreamGroup.DoesNotExist:
        raise JsonableError(
            _("Default channel group with id '{group_id}' does not exist.").format(
                group_id=group_id
            )
        )


def get_stream_by_narrow_operand_access_unchecked(operand: str | int, realm: Realm) -> Stream:
    """This is required over access_stream_* in certain cases where
    we need the stream data only to prepare a response that user can access
    and not send it out to unauthorized recipients.
    """
    if isinstance(operand, str):
        return get_stream(operand, realm)
    return get_stream_by_id_in_realm(operand, realm)


def ensure_stream(
    realm: Realm,
    stream_name: str,
    invite_only: bool = False,
    stream_description: str = "",
    *,
    acting_user: UserProfile | None,
) -> Stream:
    return create_stream_if_needed(
        realm,
        stream_name,
        invite_only=invite_only,
        stream_description=stream_description,
        acting_user=acting_user,
    )[0]


def get_occupied_streams(realm: Realm) -> QuerySet[Stream]:
    """Get streams with subscribers"""
    exists_expression = Exists(
        Subscription.objects.filter(
            active=True,
            is_user_active=True,
            user_profile__realm=realm,
            recipient_id=OuterRef("recipient_id"),
        ),
    )
    occupied_streams = (
        Stream.objects.filter(realm=realm, deactivated=False)
        .alias(occupied=exists_expression)
        .filter(occupied=True)
    )
    return occupied_streams


def get_stream_post_policy_value_based_on_group_setting(setting_group: UserGroup) -> int:
    if (
        hasattr(setting_group, "named_user_group")
        and setting_group.named_user_group.is_system_group
    ):
        group_name = setting_group.named_user_group.name
        if group_name in Stream.SYSTEM_GROUPS_ENUM_MAP:
            return Stream.SYSTEM_GROUPS_ENUM_MAP[group_name]

    return Stream.STREAM_POST_POLICY_EVERYONE


def stream_to_dict(
    stream: Stream,
    recent_traffic: dict[int, int] | None = None,
    setting_groups_dict: dict[int, int | AnonymousSettingGroupDict] | None = None,
) -> APIStreamDict:
    if recent_traffic is not None:
        stream_weekly_traffic = get_average_weekly_stream_traffic(
            stream.id, stream.date_created, recent_traffic
        )
    else:
        # We cannot compute the traffic data for a newly created
        # stream, so we set "stream_weekly_traffic" field to
        # "None" for the stream object in creation event.
        # Also, there are some cases where we do not need to send
        # the traffic data, like when deactivating a stream, and
        # passing stream data to spectators.
        stream_weekly_traffic = None

    if setting_groups_dict is not None:
        can_administer_channel_group = setting_groups_dict[stream.can_administer_channel_group_id]
        can_send_message_group = setting_groups_dict[stream.can_send_message_group_id]
        can_remove_subscribers_group = setting_groups_dict[stream.can_remove_subscribers_group_id]
    else:
        can_administer_channel_group = get_group_setting_value_for_api(
            stream.can_administer_channel_group
        )
        can_send_message_group = get_group_setting_value_for_api(stream.can_send_message_group)
        can_remove_subscribers_group = get_group_setting_value_for_api(
            stream.can_remove_subscribers_group
        )

    stream_post_policy = get_stream_post_policy_value_based_on_group_setting(
        stream.can_send_message_group
    )

    return APIStreamDict(
        is_archived=stream.deactivated,
        can_administer_channel_group=can_administer_channel_group,
        can_send_message_group=can_send_message_group,
        can_remove_subscribers_group=can_remove_subscribers_group,
        creator_id=stream.creator_id,
        date_created=datetime_to_timestamp(stream.date_created),
        description=stream.description,
        first_message_id=stream.first_message_id,
        is_recently_active=stream.is_recently_active,
        history_public_to_subscribers=stream.history_public_to_subscribers,
        invite_only=stream.invite_only,
        is_web_public=stream.is_web_public,
        message_retention_days=stream.message_retention_days,
        name=stream.name,
        rendered_description=stream.rendered_description,
        stream_id=stream.id,
        stream_post_policy=stream_post_policy,
        is_announcement_only=stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS,
        stream_weekly_traffic=stream_weekly_traffic,
    )


def get_web_public_streams(realm: Realm) -> list[APIStreamDict]:  # nocoverage
    query = get_web_public_streams_queryset(realm)
    streams = query.only(*Stream.API_FIELDS)
    setting_groups_dict = get_group_setting_value_dict_for_streams(list(streams))
    stream_dicts = [stream_to_dict(stream, None, setting_groups_dict) for stream in streams]
    return stream_dicts


def get_streams_for_user(
    user_profile: UserProfile,
    include_public: bool = True,
    include_web_public: bool = False,
    include_subscribed: bool = True,
    exclude_archived: bool = True,
    include_all_active: bool = False,
    include_owner_subscribed: bool = False,
) -> list[Stream]:
    if include_all_active and not user_profile.is_realm_admin:
        raise JsonableError(_("User not authorized for this query"))

    include_public = include_public and user_profile.can_access_public_streams()

    # Start out with all streams in the realm.
    query = Stream.objects.select_related(
        "can_send_message_group", "can_send_message_group__named_user_group"
    ).filter(realm=user_profile.realm)

    if exclude_archived:
        query = query.filter(deactivated=False)

    if include_all_active:
        streams = query.only(
            *Stream.API_FIELDS, "can_send_message_group", "can_send_message_group__named_user_group"
        )
    else:
        # We construct a query as the or (|) of the various sources
        # this user requested streams from.
        query_filter: Q | None = None

        def add_filter_option(option: Q) -> None:
            nonlocal query_filter
            if query_filter is None:
                query_filter = option
            else:
                query_filter |= option

        if include_subscribed:
            subscribed_stream_ids = get_subscribed_stream_ids_for_user(user_profile)
            recipient_check = Q(id__in=set(subscribed_stream_ids))
            add_filter_option(recipient_check)
        if include_public:
            invite_only_check = Q(invite_only=False)
            add_filter_option(invite_only_check)
        if include_web_public:
            # This should match get_web_public_streams_queryset
            web_public_check = Q(
                is_web_public=True,
                invite_only=False,
                history_public_to_subscribers=True,
                deactivated=False,
            )
            add_filter_option(web_public_check)
        if include_owner_subscribed and user_profile.is_bot:
            bot_owner = user_profile.bot_owner
            assert bot_owner is not None
            owner_stream_ids = get_subscribed_stream_ids_for_user(bot_owner)
            owner_subscribed_check = Q(id__in=set(owner_stream_ids))
            add_filter_option(owner_subscribed_check)

        if query_filter is not None:
            query = query.filter(query_filter)
            streams = query.only(*Stream.API_FIELDS)
        else:
            # Don't bother going to the database with no valid sources
            return []

    return list(streams)


def get_group_setting_value_dict_for_streams(
    streams: list[Stream],
) -> dict[int, int | AnonymousSettingGroupDict]:
    setting_group_ids = set()
    for stream in streams:
        for setting_name in Stream.stream_permission_group_settings:
            setting_group_ids.add(getattr(stream, setting_name + "_id"))

    return get_setting_values_for_group_settings(list(setting_group_ids))


def get_setting_values_for_group_settings(
    group_ids: list[int],
) -> dict[int, int | AnonymousSettingGroupDict]:
    user_groups = UserGroup.objects.filter(id__in=group_ids).select_related("named_user_group")

    setting_groups_dict: dict[int, int | AnonymousSettingGroupDict] = dict()
    anonymous_group_ids = []
    for group in user_groups:
        if hasattr(group, "named_user_group"):
            setting_groups_dict[group.id] = group.id
        else:
            anonymous_group_ids.append(group.id)

    if len(anonymous_group_ids) == 0:
        return setting_groups_dict

    user_members = (
        UserGroupMembership.objects.filter(user_group_id__in=anonymous_group_ids)
        .annotate(
            member_type=Value("user"),
        )
        .values_list("member_type", "user_group_id", "user_profile_id")
    )

    group_subgroups = (
        GroupGroupMembership.objects.filter(supergroup_id__in=anonymous_group_ids)
        .annotate(
            member_type=Value("group"),
        )
        .values_list("member_type", "supergroup_id", "subgroup_id")
    )

    all_members = user_members.union(group_subgroups)
    for member_type, group_id, member_id in all_members:
        if group_id not in setting_groups_dict:
            setting_groups_dict[group_id] = AnonymousSettingGroupDict(
                direct_members=[],
                direct_subgroups=[],
            )

        anonymous_group_dict = setting_groups_dict[group_id]
        assert isinstance(anonymous_group_dict, AnonymousSettingGroupDict)
        if member_type == "user":
            anonymous_group_dict.direct_members.append(member_id)
        else:
            anonymous_group_dict.direct_subgroups.append(member_id)

    return setting_groups_dict


def do_get_streams(
    user_profile: UserProfile,
    include_public: bool = True,
    include_web_public: bool = False,
    include_subscribed: bool = True,
    exclude_archived: bool = True,
    include_all_active: bool = False,
    include_default: bool = False,
    include_owner_subscribed: bool = False,
) -> list[APIStreamDict]:
    # This function is only used by API clients now.

    streams = get_streams_for_user(
        user_profile,
        include_public,
        include_web_public,
        include_subscribed,
        exclude_archived,
        include_all_active,
        include_owner_subscribed,
    )

    stream_ids = {stream.id for stream in streams}
    recent_traffic = get_streams_traffic(stream_ids, user_profile.realm)

    setting_groups_dict = get_group_setting_value_dict_for_streams(streams)

    stream_dicts = sorted(
        (stream_to_dict(stream, recent_traffic, setting_groups_dict) for stream in streams),
        key=lambda elt: elt["name"],
    )

    if include_default:
        default_stream_ids = get_default_stream_ids_for_realm(user_profile.realm_id)
        for stream_dict in stream_dicts:
            stream_dict["is_default"] = stream_dict["stream_id"] in default_stream_ids

    return stream_dicts


def get_subscribed_private_streams_for_user(user_profile: UserProfile) -> QuerySet[Stream]:
    exists_expression = Exists(
        Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            is_user_active=True,
            recipient_id=OuterRef("recipient_id"),
        ),
    )
    subscribed_private_streams = (
        Stream.objects.filter(realm=user_profile.realm, invite_only=True, deactivated=False)
        .alias(subscribed=exists_expression)
        .filter(subscribed=True)
    )
    return subscribed_private_streams


@transaction.atomic(durable=True)
def update_stream_active_status_for_realm(realm: Realm, date_days_ago: datetime) -> int:
    recent_messages_subquery = Message.objects.filter(
        date_sent__gte=date_days_ago,
        realm=realm,
        recipient__type=Recipient.STREAM,
        recipient__type_id=OuterRef("id"),
    )
    streams_to_mark_inactive = Stream.objects.filter(
        ~Exists(recent_messages_subquery), is_recently_active=True, realm=realm
    )

    # Send events to notify the users about the change in the stream's active status.
    for stream in streams_to_mark_inactive:
        event = dict(
            type="stream",
            op="update",
            property="is_recently_active",
            value=False,
            stream_id=stream.id,
            name=stream.name,
        )
        send_event_on_commit(stream.realm, event, active_user_ids(stream.realm_id))

    count = streams_to_mark_inactive.update(is_recently_active=False)
    return count


def check_update_all_streams_active_status(
    days: int = Stream.LAST_ACTIVITY_DAYS_BEFORE_FOR_ACTIVE,
) -> int:
    date_days_ago = timezone_now() - timedelta(days=days)
    count = 0
    for realm in Realm.objects.filter(deactivated=False):
        count += update_stream_active_status_for_realm(realm, date_days_ago)
    return count

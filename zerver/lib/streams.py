from collections import defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, TypedDict

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.default_streams import get_default_stream_ids_for_realm
from zerver.lib.exceptions import (
    CannotAdministerChannelError,
    CannotSetTopicsPolicyError,
    ChannelExistsError,
    IncompatibleParametersError,
    JsonableError,
    OrganizationOwnerRequiredError,
)
from zerver.lib.stream_subscription import (
    get_guest_user_ids_for_streams,
    get_subscribed_stream_ids_for_user,
    get_user_ids_for_streams,
)
from zerver.lib.stream_traffic import get_average_weekly_stream_traffic, get_streams_traffic
from zerver.lib.string_validation import check_stream_name
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import get_topic_display_name, messages_for_topic
from zerver.lib.types import APIStreamDict, UserGroupMembersData
from zerver.lib.user_groups import (
    UserGroupMembershipDetails,
    access_user_group_for_setting,
    get_group_setting_value_for_register_api,
    get_members_and_subgroups_of_groups,
    get_recursive_membership_groups,
    get_role_based_system_groups_dict,
    get_root_id_annotated_recursive_subgroups_for_groups,
    parse_group_setting_value,
    user_has_permission_for_group_setting,
)
from zerver.models import (
    ChannelFolder,
    DefaultStreamGroup,
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
    StreamTopicsPolicyEnum,
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
    topics_policy: int | None
    can_add_subscribers_group: UserGroup | None
    can_administer_channel_group: UserGroup | None
    can_create_topic_group: UserGroup | None
    can_delete_any_message_group: UserGroup | None
    can_delete_own_message_group: UserGroup | None
    can_move_messages_out_of_channel_group: UserGroup | None
    can_move_messages_within_channel_group: UserGroup | None
    can_send_message_group: UserGroup | None
    can_remove_subscribers_group: UserGroup | None
    can_resolve_topics_group: UserGroup | None
    can_subscribe_group: UserGroup | None
    folder: ChannelFolder | None


def get_stream_permission_policy_key(
    *,
    invite_only: bool | None = None,
    history_public_to_subscribers: bool | None = None,
    is_web_public: bool | None = None,
) -> str:
    policy_key = None
    for permission_key, permission_dict in Stream.PERMISSION_POLICIES.items():
        if (
            permission_dict["invite_only"] == invite_only
            and permission_dict["history_public_to_subscribers"] == history_public_to_subscribers
            and permission_dict["is_web_public"] == is_web_public
        ):
            policy_key = permission_key
            break

    assert policy_key is not None
    return policy_key


def get_stream_topics_policy(realm: Realm, stream: Stream) -> int:
    if stream.topics_policy == StreamTopicsPolicyEnum.inherit.value:
        return realm.topics_policy
    return stream.topics_policy


def validate_topics_policy(
    topics_policy: str | None,
    user_profile: UserProfile,
    # Pass None when creating a channel and the channel being edited when editing a channel's settings
    stream: Stream | None = None,
) -> StreamTopicsPolicyEnum | None:
    if topics_policy is not None and isinstance(topics_policy, StreamTopicsPolicyEnum):
        if (
            topics_policy != StreamTopicsPolicyEnum.inherit
            and not user_profile.can_set_topics_policy()
        ):
            raise JsonableError(_("Insufficient permission"))

        # Cannot set `topics_policy` to `empty_topic_only` when there are messages
        # in non-empty topics in the current channel.
        if (
            stream is not None
            and topics_policy == StreamTopicsPolicyEnum.empty_topic_only
            and channel_has_named_topics(stream)
        ):
            raise CannotSetTopicsPolicyError(
                get_topic_display_name("", user_profile.default_language)
            )
        return topics_policy
    return None


def validate_can_create_topic_group_setting_for_protected_history_streams(
    history_public_to_subscribers: bool | None,
    invite_only: bool,
    can_create_topic_group: int | UserGroupMembersData,
    system_groups_name_dict: dict[str, NamedUserGroup],
) -> None:
    if history_public_to_subscribers is None:
        history_public_to_subscribers = get_default_value_for_history_public_to_subscribers(
            invite_only, history_public_to_subscribers
        )

    if history_public_to_subscribers:
        return

    # If a group setting has value "Everyone including guests" along with additional
    # users or groups, we do not treat it as equivalent to just "Everyone including guests".
    # For a channel with protected history, everyone must be allowed to create new topics.
    # As a result, enabling protected history for a channel requires the `can_create_topic_group`
    # setting to have "Everyone including guests" group configuration only.
    if (
        not isinstance(can_create_topic_group, int)
        or can_create_topic_group != system_groups_name_dict[SystemGroups.EVERYONE].id
    ):
        raise IncompatibleParametersError(
            ["history_public_to_subscribers", "can_create_topic_group"]
        )


def get_default_value_for_history_public_to_subscribers(
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

    return history_public_to_subscribers


def render_stream_description(
    text: str, realm: Realm, *, acting_user: UserProfile | None = None
) -> str:
    from zerver.lib.markdown import markdown_convert

    return markdown_convert(
        text, message_realm=realm, no_previews=True, acting_user=acting_user
    ).rendered_content


def send_stream_creation_event(
    realm: Realm,
    stream: Stream,
    user_ids: list[int],
    recent_traffic: dict[int, int] | None = None,
    anonymous_group_membership: dict[int, UserGroupMembersData] | None = None,
    for_unarchiving: bool = False,
) -> None:
    event = dict(
        type="stream",
        op="create",
        streams=[stream_to_dict(stream, recent_traffic, anonymous_group_membership)],
        for_unarchiving=for_unarchiving,
    )
    send_event_on_commit(realm, event, user_ids)


def check_channel_creation_permissions(
    user_profile: UserProfile,
    *,
    is_default_stream: bool,
    invite_only: bool,
    is_web_public: bool,
    message_retention_days: str | int | None,
) -> None:
    if invite_only and not user_profile.can_create_private_streams():
        raise JsonableError(_("Insufficient permission"))
    if not invite_only and not user_profile.can_create_public_streams():
        raise JsonableError(_("Insufficient permission"))
    if is_default_stream and not user_profile.is_realm_admin:
        raise JsonableError(_("Insufficient permission"))
    if invite_only and is_default_stream:
        raise JsonableError(_("A default channel cannot be private."))
    if is_web_public:
        if not user_profile.realm.web_public_streams_enabled():
            raise JsonableError(_("Web-public channels are not enabled."))
        if not user_profile.can_create_web_public_streams():
            # We set can_create_web_public_channel_group to allow only organization
            # owners to create web-public streams, because of their sensitive nature.
            raise JsonableError(_("Insufficient permission"))
    if message_retention_days is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError
        user_profile.realm.ensure_not_on_limited_plan()


def get_stream_permission_default_group(
    setting_name: str,
    system_groups_name_dict: dict[str, NamedUserGroup],
    creator: UserProfile | None = None,
) -> UserGroup:
    setting_default_name = Stream.stream_permission_group_settings[setting_name].default_group_name
    if setting_default_name == "channel_creator":
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


def get_users_dict_with_metadata_access_to_streams_via_permission_groups(
    streams: list[Stream],
    realm_id: int,
) -> dict[int, set[int]]:
    can_administer_group_ids = {stream.can_administer_channel_group_id for stream in streams}
    can_add_subscriber_group_ids = {stream.can_add_subscribers_group_id for stream in streams}
    can_subscribe_group_ids = {stream.can_subscribe_group_id for stream in streams}

    all_permission_group_ids = list(
        can_administer_group_ids | can_add_subscriber_group_ids | can_subscribe_group_ids
    )

    recursive_subgroups = get_root_id_annotated_recursive_subgroups_for_groups(
        all_permission_group_ids, realm_id
    )
    subgroup_root_id_dict = {}
    all_subgroup_ids = set()
    for group in recursive_subgroups:
        subgroup_root_id_dict[group.id] = group.root_id  # type: ignore[attr-defined]  # root_id is an annotated field.
        all_subgroup_ids.add(group.id)

    group_members = (
        UserGroupMembership.objects.filter(
            user_group_id__in=list(all_subgroup_ids), user_profile__is_active=True
        )
        .exclude(
            # allow_everyone_group=False is false for both
            # can_add_subscribers_group and
            # can_administer_channel_group, so guest users cannot
            # exercise these permission to get metadata access.
            user_profile__role=UserProfile.ROLE_GUEST
        )
        .values_list("user_group_id", "user_profile_id")
    )
    group_members_dict = defaultdict(set)
    for user_group_id, user_profile_id in group_members:
        root_id = subgroup_root_id_dict[user_group_id]
        group_members_dict[root_id].add(user_profile_id)

    users_with_metadata_access_dict = defaultdict(set)
    for stream in streams:
        users_with_metadata_access_dict[stream.id] = (
            group_members_dict[stream.can_administer_channel_group_id]
            | group_members_dict[stream.can_add_subscribers_group_id]
            | group_members_dict[stream.can_subscribe_group_id]
        )

    return users_with_metadata_access_dict


def get_user_ids_with_metadata_access_via_permission_groups(stream: Stream) -> set[int]:
    users_with_metadata_access_dict = (
        get_users_dict_with_metadata_access_to_streams_via_permission_groups(
            [stream], stream.realm_id
        )
    )
    return users_with_metadata_access_dict[stream.id]


def channel_events_topic_name(stream: Stream) -> str:
    if stream.topics_policy == StreamTopicsPolicyEnum.empty_topic_only.value:
        return ""
    return str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME)


def channel_has_named_topics(stream: Stream) -> bool:
    return (
        Message.objects.filter(realm_id=stream.realm_id, recipient=stream.recipient)
        .exclude(subject="")
        .exists()
    )


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
    topics_policy: int | None = None,
    can_add_subscribers_group: UserGroup | None = None,
    can_administer_channel_group: UserGroup | None = None,
    can_create_topic_group: UserGroup | None = None,
    can_delete_any_message_group: UserGroup | None = None,
    can_delete_own_message_group: UserGroup | None = None,
    can_move_messages_out_of_channel_group: UserGroup | None = None,
    can_move_messages_within_channel_group: UserGroup | None = None,
    can_send_message_group: UserGroup | None = None,
    can_remove_subscribers_group: UserGroup | None = None,
    can_resolve_topics_group: UserGroup | None = None,
    can_subscribe_group: UserGroup | None = None,
    folder: ChannelFolder | None = None,
    acting_user: UserProfile | None = None,
    anonymous_group_membership: dict[int, UserGroupMembersData] | None = None,
) -> tuple[Stream, bool]:
    history_public_to_subscribers = get_default_value_for_history_public_to_subscribers(
        invite_only, history_public_to_subscribers
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

    if topics_policy is None:
        topics_policy = StreamTopicsPolicyEnum.inherit.value

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
            message_retention_days=message_retention_days,
            folder=folder,
            topics_policy=topics_policy,
            **group_setting_values,
        ),
    )

    if created:
        recipient = Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)

        stream.recipient = recipient
        stream.rendered_description = render_stream_description(
            stream_description, realm, acting_user=acting_user
        )
        stream.save(update_fields=["recipient", "rendered_description"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=AuditLogEventType.CHANNEL_CREATED,
            event_time=event_time,
        )

        if anonymous_group_membership is None:
            anonymous_group_membership = get_anonymous_group_membership_dict_for_streams([stream])

        if stream.is_public():
            if stream.is_web_public:
                notify_user_ids = active_user_ids(stream.realm_id)
            else:
                # TODO: This should include guests with metadata
                # access to the channel, once that is possible via
                # can_join_group.
                notify_user_ids = active_non_guest_user_ids(stream.realm_id)
            send_stream_creation_event(
                realm,
                stream,
                notify_user_ids,
                anonymous_group_membership=anonymous_group_membership,
            )
        else:
            realm_admin_ids = {user.id for user in stream.realm.get_admin_users_and_bots()}
            send_stream_creation_event(
                realm,
                stream,
                list(
                    realm_admin_ids
                    | get_user_ids_with_metadata_access_via_permission_groups(stream)
                ),
                anonymous_group_membership=anonymous_group_membership,
            )

    return stream, created


def create_streams_if_needed(
    realm: Realm,
    stream_dicts: list[StreamDict],
    acting_user: UserProfile | None = None,
    anonymous_group_membership: dict[int, UserGroupMembersData] | None = None,
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
            topics_policy=stream_dict.get("topics_policy", None),
            can_add_subscribers_group=stream_dict.get("can_add_subscribers_group", None),
            can_administer_channel_group=stream_dict.get("can_administer_channel_group", None),
            can_create_topic_group=stream_dict.get("can_create_topic_group", None),
            can_delete_any_message_group=stream_dict.get("can_delete_any_message_group", None),
            can_delete_own_message_group=stream_dict.get("can_delete_own_message_group", None),
            can_move_messages_out_of_channel_group=stream_dict.get(
                "can_move_messages_out_of_channel_group", None
            ),
            can_move_messages_within_channel_group=stream_dict.get(
                "can_move_messages_within_channel_group", None
            ),
            can_send_message_group=stream_dict.get("can_send_message_group", None),
            can_remove_subscribers_group=stream_dict.get("can_remove_subscribers_group", None),
            can_resolve_topics_group=stream_dict.get("can_resolve_topics_group", None),
            can_subscribe_group=stream_dict.get("can_subscribe_group", None),
            folder=stream_dict.get("folder", None),
            acting_user=acting_user,
            anonymous_group_membership=anonymous_group_membership,
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


def is_user_in_can_administer_channel_group(
    stream: Stream, user_recursive_group_ids: set[int]
) -> bool:
    # Important: The caller must have verified the acting user is not
    # a guest, to enforce that can_administer_channel_group has
    # allow_everyone_group=False.
    group_allowed_to_administer_channel_id = stream.can_administer_channel_group_id
    assert group_allowed_to_administer_channel_id is not None
    return group_allowed_to_administer_channel_id in user_recursive_group_ids


def is_user_in_can_add_subscribers_group(
    stream: Stream, user_recursive_group_ids: set[int]
) -> bool:
    # Important: The caller must have verified the acting user is not
    # a guest, to enforce that can_add_subscribers_group has
    # allow_everyone_group=False.
    group_allowed_to_add_subscribers_id = stream.can_add_subscribers_group_id
    assert group_allowed_to_add_subscribers_id is not None
    return group_allowed_to_add_subscribers_id in user_recursive_group_ids


def is_user_in_can_subscribe_group(stream: Stream, user_recursive_group_ids: set[int]) -> bool:
    # Important: The caller must have verified the acting user
    # is not a guest, to enforce that can_subscribe_group has
    # allow_everyone_group=False.
    group_allowed_to_subscribe_id = stream.can_subscribe_group_id
    return group_allowed_to_subscribe_id in user_recursive_group_ids


def is_user_in_groups_granting_content_access(
    stream: Stream, user_recursive_group_ids: set[int]
) -> bool:
    # Important: The caller must have verified the acting user is not
    # a guest, to enforce that can_add_subscribers_group has
    # allow_everyone_group=False.
    return is_user_in_can_subscribe_group(
        stream, user_recursive_group_ids
    ) or is_user_in_can_add_subscribers_group(stream, user_recursive_group_ids)


def is_user_in_can_remove_subscribers_group(
    stream: Stream, user_recursive_group_ids: set[int]
) -> bool:
    # Important: The caller must have verified the acting user is not
    # a guest, to enforce that can_remove_subscribers_group has
    # allow_everyone_group=False.
    group_allowed_to_remove_subscribers_id = stream.can_remove_subscribers_group_id
    assert group_allowed_to_remove_subscribers_id is not None
    return group_allowed_to_remove_subscribers_id in user_recursive_group_ids


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
        stream.can_send_message_group_id,
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

    # You cannot send mesasges to archived channels
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

    user_recursive_group_ids = set(
        get_recursive_membership_groups(sender).values_list("id", flat=True)
    )

    if (
        stream.history_public_to_subscribers
        and is_user_in_groups_granting_content_access(stream, user_recursive_group_ids)
        and not sender.is_guest
    ):
        return

    # All other cases are an error.
    raise JsonableError(
        _("Not authorized to send to channel '{channel_name}'").format(channel_name=stream.name)
    )


def check_user_can_create_new_topics(user_profile: UserProfile, stream: Stream) -> None:
    can_create_topic_group = stream.can_create_topic_group
    if (
        hasattr(can_create_topic_group, "named_user_group")
        and can_create_topic_group.named_user_group.name == SystemGroups.NOBODY
    ):
        raise JsonableError(_("You do not have permission to create new topics in this channel."))

    if not user_has_permission_for_group_setting(
        stream.can_create_topic_group_id,
        user_profile,
        Stream.stream_permission_group_settings["can_create_topic_group"],
        direct_member_only=False,
    ):
        raise JsonableError(_("You do not have permission to create new topics in this channel."))


def check_for_can_create_topic_group_violation(
    user_profile: UserProfile, stream: Stream, topic_name: str
) -> None:
    if is_cross_realm_bot_email(user_profile.delivery_email):
        return

    can_create_topic_group = stream.can_create_topic_group
    if (
        hasattr(can_create_topic_group, "named_user_group")
        and can_create_topic_group.named_user_group.name == SystemGroups.EVERYONE
    ):
        return

    assert stream.recipient_id is not None
    topic_exists = messages_for_topic(
        realm_id=stream.realm_id, stream_recipient_id=stream.recipient_id, topic_name=topic_name
    ).exists()

    if not topic_exists:
        try:
            check_user_can_create_new_topics(user_profile, stream)
        except JsonableError as e:
            if user_profile.is_bot and user_profile.bot_owner is not None:
                check_user_can_create_new_topics(user_profile.bot_owner, stream)
            else:
                raise JsonableError(e.msg)


def check_for_exactly_one_stream_arg(stream_id: int | None, stream: str | None) -> None:
    if stream_id is None and stream is None:
        # Uses the same translated string as RequestVariableMissingError
        # with the stream_id parameter, which is the more common use case.
        error = _("Missing '{var_name}' argument").format(var_name="stream_id")
        raise JsonableError(error)

    if stream_id is not None and stream is not None:
        raise IncompatibleParametersError(["stream_id", "stream"])


def user_has_metadata_access(
    user_profile: UserProfile,
    stream: Stream,
    user_group_membership_details: UserGroupMembershipDetails,
    *,
    is_subscribed: bool,
) -> bool:
    if stream.is_web_public:
        return True

    if is_subscribed:
        return True

    if user_profile.is_guest:
        return False

    if stream.is_public():
        return True

    if user_profile.is_realm_admin:
        return True

    if user_group_membership_details.user_recursive_group_ids is None:
        user_group_membership_details.user_recursive_group_ids = set(
            get_recursive_membership_groups(user_profile).values_list("id", flat=True)
        )

    if has_metadata_access_to_channel_via_groups(
        user_profile,
        user_group_membership_details.user_recursive_group_ids,
        stream.can_administer_channel_group_id,
        stream.can_add_subscribers_group_id,
        stream.can_subscribe_group_id,
    ):
        return True

    return False


def user_has_content_access(
    user_profile: UserProfile,
    stream: Stream,
    user_group_membership_details: UserGroupMembershipDetails,
    *,
    is_subscribed: bool,
) -> bool:
    if stream.is_web_public:
        return True

    if is_subscribed:
        return True

    if user_profile.is_guest:
        return False

    if stream.is_public():
        return True

    if user_group_membership_details.user_recursive_group_ids is None:
        user_group_membership_details.user_recursive_group_ids = set(
            get_recursive_membership_groups(user_profile).values_list("id", flat=True)
        )

    # This check must be after the user_profile.is_guest check, since
    # allow_everyone_group=False for can_add_subscribers_group and
    # can_subscribe_group.
    if is_user_in_groups_granting_content_access(
        stream, user_group_membership_details.user_recursive_group_ids
    ):
        return True

    return False


def check_stream_access_for_delete_or_update_requiring_metadata_access(
    user_profile: UserProfile, stream: Stream, sub: Subscription | None = None
) -> None:
    error = _("Invalid channel ID")
    if stream.realm_id != user_profile.realm_id:
        raise JsonableError(error)

    # Optimization for the organization administrator code path. We
    # don't explicitly grant realm admins this permission, but admins
    # implicitly have the can_administer_channel_group permission for
    # all accessible channels.
    if user_profile.is_realm_admin:
        return

    if can_administer_accessible_channel(stream, user_profile):
        return

    # We only want to reveal that user is not an administrator
    # if the user has access to the channel in the first place.
    # Ideally, we would be checking if user has metadata access
    # to the channel for this block, but since we have ruled out
    # the possibility that the user is a channel admin, checking
    # for content access will save us valuable DB queries.
    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    if user_has_content_access(
        user_profile, stream, user_group_membership_details, is_subscribed=sub is not None
    ):
        raise CannotAdministerChannelError

    raise JsonableError(error)


def access_stream_for_delete_or_update_requiring_metadata_access(
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

    check_stream_access_for_delete_or_update_requiring_metadata_access(user_profile, stream, sub)
    return (stream, sub)


def has_metadata_access_to_channel_via_groups(
    user_profile: UserProfile,
    user_recursive_group_ids: set[int],
    can_administer_channel_group_id: int,
    can_add_subscribers_group_id: int,
    can_subscribe_group_id: int,
) -> bool:
    for setting_name in Stream.stream_permission_group_settings_granting_metadata_access:
        permission_configuration = Stream.stream_permission_group_settings[setting_name]
        if not permission_configuration.allow_everyone_group and user_profile.is_guest:
            return False

    # It's best to just check the variables directly here since it
    # becomes complicated to create an automated loop for both settings
    # and values because of https://github.com/python/mypy/issues/5382.
    return (
        can_administer_channel_group_id in user_recursive_group_ids
        or can_add_subscribers_group_id in user_recursive_group_ids
        or can_subscribe_group_id in user_recursive_group_ids
    )


def check_basic_stream_access(
    user_profile: UserProfile,
    stream: Stream,
    *,
    is_subscribed: bool,
    require_content_access: bool = True,
) -> bool:
    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    if user_has_content_access(
        user_profile, stream, user_group_membership_details, is_subscribed=is_subscribed
    ):
        return True

    if not require_content_access:
        if user_profile.is_realm_admin:
            return True

        # This will not get fired in practice since we will only arrive
        # at this if block if `user_has_content_access` returns False.
        # In every case that `user_has_content_access` returns False,
        # we already would have calculated `user_recursive_group_ids`.
        # It is still good to keep this around in case there are
        # changes in that function.
        if user_group_membership_details.user_recursive_group_ids is None:  # nocoverage
            user_group_membership_details.user_recursive_group_ids = set(  # nocoverage
                get_recursive_membership_groups(user_profile).values_list(
                    "id", flat=True
                )  # nocoverage
            )  # nocoverage
        if has_metadata_access_to_channel_via_groups(
            user_profile,
            user_group_membership_details.user_recursive_group_ids,
            stream.can_administer_channel_group_id,
            stream.can_add_subscribers_group_id,
            stream.can_subscribe_group_id,
        ):
            return True

    return False


# Only set require_content_access flag to False when you want
# to allow users with metadata access to access unsubscribed private
# stream content.
def access_stream_common(
    user_profile: UserProfile,
    stream: Stream,
    error: str,
    *,
    require_active_channel: bool = True,
    require_content_access: bool = True,
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
            user_profile=user_profile, recipient_id=stream.recipient_id, active=True
        )
    except Subscription.DoesNotExist:
        sub = None

    if require_active_channel and stream.deactivated:
        raise JsonableError(error)

    if check_basic_stream_access(
        user_profile,
        stream,
        is_subscribed=sub is not None,
        require_content_access=require_content_access,
    ):
        return sub

    # Otherwise it is a private stream and you're not on it, so throw
    # an error.
    raise JsonableError(error)


def access_stream_by_id(
    user_profile: UserProfile,
    stream_id: int,
    *,
    require_active_channel: bool = True,
    require_content_access: bool = True,
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
        require_active_channel=require_active_channel,
        require_content_access=require_content_access,
    )
    return (stream, sub)


def access_stream_by_id_for_message(
    user_profile: UserProfile,
    stream_id: int,
    *,
    require_active_channel: bool = True,
    require_content_access: bool = True,
) -> tuple[Stream, Subscription | None]:
    """
    Variant of access_stream_by_id that uses get_stream_by_id_for_sending_message
    to ensure we do a select_related("can_send_message_group", "can_create_topic_group").
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
        require_active_channel=require_active_channel,
        require_content_access=require_content_access,
    )
    return (stream, sub)


def get_public_streams_queryset(realm: Realm) -> QuerySet[Stream]:
    return Stream.objects.filter(realm=realm, invite_only=False, history_public_to_subscribers=True)


def get_web_public_streams_queryset(realm: Realm) -> QuerySet[Stream]:
    # This should match the include_web_public code path in do_get_streams.
    return Stream.objects.filter(
        realm=realm,
        is_web_public=True,
        # In theory, is_web_public=True implies invite_only=False and
        # history_public_to_subscribers=True, but it's safer to include
        # these in the query.
        invite_only=False,
        history_public_to_subscribers=True,
    )


def check_stream_name_available(realm: Realm, name: str) -> None:
    check_stream_name(name)
    try:
        get_stream(name, realm)
        raise ChannelExistsError(name)
    except Stream.DoesNotExist:
        pass


def access_stream_by_name(
    user_profile: UserProfile,
    stream_name: str,
    *,
    require_active_channel: bool = True,
    require_content_access: bool = True,
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
        require_active_channel=require_active_channel,
        require_content_access=require_content_access,
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


def can_access_stream_metadata_user_ids(stream: Stream) -> set[int]:
    # return user ids of users who can access the attributes of a
    # stream, such as its name/description.  Useful for sending events
    # to all users with access to a stream's attributes.
    return bulk_can_access_stream_metadata_user_ids([stream])[stream.id]


def bulk_can_access_stream_metadata_user_ids(streams: list[Stream]) -> dict[int, set[int]]:
    # return user ids of users who can access the attributes of a
    # stream, such as its name/description.  Useful for sending events
    # to all users with access to a stream's attributes.
    result: dict[int, set[int]] = {}
    public_streams = []
    private_streams = []
    for stream in streams:
        if stream.is_public():
            public_streams.append(stream)
        else:
            private_streams.append(stream)

    if len(public_streams) > 0:
        guest_subscriptions = get_guest_user_ids_for_streams(
            {stream.id for stream in public_streams}
        )
        active_non_guest_user_id_set = set(active_non_guest_user_ids(public_streams[0].realm_id))
        for stream in public_streams:
            result[stream.id] = set(active_non_guest_user_id_set | guest_subscriptions[stream.id])

    if len(private_streams) > 0:
        private_stream_user_ids = get_user_ids_for_streams(
            {stream.id for stream in private_streams}
        )
        admin_users_and_bots = {user.id for user in stream.realm.get_admin_users_and_bots()}
        users_dict_with_metadata_access_to_streams_via_permission_groups = (
            get_users_dict_with_metadata_access_to_streams_via_permission_groups(
                private_streams, private_streams[0].realm_id
            )
        )
        for stream in private_streams:
            result[stream.id] = (
                private_stream_user_ids[stream.id]
                | admin_users_and_bots
                | users_dict_with_metadata_access_to_streams_via_permission_groups[stream.id]
            )

    return result


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


def can_delete_any_message_in_channel(user_profile: UserProfile, stream: Stream) -> bool:
    return user_has_permission_for_group_setting(
        stream.can_delete_any_message_group_id,
        user_profile,
        Stream.stream_permission_group_settings["can_delete_any_message_group"],
        direct_member_only=False,
    )


def can_delete_own_message_in_channel(user_profile: UserProfile, stream: Stream) -> bool:
    return user_has_permission_for_group_setting(
        stream.can_delete_own_message_group_id,
        user_profile,
        Stream.stream_permission_group_settings["can_delete_own_message_group"],
        direct_member_only=False,
    )


def can_move_messages_out_of_channel(user_profile: UserProfile, stream: Stream) -> bool:
    if user_profile.is_realm_admin:
        return True

    if user_profile.can_move_messages_between_streams():
        return True

    if can_administer_accessible_channel(stream, user_profile):
        return True

    return user_has_permission_for_group_setting(
        stream.can_move_messages_out_of_channel_group_id,
        user_profile,
        Stream.stream_permission_group_settings["can_move_messages_out_of_channel_group"],
        direct_member_only=False,
    )


def can_move_messages_within_channel(user_profile: UserProfile, stream: Stream) -> bool:
    if user_profile.is_realm_admin or can_administer_accessible_channel(stream, user_profile):
        return True

    return user_has_permission_for_group_setting(
        stream.can_move_messages_within_channel_group_id,
        user_profile,
        Stream.stream_permission_group_settings["can_move_messages_within_channel_group"],
        direct_member_only=False,
    )


def can_edit_topic(user_profile: UserProfile, orig_stream: Stream, target_stream: Stream) -> bool:
    # Users can only edit topics if they have either of these permissions:
    #   1) organization-level permission to edit topics
    #   2) channel-level permission to edit topics in the original channel
    #   3) channel-level permission to edit topics in the target channel
    # If none apply, throw error.
    if user_profile.can_move_messages_to_another_topic():
        return True

    if can_move_messages_within_channel(user_profile, orig_stream):
        return True

    if orig_stream.id != target_stream.id and can_move_messages_within_channel(
        user_profile, target_stream
    ):
        return True

    return False


def can_resolve_topics_in_stream(user: UserProfile, stream: Stream) -> bool:
    return user_has_permission_for_group_setting(
        stream.can_resolve_topics_group_id,
        user,
        Stream.stream_permission_group_settings["can_resolve_topics_group"],
        direct_member_only=False,
    )


def can_resolve_topics(user: UserProfile, orig_stream: Stream, target_stream: Stream) -> bool:
    # Users can only resolve topics if they have either of these permissions:
    #   1) organization-level permission to resolve topics
    #   2) channel-level permission to resolve topics in the original channel
    #   3) channel-level permission to resolve topics in the target channel
    # If none apply, throw error.
    if user.can_resolve_topic():
        return True

    if can_resolve_topics_in_stream(user, orig_stream):
        return True

    if orig_stream != target_stream and can_resolve_topics_in_stream(user, target_stream):
        return True

    return False


def bulk_can_remove_subscribers_from_streams(
    streams: list[Stream], user_profile: UserProfile
) -> bool:
    # Optimization for the organization administrator code path. We
    # don't explicitly grant realm admins this permission, but admins
    # implicitly have the can_administer_channel_group permission for
    # all accessible channels. For channels that the administrator
    # cannot access, they can do limited administration including
    # removing subscribers.
    if user_profile.is_realm_admin:
        return True

    if user_profile.is_guest:
        # All the permissions in this function have allow_everyone_group=False
        return False  # nocoverage

    user_recursive_group_ids = set(
        get_recursive_membership_groups(user_profile).values_list("id", flat=True)
    )

    # We check this before basic access since for the channels the user
    # cannot access, they can unsubscribe other users if they have
    # permission to administer that channel.
    permission_failure_streams: set[int] = set()
    for stream in streams:
        if not is_user_in_can_administer_channel_group(stream, user_recursive_group_ids):
            permission_failure_streams.add(stream.id)

    if not bool(permission_failure_streams):
        return True

    existing_recipient_ids = [stream.recipient_id for stream in streams]
    sub_recipient_ids = Subscription.objects.filter(
        user_profile=user_profile, recipient_id__in=existing_recipient_ids, active=True
    ).values_list("recipient_id", flat=True)

    for stream in streams:
        assert stream.recipient_id is not None
        is_subscribed = stream.recipient_id in sub_recipient_ids
        if not check_basic_stream_access(
            user_profile, stream, is_subscribed=is_subscribed, require_content_access=False
        ):
            return False

    for stream in streams:
        if not is_user_in_can_remove_subscribers_group(stream, user_recursive_group_ids):
            return False

    return True


def get_streams_to_which_user_cannot_add_subscribers(
    streams: list[Stream],
    user_profile: UserProfile,
    *,
    allow_default_streams: bool = False,
    user_group_membership_details: UserGroupMembershipDetails,
) -> list[Stream]:
    # IMPORTANT: This function expects its callers to have already
    # checked that the user can access the provided channels, and thus
    # does not waste database queries re-checking that.
    result: list[Stream] = []

    if user_profile.can_subscribe_others_to_all_accessible_streams():
        return []

    # Optimization for the organization administrator code path. We
    # don't explicitly grant realm admins this permission, but admins
    # implicitly have the can_administer_channel_group permission for
    # all accessible channels.
    if user_profile.is_realm_admin:
        return []

    if user_group_membership_details.user_recursive_group_ids is None:
        user_group_membership_details.user_recursive_group_ids = set(
            get_recursive_membership_groups(user_profile).values_list("id", flat=True)
        )
    if allow_default_streams:
        default_stream_ids = get_default_stream_ids_for_realm(user_profile.realm_id)

    for stream in streams:
        # All the permissions in this function have allow_everyone_group=False
        if user_profile.is_guest:  # nocoverage
            result.append(stream)
            continue

        # We only allow this exception for the invite code path and not
        # for other code paths, since a user should be able to add the
        # invited users to default channels regardless of their permission
        # for that individual channel.
        if allow_default_streams and stream.id in default_stream_ids:
            continue

        if is_user_in_can_administer_channel_group(
            stream, user_group_membership_details.user_recursive_group_ids
        ):
            continue

        if not is_user_in_can_add_subscribers_group(
            stream, user_group_membership_details.user_recursive_group_ids
        ):
            result.append(stream)

    return result


def can_administer_accessible_channel(channel: Stream, user_profile: UserProfile) -> bool:
    # IMPORTANT: This function expects its callers to have already
    # checked that the user can access the provided channel.
    group_id_allowed_to_administer_channel = channel.can_administer_channel_group_id
    assert group_id_allowed_to_administer_channel is not None
    return user_has_permission_for_group_setting(
        group_id_allowed_to_administer_channel,
        user_profile,
        Stream.stream_permission_group_settings["can_administer_channel_group"],
    )


def get_metadata_access_streams(
    user_profile: UserProfile,
    streams: Collection[Stream],
    user_group_membership_details: UserGroupMembershipDetails,
) -> list[Stream]:
    if len(streams) == 0:
        return []

    recipient_ids = [stream.recipient_id for stream in streams]
    subscribed_recipient_ids = set(
        Subscription.objects.filter(
            user_profile=user_profile, recipient_id__in=recipient_ids, active=True
        ).values_list("recipient_id", flat=True)
    )

    metadata_access_streams: list[Stream] = []

    for stream in streams:
        is_subscribed = stream.recipient_id in subscribed_recipient_ids
        if user_has_metadata_access(
            user_profile,
            stream,
            user_group_membership_details,
            is_subscribed=is_subscribed,
        ):
            metadata_access_streams.append(stream)

    return metadata_access_streams


@dataclass
class StreamsCategorizedByPermissionsForAddingSubscribers:
    authorized_streams: list[Stream]
    unauthorized_streams: list[Stream]
    streams_to_which_user_cannot_add_subscribers: list[Stream]


def get_content_access_streams(
    user_profile: UserProfile,
    streams: Collection[Stream],
    user_group_membership_details: UserGroupMembershipDetails,
) -> list[Stream]:
    if len(streams) == 0:
        return []

    recipient_ids = [stream.recipient_id for stream in streams]
    subscribed_recipient_ids = set(
        Subscription.objects.filter(
            user_profile=user_profile, recipient_id__in=recipient_ids, active=True
        ).values_list("recipient_id", flat=True)
    )

    content_access_streams: list[Stream] = []

    for stream in streams:
        is_subscribed = stream.recipient_id in subscribed_recipient_ids
        if user_has_content_access(
            user_profile,
            stream,
            user_group_membership_details,
            is_subscribed=is_subscribed,
        ):
            content_access_streams.append(stream)

    return content_access_streams


def filter_stream_authorization_for_adding_subscribers(
    user_profile: UserProfile, streams: Collection[Stream], is_subscribing_other_users: bool = False
) -> StreamsCategorizedByPermissionsForAddingSubscribers:
    if len(streams) == 0:
        return StreamsCategorizedByPermissionsForAddingSubscribers(
            authorized_streams=[],
            unauthorized_streams=[],
            streams_to_which_user_cannot_add_subscribers=[],
        )

    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    content_access_streams = get_content_access_streams(
        user_profile,
        streams,
        user_group_membership_details,
    )
    content_access_stream_ids = {stream.id for stream in content_access_streams}

    streams_to_which_user_cannot_add_subscribers: list[Stream] = []
    if is_subscribing_other_users:
        streams_to_which_user_cannot_add_subscribers = (
            get_streams_to_which_user_cannot_add_subscribers(
                content_access_streams,
                user_profile,
                user_group_membership_details=user_group_membership_details,
            )
        )

    unauthorized_streams = [
        stream for stream in streams if stream.id not in content_access_stream_ids
    ]
    unauthorized_stream_ids = {stream.id for stream in unauthorized_streams}

    stream_ids_to_which_user_cannot_add_subscribers = {
        stream.id for stream in streams_to_which_user_cannot_add_subscribers
    }
    authorized_streams = [
        stream
        for stream in content_access_streams
        if stream.id not in stream_ids_to_which_user_cannot_add_subscribers
        and stream.id not in unauthorized_stream_ids
    ]
    return StreamsCategorizedByPermissionsForAddingSubscribers(
        authorized_streams=authorized_streams,
        unauthorized_streams=unauthorized_streams,
        streams_to_which_user_cannot_add_subscribers=streams_to_which_user_cannot_add_subscribers,
    )


def access_requested_group_permissions_for_streams(
    stream_names: list[str],
    user_profile: UserProfile,
    realm: Realm,
    request_settings_dict: dict[str, Any],
) -> tuple[dict[str, dict[str, UserGroup]], dict[int, UserGroupMembersData]]:
    anonymous_group_membership = {}
    stream_group_settings_map = {}
    system_groups_name_dict = get_role_based_system_groups_dict(realm)
    for stream_name in stream_names:
        group_settings_map = {}
        for (
            setting_name,
            permission_configuration,
        ) in Stream.stream_permission_group_settings.items():
            assert setting_name in request_settings_dict
            if request_settings_dict[setting_name] is not None:
                setting_request_value = request_settings_dict[setting_name]
                setting_value = parse_group_setting_value(
                    setting_request_value, system_groups_name_dict[SystemGroups.NOBODY]
                )

                if setting_name == "can_create_topic_group":
                    validate_can_create_topic_group_setting_for_protected_history_streams(
                        request_settings_dict["history_public_to_subscribers"],
                        request_settings_dict["invite_only"],
                        setting_value,
                        system_groups_name_dict,
                    )

                group_settings_map[setting_name] = access_user_group_for_setting(
                    setting_value,
                    user_profile,
                    setting_name=setting_name,
                    permission_configuration=permission_configuration,
                )
                if (
                    setting_name in ["can_delete_any_message_group", "can_delete_own_message_group"]
                    and group_settings_map[setting_name].id
                    != system_groups_name_dict[SystemGroups.NOBODY].id
                    and not user_profile.can_set_delete_message_policy()
                ):
                    raise JsonableError(_("Insufficient permission"))

                if not isinstance(setting_value, int):
                    anonymous_group_membership[group_settings_map[setting_name].id] = setting_value
            else:
                group_settings_map[setting_name] = get_stream_permission_default_group(
                    setting_name, system_groups_name_dict, creator=user_profile
                )
                if permission_configuration.default_group_name == "channel_creator":
                    # Default for some settings like "can_administer_channel_group"
                    # is anonymous group with stream creator.
                    anonymous_group_membership[group_settings_map[setting_name].id] = (
                        UserGroupMembersData(direct_subgroups=[], direct_members=[user_profile.id])
                    )
        stream_group_settings_map[stream_name] = group_settings_map
    return stream_group_settings_map, anonymous_group_membership


def list_to_streams(
    streams_raw: Collection[StreamDict],
    user_profile: UserProfile,
    autocreate: bool = False,
    unsubscribing_others: bool = False,
    is_default_stream: bool = False,
    request_settings_dict: dict[str, Any] | None = None,
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

    if unsubscribing_others and not bulk_can_remove_subscribers_from_streams(
        list(existing_stream_map.values()), user_profile
    ):
        raise JsonableError(_("Insufficient permission"))

    for stream_dict in streams_raw:
        stream_name = stream_dict["name"]
        stream = existing_stream_map.get(stream_name.lower())
        if stream is None:
            missing_stream_dicts.append(stream_dict)
        else:
            existing_streams.append(stream)

    if len(missing_stream_dicts) == 0:
        # This is the happy path for callers who expected all of these
        # streams to exist already.
        created_streams: list[Stream] = []
    else:
        if not autocreate:
            raise JsonableError(
                _("Channel(s) ({channel_names}) do not exist").format(
                    channel_names=", ".join(
                        stream_dict["name"] for stream_dict in missing_stream_dicts
                    ),
                )
            )

        assert request_settings_dict is not None
        stream_names = [stream_dict["name"] for stream_dict in missing_stream_dicts]
        stream_group_settings_map, anonymous_group_membership = (
            access_requested_group_permissions_for_streams(
                stream_names,
                user_profile,
                user_profile.realm,
                request_settings_dict,
            )
        )

        # autocreate=True path starts here
        for stream_dict in missing_stream_dicts:
            group_settings_map = stream_group_settings_map[stream_dict["name"]]
            check_channel_creation_permissions(
                user_profile,
                is_default_stream=is_default_stream,
                invite_only=stream_dict.get("invite_only", False),
                is_web_public=stream_dict["is_web_public"],
                message_retention_days=stream_dict.get("message_retention_days", None),
            )

            stream_dict["can_add_subscribers_group"] = group_settings_map[
                "can_add_subscribers_group"
            ]
            stream_dict["can_administer_channel_group"] = group_settings_map[
                "can_administer_channel_group"
            ]
            stream_dict["can_create_topic_group"] = group_settings_map["can_create_topic_group"]
            stream_dict["can_delete_any_message_group"] = group_settings_map[
                "can_delete_any_message_group"
            ]
            stream_dict["can_delete_own_message_group"] = group_settings_map[
                "can_delete_own_message_group"
            ]
            stream_dict["can_move_messages_out_of_channel_group"] = group_settings_map[
                "can_move_messages_out_of_channel_group"
            ]
            stream_dict["can_move_messages_within_channel_group"] = group_settings_map[
                "can_move_messages_within_channel_group"
            ]
            stream_dict["can_send_message_group"] = group_settings_map["can_send_message_group"]
            stream_dict["can_remove_subscribers_group"] = group_settings_map[
                "can_remove_subscribers_group"
            ]
            stream_dict["can_resolve_topics_group"] = group_settings_map["can_resolve_topics_group"]
            stream_dict["can_subscribe_group"] = group_settings_map["can_subscribe_group"]

        # We already filtered out existing streams, so dup_streams
        # will normally be an empty list below, but we protect against somebody
        # else racing to create the same stream.  (This is not an entirely
        # paranoid approach, since often on Zulip two people will discuss
        # creating a new stream, and both people eagerly do it.)
        created_streams, dup_streams = create_streams_if_needed(
            realm=user_profile.realm,
            stream_dicts=missing_stream_dicts,
            acting_user=user_profile,
            anonymous_group_membership=anonymous_group_membership,
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
    anonymous_group_membership: dict[int, UserGroupMembersData] | None = None,
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

    assert anonymous_group_membership is not None
    can_add_subscribers_group = get_group_setting_value_for_register_api(
        stream.can_add_subscribers_group_id, anonymous_group_membership
    )
    can_administer_channel_group = get_group_setting_value_for_register_api(
        stream.can_administer_channel_group_id, anonymous_group_membership
    )
    can_create_topic_group = get_group_setting_value_for_register_api(
        stream.can_create_topic_group_id, anonymous_group_membership
    )
    can_delete_any_message_group = get_group_setting_value_for_register_api(
        stream.can_delete_any_message_group_id, anonymous_group_membership
    )
    can_delete_own_message_group = get_group_setting_value_for_register_api(
        stream.can_delete_own_message_group_id, anonymous_group_membership
    )
    can_move_messages_out_of_channel_group = get_group_setting_value_for_register_api(
        stream.can_move_messages_out_of_channel_group_id, anonymous_group_membership
    )
    can_move_messages_within_channel_group = get_group_setting_value_for_register_api(
        stream.can_move_messages_within_channel_group_id, anonymous_group_membership
    )
    can_send_message_group = get_group_setting_value_for_register_api(
        stream.can_send_message_group_id, anonymous_group_membership
    )
    can_remove_subscribers_group = get_group_setting_value_for_register_api(
        stream.can_remove_subscribers_group_id, anonymous_group_membership
    )
    can_resolve_topics_group = get_group_setting_value_for_register_api(
        stream.can_resolve_topics_group_id, anonymous_group_membership
    )
    can_subscribe_group = get_group_setting_value_for_register_api(
        stream.can_subscribe_group_id, anonymous_group_membership
    )

    stream_post_policy = get_stream_post_policy_value_based_on_group_setting(
        stream.can_send_message_group
    )

    return APIStreamDict(
        is_archived=stream.deactivated,
        can_add_subscribers_group=can_add_subscribers_group,
        can_administer_channel_group=can_administer_channel_group,
        can_create_topic_group=can_create_topic_group,
        can_delete_any_message_group=can_delete_any_message_group,
        can_delete_own_message_group=can_delete_own_message_group,
        can_move_messages_out_of_channel_group=can_move_messages_out_of_channel_group,
        can_move_messages_within_channel_group=can_move_messages_within_channel_group,
        can_send_message_group=can_send_message_group,
        can_remove_subscribers_group=can_remove_subscribers_group,
        can_resolve_topics_group=can_resolve_topics_group,
        can_subscribe_group=can_subscribe_group,
        creator_id=stream.creator_id,
        date_created=datetime_to_timestamp(stream.date_created),
        description=stream.description,
        first_message_id=stream.first_message_id,
        folder_id=stream.folder_id,
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
        subscriber_count=stream.subscriber_count,
        topics_policy=StreamTopicsPolicyEnum(stream.topics_policy).name,
    )


def get_web_public_streams(
    realm: Realm, anonymous_group_membership: dict[int, UserGroupMembersData]
) -> list[APIStreamDict]:  # nocoverage
    query = get_web_public_streams_queryset(realm).select_related(
        # TODO: We need these fields to compute stream_post_policy; we
        # can drop this select_related clause once that legacy field
        # is removed from the API.
        "can_send_message_group",
        "can_send_message_group__named_user_group",
    )
    streams = query.only(*Stream.API_FIELDS)
    stream_dicts = [stream_to_dict(stream, None, anonymous_group_membership) for stream in streams]
    return stream_dicts


def get_streams_for_user(
    user_profile: UserProfile,
    include_public: bool = True,
    include_web_public: bool = False,
    include_subscribed: bool = True,
    exclude_archived: bool = True,
    include_all: bool = False,
    include_owner_subscribed: bool = False,
    include_can_access_content: bool = False,
) -> list[Stream]:
    include_public = include_public and user_profile.can_access_public_streams()

    # Start out with all streams in the realm.
    query = Stream.objects.select_related(
        "can_send_message_group", "can_send_message_group__named_user_group"
    ).filter(realm=user_profile.realm)

    if exclude_archived:
        query = query.filter(deactivated=False)

    if include_all:
        all_streams = list(
            query.only(
                *Stream.API_FIELDS,
                "can_send_message_group",
                "can_send_message_group__named_user_group",
                # This field is needed for get_content_access_streams.
                "recipient_id",
            )
        )
        user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
        return get_metadata_access_streams(user_profile, all_streams, user_group_membership_details)
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

        should_add_owner_subscribed_filter = include_owner_subscribed and user_profile.is_bot

        if include_can_access_content:
            all_streams = list(
                query.only(
                    *Stream.API_FIELDS,
                    "can_send_message_group",
                    "can_send_message_group__named_user_group",
                    # This field is needed for get_content_access_streams.
                    "recipient_id",
                )
            )
            user_group_membership_details = UserGroupMembershipDetails(
                user_recursive_group_ids=None
            )
            content_access_streams = get_content_access_streams(
                user_profile, all_streams, user_group_membership_details
            )
            # Optimization: Currently, only include_owner_subscribed
            # has the ability to add additional results to
            # content_access_streams. We return early to save us a
            # database query down the line if we do not need to add
            # include_owner_subscribed filter.
            if not should_add_owner_subscribed_filter:
                return content_access_streams

            content_access_stream_ids = [stream.id for stream in content_access_streams]
            content_access_stream_check = Q(id__in=set(content_access_stream_ids))
            add_filter_option(content_access_stream_check)

        # Subscribed channels will already have been included if
        # include_can_access_content is True.
        if not include_can_access_content and include_subscribed:
            subscribed_stream_ids = get_subscribed_stream_ids_for_user(user_profile)
            recipient_check = Q(id__in=set(subscribed_stream_ids))
            add_filter_option(recipient_check)

        # All accessible public channels will already have been
        # included if include_can_access_content is True.
        if not include_can_access_content and include_public:
            invite_only_check = Q(invite_only=False)
            add_filter_option(invite_only_check)

        # All accessible web-public channels will already have been
        # included if include_can_access_content is True.
        if not include_can_access_content and include_web_public:
            # This should match get_web_public_streams_queryset
            web_public_check = Q(
                is_web_public=True,
                invite_only=False,
                history_public_to_subscribers=True,
                deactivated=False,
            )
            add_filter_option(web_public_check)

        if should_add_owner_subscribed_filter:
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


def get_anonymous_group_membership_dict_for_streams(
    streams: list[Stream],
) -> dict[int, UserGroupMembersData]:
    setting_group_ids = set()
    for stream in streams:
        for setting_name in Stream.stream_permission_group_settings:
            setting_group_ids.add(getattr(stream, setting_name + "_id"))

    anonymous_groups_membership_dict: dict[int, UserGroupMembersData] = dict()

    anonymous_group_ids = UserGroup.objects.filter(
        id__in=setting_group_ids, named_user_group=None
    ).values_list("id", flat=True)
    if len(anonymous_group_ids) == 0:
        return anonymous_groups_membership_dict

    return get_members_and_subgroups_of_groups(anonymous_group_ids)


def do_get_streams(
    user_profile: UserProfile,
    include_public: bool = True,
    include_web_public: bool = False,
    include_subscribed: bool = True,
    exclude_archived: bool = True,
    include_all: bool = False,
    include_default: bool = False,
    include_owner_subscribed: bool = False,
    include_can_access_content: bool = False,
    anonymous_group_membership: dict[int, UserGroupMembersData] | None = None,
) -> list[APIStreamDict]:
    # This function is only used by API clients now.

    streams = get_streams_for_user(
        user_profile,
        include_public,
        include_web_public,
        include_subscribed,
        exclude_archived,
        include_all,
        include_owner_subscribed,
        include_can_access_content,
    )

    stream_ids = {stream.id for stream in streams}
    recent_traffic = get_streams_traffic(user_profile.realm, stream_ids)

    if anonymous_group_membership is None:
        anonymous_group_membership = get_anonymous_group_membership_dict_for_streams(streams)

    stream_dicts = sorted(
        (stream_to_dict(stream, recent_traffic, anonymous_group_membership) for stream in streams),
        key=lambda elt: elt["name"],
    )

    if include_default:
        default_stream_ids = get_default_stream_ids_for_realm(user_profile.realm_id)
        for stream_dict in stream_dicts:
            stream_dict["is_default"] = stream_dict["stream_id"] in default_stream_ids

    return stream_dicts


def notify_stream_is_recently_active_update(stream: Stream, value: bool) -> None:
    event = dict(
        type="stream",
        op="update",
        property="is_recently_active",
        value=value,
        stream_id=stream.id,
        name=stream.name,
    )

    send_event_on_commit(stream.realm, event, can_access_stream_metadata_user_ids(stream))


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
        notify_stream_is_recently_active_update(stream, False)

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


def send_stream_deletion_event(
    realm: Realm, user_ids: Iterable[int], streams: list[Stream], for_archiving: bool = False
) -> None:
    stream_deletion_event = dict(
        type="stream",
        op="delete",
        # "streams" is deprecated, kept only for compatibility.
        streams=[dict(stream_id=stream.id) for stream in streams],
        stream_ids=[stream.id for stream in streams],
        for_archiving=for_archiving,
    )
    send_event_on_commit(realm, stream_deletion_event, user_ids)


def get_metadata_access_streams_via_group_ids(
    group_ids: list[int], realm: Realm
) -> QuerySet[Stream]:
    """
    Given a list of group ids, we will return streams that contains
    those group ids as a value for one of the group permission settings
    that can grant metadata access.
    """
    return Stream.objects.filter(
        Q(can_add_subscribers_group_id__in=group_ids)
        | Q(can_administer_channel_group_id__in=group_ids)
        | Q(can_subscribe_group_id__in=group_ids),
        realm_id=realm.id,
    )

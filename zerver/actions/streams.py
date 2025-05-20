from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.default_streams import (
    do_remove_default_stream,
    do_remove_streams_from_default_stream_group,
)
from zerver.actions.message_send import internal_send_stream_message
from zerver.actions.subscriptions import bulk_add_subscriptions, bulk_remove_subscriptions
from zerver.lib.cache import (
    cache_delete_many,
    cache_set,
    display_recipient_cache_key,
    to_dict_cache_key_id,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import silent_mention_syntax_for_user, silent_mention_syntax_for_user_group
from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_id
from zerver.lib.stream_traffic import get_streams_traffic
from zerver.lib.streams import (
    can_access_stream_metadata_user_ids,
    get_anonymous_group_membership_dict_for_streams,
    get_stream_permission_policy_key,
    get_stream_post_policy_value_based_on_group_setting,
    get_user_ids_with_metadata_access_via_permission_groups,
    render_stream_description,
    send_stream_creation_event,
    send_stream_deletion_event,
)
from zerver.lib.subscription_info import get_subscribers_query
from zerver.lib.types import UserGroupMembersData
from zerver.lib.user_groups import (
    convert_to_user_group_members_dict,
    get_group_setting_value_for_api,
    get_group_setting_value_for_audit_log_data,
    update_or_create_user_group_for_setting,
)
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    ChannelEmailAddress,
    DefaultStream,
    DefaultStreamGroup,
    Message,
    Realm,
    RealmAuditLog,
    Stream,
    Subscription,
    UserProfile,
)
from zerver.models.groups import NamedUserGroup, UserGroup
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm_by_id
from zerver.models.users import active_non_guest_user_ids, active_user_ids, get_system_bot
from zerver.tornado.django_api import send_event_on_commit


def maybe_set_moderation_or_announcement_channels_none(stream: Stream) -> None:
    realm = get_realm_by_id(realm_id=stream.realm_id)
    realm_moderation_or_announcement_channels = (
        "moderation_request_channel_id",
        "new_stream_announcements_stream_id",
        "signup_announcements_stream_id",
        "zulip_update_announcements_stream_id",
    )
    update_realm_moderation_or_announcement_channels = []

    for field in realm_moderation_or_announcement_channels:
        if getattr(realm, field) == stream.id:
            setattr(realm, field, None)
            update_realm_moderation_or_announcement_channels.append(field)

    if update_realm_moderation_or_announcement_channels:
        realm.save(update_fields=update_realm_moderation_or_announcement_channels)

        event_data: dict[str, int] = {}
        for field in update_realm_moderation_or_announcement_channels:
            event_data[field] = -1

        event = dict(
            type="realm",
            op="update_dict",
            property="default",
            data=event_data,
        )
        send_event_on_commit(realm, event, active_user_ids(realm.id))


@transaction.atomic(savepoint=False)
def do_deactivate_stream(stream: Stream, *, acting_user: UserProfile | None) -> None:
    # If the stream is already deactivated, this is a no-op
    if stream.deactivated is True:
        raise JsonableError(_("Channel is already deactivated"))

    # Get the affected user ids *before* we deactivate everybody.
    affected_user_ids = can_access_stream_metadata_user_ids(stream)

    was_public = stream.is_public()
    was_web_public = stream.is_web_public
    stream.deactivated = True
    stream.save(update_fields=["deactivated"])

    ChannelEmailAddress.objects.filter(realm=stream.realm, channel=stream).update(deactivated=True)

    maybe_set_moderation_or_announcement_channels_none(stream)

    assert stream.recipient_id is not None
    if was_web_public:
        assert was_public
        # Unset the is_web_public and is_realm_public cache on attachments,
        # since the stream is now archived.
        Attachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_web_public=None, is_realm_public=None
        )
        ArchivedAttachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_web_public=None, is_realm_public=None
        )
    elif was_public:
        # Unset the is_realm_public cache on attachments, since the stream is now archived.
        Attachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_realm_public=None
        )
        ArchivedAttachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_realm_public=None
        )

    # If this is a default stream, remove it, properly sending a
    # notification to browser clients.
    if DefaultStream.objects.filter(realm_id=stream.realm_id, stream_id=stream.id).exists():
        do_remove_default_stream(stream)

    default_stream_groups_for_stream = DefaultStreamGroup.objects.filter(streams__id=stream.id)
    for group in default_stream_groups_for_stream:
        do_remove_streams_from_default_stream_group(stream.realm, group, [stream])

    event = dict(
        type="stream",
        op="update",
        stream_id=stream.id,
        name=stream.name,
        property="is_archived",
        value=True,
    )
    send_event_on_commit(stream.realm, event, affected_user_ids)

    send_stream_deletion_event(stream.realm, affected_user_ids, [stream], for_archiving=True)

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=stream.realm,
        acting_user=acting_user,
        modified_stream=stream,
        event_type=AuditLogEventType.CHANNEL_DEACTIVATED,
        event_time=event_time,
    )

    sender = get_system_bot(settings.NOTIFICATION_BOT, stream.realm_id)
    with override_language(stream.realm.default_language):
        internal_send_stream_message(
            sender,
            stream,
            topic_name=str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME),
            content=_("Channel #**{channel_name}** has been archived.").format(
                channel_name=stream.name
            ),
            archived_channel_notice=True,
            limit_unread_user_ids=set(),
        )


def deactivated_streams_by_old_name(realm: Realm, stream_name: str) -> QuerySet[Stream]:
    fixed_length_prefix = ".......!DEACTIVATED:"
    truncated_name = stream_name[0 : Stream.MAX_NAME_LENGTH - len(fixed_length_prefix)]

    old_names: list[str] = [
        ("!" * bang_length + "DEACTIVATED:" + stream_name)[: Stream.MAX_NAME_LENGTH]
        for bang_length in range(1, 21)
    ]

    possible_streams = Stream.objects.filter(realm=realm, deactivated=True).filter(
        # We go looking for names as they are post-1b6f68bb59dc; 8
        # characters, followed by `!DEACTIVATED:`, followed by at
        # most MAX_NAME_LENGTH-(length of the prefix) of the name
        # they provided:
        Q(name=stream_name)
        | Q(name__regex=rf"^{fixed_length_prefix}{truncated_name}")
        # Finally, we go looking for the pre-1b6f68bb59dc version,
        # which is any number of `!` followed by `DEACTIVATED:`
        # and a prefix of the old stream name
        | Q(name__in=old_names),
    )

    return possible_streams


@transaction.atomic(savepoint=False)
def do_unarchive_stream(stream: Stream, new_name: str, *, acting_user: UserProfile | None) -> None:
    realm = stream.realm
    stream_subscribers = get_active_subscriptions_for_stream_id(
        stream.id, include_deactivated_users=True
    ).select_related("user_profile")

    if not stream.deactivated:
        raise JsonableError(_("Channel is not currently deactivated"))
    if stream.name != new_name and Stream.objects.filter(realm=realm, name=new_name).exists():
        raise JsonableError(
            _("Channel named {channel_name} already exists").format(channel_name=new_name)
        )
    if stream.invite_only and not stream_subscribers:
        raise JsonableError(_("Channel is private and have no subscribers"))
    assert stream.recipient_id is not None

    stream.deactivated = False
    stream.name = new_name
    if stream.invite_only and stream.is_web_public:
        # Previously, because archiving a channel set invite_only=True
        # without mutating is_web_public, it was possible for archived
        # channels to have this invalid state. Fix that.
        stream.is_web_public = False

    stream.save(
        update_fields=[
            "name",
            "deactivated",
            "is_web_public",
        ]
    )

    ChannelEmailAddress.objects.filter(realm=realm, channel=stream).update(deactivated=False)

    # Update caches
    cache_set(display_recipient_cache_key(stream.recipient_id), new_name)
    messages = Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_id
        realm_id=realm.id,
        recipient_id=stream.recipient_id,
    ).only("id")
    cache_delete_many(to_dict_cache_key_id(message.id) for message in messages)

    # Unset the is_web_public and is_realm_public cache on attachments,
    # since the stream is now private.
    Attachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
        is_web_public=None, is_realm_public=None
    )
    ArchivedAttachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
        is_web_public=None, is_realm_public=None
    )

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        modified_stream=stream,
        event_type=AuditLogEventType.CHANNEL_REACTIVATED,
        event_time=timezone_now(),
    )

    recent_traffic = get_streams_traffic({stream.id}, realm)

    notify_user_ids = list(can_access_stream_metadata_user_ids(stream))

    event = dict(
        type="stream",
        op="update",
        stream_id=stream.id,
        name=stream.name,
        property="is_archived",
        value=False,
    )
    send_event_on_commit(stream.realm, event, notify_user_ids)

    anonymous_group_membership = get_anonymous_group_membership_dict_for_streams([stream])
    send_stream_creation_event(
        realm,
        stream,
        notify_user_ids,
        recent_traffic,
        anonymous_group_membership,
        for_unarchiving=True,
    )

    sender = get_system_bot(settings.NOTIFICATION_BOT, stream.realm_id)
    with override_language(stream.realm.default_language):
        internal_send_stream_message(
            sender,
            stream,
            str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME),
            _("Channel #**{channel_name}** has been unarchived.").format(channel_name=new_name),
        )


def bulk_delete_cache_keys(message_ids_to_clear: list[int]) -> None:
    while len(message_ids_to_clear) > 0:
        batch = message_ids_to_clear[0:5000]

        keys_to_delete = [to_dict_cache_key_id(message_id) for message_id in batch]
        cache_delete_many(keys_to_delete)

        message_ids_to_clear = message_ids_to_clear[5000:]


def merge_streams(
    realm: Realm, stream_to_keep: Stream, stream_to_destroy: Stream
) -> tuple[int, int, int]:
    recipient_to_destroy = stream_to_destroy.recipient
    recipient_to_keep = stream_to_keep.recipient
    assert recipient_to_keep is not None
    assert recipient_to_destroy is not None
    if recipient_to_destroy.id == recipient_to_keep.id:
        return (0, 0, 0)

    # The high-level approach here is to move all the messages to
    # the surviving stream, deactivate all the subscriptions on
    # the stream to be removed and deactivate the stream, and add
    # new subscriptions to the stream to keep for any users who
    # were only on the now-deactivated stream.
    #
    # The order of operations is carefully chosen so that calling this
    # function again is likely to be an effective way to recover if
    # this process is interrupted by an error.

    # Move the Subscription objects.  This algorithm doesn't
    # preserve any stream settings/colors/etc. from the stream
    # being destroyed, but it's convenient.
    existing_subs = Subscription.objects.filter(recipient=recipient_to_keep)
    users_already_subscribed = {sub.user_profile_id: sub.active for sub in existing_subs}

    subs_to_deactivate = Subscription.objects.filter(recipient=recipient_to_destroy, active=True)
    users_to_activate = [
        sub.user_profile
        for sub in subs_to_deactivate
        if not users_already_subscribed.get(sub.user_profile_id, False)
    ]

    if len(users_to_activate) > 0:
        bulk_add_subscriptions(realm, [stream_to_keep], users_to_activate, acting_user=None)

    # Move the messages, and delete the old copies from caches. We do
    # this before removing the subscription objects, to avoid messages
    # "disappearing" if an error interrupts this function.
    message_ids_to_clear = list(
        Message.objects.filter(
            # Uses index: zerver_message_realm_recipient_id
            realm_id=realm.id,
            recipient=recipient_to_destroy,
        ).values_list("id", flat=True)
    )
    count = Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_id (prefix)
        realm_id=realm.id,
        recipient=recipient_to_destroy,
    ).update(recipient=recipient_to_keep)
    bulk_delete_cache_keys(message_ids_to_clear)

    # Remove subscriptions to the old stream.
    if len(subs_to_deactivate) > 0:
        bulk_remove_subscriptions(
            realm,
            [sub.user_profile for sub in subs_to_deactivate],
            [stream_to_destroy],
            acting_user=None,
        )

    do_deactivate_stream(stream_to_destroy, acting_user=None)

    return (len(users_to_activate), count, len(subs_to_deactivate))


def get_subscriber_ids(
    stream: Stream, requesting_user: UserProfile | None = None
) -> QuerySet[Subscription, int]:
    subscriptions_query = get_subscribers_query(stream, requesting_user)
    return subscriptions_query.values_list("user_profile_id", flat=True)


def send_change_stream_permission_notification(
    stream: Stream,
    *,
    old_policy_name: str,
    new_policy_name: str,
    acting_user: UserProfile,
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, acting_user.realm_id)
    user_mention = silent_mention_syntax_for_user(acting_user)

    with override_language(stream.realm.default_language):
        notification_string = _(
            "{user} changed the [access permissions]({help_link}) "
            "for this channel from **{old_policy}** to **{new_policy}**."
        )
        notification_string = notification_string.format(
            user=user_mention,
            help_link="/help/channel-permissions",
            old_policy=old_policy_name,
            new_policy=new_policy_name,
        )
        internal_send_stream_message(
            sender, stream, str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME), notification_string
        )


@transaction.atomic(savepoint=False)
def do_change_stream_permission(
    stream: Stream,
    *,
    invite_only: bool,
    history_public_to_subscribers: bool,
    is_web_public: bool,
    acting_user: UserProfile,
) -> None:
    old_invite_only_value = stream.invite_only
    old_history_public_to_subscribers_value = stream.history_public_to_subscribers
    old_is_web_public_value = stream.is_web_public

    stream.is_web_public = is_web_public
    stream.invite_only = invite_only
    stream.history_public_to_subscribers = history_public_to_subscribers
    stream.save(update_fields=["invite_only", "history_public_to_subscribers", "is_web_public"])

    realm = stream.realm

    event_time = timezone_now()
    if old_invite_only_value != stream.invite_only:
        # Reset the Attachment.is_realm_public cache for all
        # messages in the stream whose permissions were changed.
        assert stream.recipient_id is not None
        Attachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_realm_public=None
        )
        # We need to do the same for ArchivedAttachment to avoid
        # bugs if deleted attachments are later restored.
        ArchivedAttachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_realm_public=None
        )

        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            event_time=event_time,
            extra_data={
                RealmAuditLog.OLD_VALUE: old_invite_only_value,
                RealmAuditLog.NEW_VALUE: stream.invite_only,
                "property": "invite_only",
            },
        )

    if old_history_public_to_subscribers_value != stream.history_public_to_subscribers:
        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            event_time=event_time,
            extra_data={
                RealmAuditLog.OLD_VALUE: old_history_public_to_subscribers_value,
                RealmAuditLog.NEW_VALUE: stream.history_public_to_subscribers,
                "property": "history_public_to_subscribers",
            },
        )

    if old_is_web_public_value != stream.is_web_public:
        # Reset the Attachment.is_realm_public cache for all
        # messages in the stream whose permissions were changed.
        assert stream.recipient_id is not None
        Attachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_web_public=None
        )
        # We need to do the same for ArchivedAttachment to avoid
        # bugs if deleted attachments are later restored.
        ArchivedAttachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
            is_web_public=None
        )

        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            event_time=event_time,
            extra_data={
                RealmAuditLog.OLD_VALUE: old_is_web_public_value,
                RealmAuditLog.NEW_VALUE: stream.is_web_public,
                "property": "is_web_public",
            },
        )

    notify_stream_creation_ids = set()
    if old_invite_only_value and not stream.invite_only:
        # We need to send stream creation event to users who can access the
        # stream now but were not able to do so previously. So, we can exclude
        # subscribers and realm admins from the non-guest user list.
        stream_subscriber_user_ids = get_active_subscriptions_for_stream_id(
            stream.id, include_deactivated_users=False
        ).values_list("user_profile_id", flat=True)

        old_can_access_stream_metadata_user_ids = set(stream_subscriber_user_ids) | {
            user.id for user in stream.realm.get_admin_users_and_bots()
        }
        user_ids_with_metadata_access_via_permission_groups = (
            get_user_ids_with_metadata_access_via_permission_groups(stream)
        )
        non_guest_user_ids = set(active_non_guest_user_ids(stream.realm_id))
        notify_stream_creation_ids = (
            non_guest_user_ids
            - old_can_access_stream_metadata_user_ids
            - user_ids_with_metadata_access_via_permission_groups
        )

        recent_traffic = get_streams_traffic({stream.id}, realm)
        anonymous_group_membership = get_anonymous_group_membership_dict_for_streams([stream])
        send_stream_creation_event(
            realm,
            stream,
            list(notify_stream_creation_ids),
            recent_traffic,
            anonymous_group_membership,
        )

        # Add subscribers info to the stream object. We need to send peer_add
        # events to users who were previously subscribed to the streams as
        # they did not had subscribers data.
        old_subscribers_access_user_ids = set(stream_subscriber_user_ids) | {
            user.id for user in stream.realm.get_admin_users_and_bots()
        }
        peer_notify_user_ids = (
            non_guest_user_ids
            - old_subscribers_access_user_ids
            - user_ids_with_metadata_access_via_permission_groups
        )
        peer_add_event = dict(
            type="subscription",
            op="peer_add",
            stream_ids=[stream.id],
            user_ids=sorted(stream_subscriber_user_ids),
        )
        send_event_on_commit(stream.realm, peer_add_event, peer_notify_user_ids)

    event = dict(
        op="update",
        type="stream",
        property="invite_only",
        value=stream.invite_only,
        history_public_to_subscribers=stream.history_public_to_subscribers,
        is_web_public=stream.is_web_public,
        stream_id=stream.id,
        name=stream.name,
    )
    # we do not need to send update events to the users who received creation event
    # since they already have the updated stream info.
    notify_stream_update_ids = (
        can_access_stream_metadata_user_ids(stream) - notify_stream_creation_ids
    )
    send_event_on_commit(stream.realm, event, notify_stream_update_ids)

    old_policy_key = get_stream_permission_policy_key(
        invite_only=old_invite_only_value,
        history_public_to_subscribers=old_history_public_to_subscribers_value,
        is_web_public=old_is_web_public_value,
    )
    old_policy_name = Stream.PERMISSION_POLICIES[old_policy_key]["policy_name"]
    new_policy_key = get_stream_permission_policy_key(
        invite_only=stream.invite_only,
        history_public_to_subscribers=stream.history_public_to_subscribers,
        is_web_public=stream.is_web_public,
    )
    new_policy_name = Stream.PERMISSION_POLICIES[new_policy_key]["policy_name"]
    send_change_stream_permission_notification(
        stream,
        old_policy_name=old_policy_name,
        new_policy_name=new_policy_name,
        acting_user=acting_user,
    )


def get_users_string_with_permission(setting_value: int | UserGroupMembersData) -> str:
    if isinstance(setting_value, int):
        setting_group = NamedUserGroup.objects.get(id=setting_value)
        return silent_mention_syntax_for_user_group(setting_group)

    # Sorting by ID generates a deterministic order with system groups
    # first, which seems broadly reasonable.
    groups_with_permission = NamedUserGroup.objects.filter(
        id__in=setting_value.direct_subgroups
    ).order_by("id")
    group_name_syntax_list = [
        silent_mention_syntax_for_user_group(group) for group in groups_with_permission
    ]

    # Sorting by ID generates a deterministic order with older users
    # first, which seems broadly reasonable.
    users_with_permission = UserProfile.objects.filter(
        id__in=setting_value.direct_members
    ).order_by("id")
    user_name_syntax_list = [silent_mention_syntax_for_user(user) for user in users_with_permission]

    return ", ".join(group_name_syntax_list + user_name_syntax_list)


def send_stream_posting_permission_update_notification(
    stream: Stream,
    *,
    old_setting_value: int | UserGroupMembersData,
    new_setting_value: int | UserGroupMembersData,
    acting_user: UserProfile,
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, acting_user.realm_id)
    user_mention = silent_mention_syntax_for_user(acting_user)

    old_setting_description = get_users_string_with_permission(old_setting_value)
    new_setting_description = get_users_string_with_permission(new_setting_value)

    with override_language(stream.realm.default_language):
        notification_string = _(
            "{user} changed the [posting permissions]({help_link}) "
            "for this channel:\n\n"
            "* **Old**: {old_setting_description}\n"
            "* **New**: {new_setting_description}\n"
        )
        notification_string = notification_string.format(
            user=user_mention,
            help_link="/help/channel-posting-policy",
            old_setting_description=old_setting_description,
            new_setting_description=new_setting_description,
        )
        internal_send_stream_message(
            sender, stream, str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME), notification_string
        )


@transaction.atomic(durable=True)
def do_rename_stream(stream: Stream, new_name: str, user_profile: UserProfile) -> None:
    old_name = stream.name
    stream.name = new_name
    stream.save(update_fields=["name"])

    RealmAuditLog.objects.create(
        realm=stream.realm,
        acting_user=user_profile,
        modified_stream=stream,
        event_type=AuditLogEventType.CHANNEL_NAME_CHANGED,
        event_time=timezone_now(),
        extra_data={
            RealmAuditLog.OLD_VALUE: old_name,
            RealmAuditLog.NEW_VALUE: new_name,
        },
    )

    assert stream.recipient_id is not None
    recipient_id: int = stream.recipient_id
    messages = Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_id
        realm_id=stream.realm_id,
        recipient_id=recipient_id,
    ).only("id")

    cache_set(display_recipient_cache_key(recipient_id), stream.name)

    # Delete cache entries for everything else, which is cheaper and
    # clearer than trying to set them. display_recipient is the out of
    # date field in all cases.
    cache_delete_many(to_dict_cache_key_id(message.id) for message in messages)

    # We want to key these updates by id, not name, since id is
    # the immutable primary key, and obviously name is not.
    event = dict(
        op="update",
        type="stream",
        property="name",
        value=new_name,
        stream_id=stream.id,
        name=old_name,
    )
    send_event_on_commit(stream.realm, event, can_access_stream_metadata_user_ids(stream))
    sender = get_system_bot(settings.NOTIFICATION_BOT, stream.realm_id)
    with override_language(stream.realm.default_language):
        internal_send_stream_message(
            sender,
            stream,
            str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME),
            _("{user_name} renamed channel {old_channel_name} to {new_channel_name}.").format(
                user_name=silent_mention_syntax_for_user(user_profile),
                old_channel_name=f"**{old_name}**",
                new_channel_name=f"**{new_name}**",
            ),
        )


def send_change_stream_description_notification(
    stream: Stream, *, old_description: str, new_description: str, acting_user: UserProfile
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, acting_user.realm_id)
    user_mention = silent_mention_syntax_for_user(acting_user)

    with override_language(stream.realm.default_language):
        if new_description == "":
            new_description = "*" + _("No description.") + "*"
        if old_description == "":
            old_description = "*" + _("No description.") + "*"

        notification_string = (
            _("{user} changed the description for this channel.").format(user=user_mention)
            + "\n\n* **"
            + _("Old description")
            + ":**"
            + f"\n```` quote\n{old_description}\n````\n"
            + "* **"
            + _("New description")
            + ":**"
            + f"\n```` quote\n{new_description}\n````"
        )

        internal_send_stream_message(
            sender, stream, str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME), notification_string
        )


@transaction.atomic(durable=True)
def do_change_stream_description(
    stream: Stream, new_description: str, *, acting_user: UserProfile
) -> None:
    old_description = stream.description
    stream.description = new_description
    stream.rendered_description = render_stream_description(
        new_description, stream.realm, acting_user=acting_user
    )
    stream.save(update_fields=["description", "rendered_description"])
    RealmAuditLog.objects.create(
        realm=stream.realm,
        acting_user=acting_user,
        modified_stream=stream,
        event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
        event_time=timezone_now(),
        extra_data={
            RealmAuditLog.OLD_VALUE: old_description,
            RealmAuditLog.NEW_VALUE: new_description,
            "property": "description",
        },
    )

    event = dict(
        type="stream",
        op="update",
        property="description",
        name=stream.name,
        stream_id=stream.id,
        value=new_description,
        rendered_description=stream.rendered_description,
    )
    send_event_on_commit(stream.realm, event, can_access_stream_metadata_user_ids(stream))

    send_change_stream_description_notification(
        stream,
        old_description=old_description,
        new_description=new_description,
        acting_user=acting_user,
    )


def send_change_stream_message_retention_days_notification(
    user_profile: UserProfile, stream: Stream, old_value: int | None, new_value: int | None
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id)
    user_mention = silent_mention_syntax_for_user(user_profile)

    # If switching from or to the organization's default retention policy,
    # we want to take the realm's default into account.
    if old_value is None:
        old_value = stream.realm.message_retention_days
    if new_value is None:
        new_value = stream.realm.message_retention_days

    with override_language(stream.realm.default_language):
        if old_value == Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP["unlimited"]:
            old_retention_period = _("Forever")
            new_retention_period = _("{number_of_days} days").format(number_of_days=new_value)
            summary_line = _(
                "Messages in this channel will now be automatically deleted {number_of_days} days after they are sent."
            ).format(number_of_days=new_value)
        elif new_value == Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP["unlimited"]:
            old_retention_period = _("{number_of_days} days").format(number_of_days=old_value)
            new_retention_period = _("Forever")
            summary_line = _("Messages in this channel will now be retained forever.")
        else:
            old_retention_period = _("{number_of_days} days").format(number_of_days=old_value)
            new_retention_period = _("{number_of_days} days").format(number_of_days=new_value)
            summary_line = _(
                "Messages in this channel will now be automatically deleted {number_of_days} days after they are sent."
            ).format(number_of_days=new_value)
        notification_string = _(
            "{user} has changed the [message retention period]({help_link}) for this channel:\n"
            "* **Old retention period**: {old_retention_period}\n"
            "* **New retention period**: {new_retention_period}\n\n"
            "{summary_line}"
        )
        notification_string = notification_string.format(
            user=user_mention,
            help_link="/help/message-retention-policy",
            old_retention_period=old_retention_period,
            new_retention_period=new_retention_period,
            summary_line=summary_line,
        )
        internal_send_stream_message(
            sender, stream, str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME), notification_string
        )


@transaction.atomic(durable=True)
def do_change_stream_message_retention_days(
    stream: Stream, acting_user: UserProfile, message_retention_days: int | None = None
) -> None:
    old_message_retention_days_value = stream.message_retention_days
    stream.message_retention_days = message_retention_days
    stream.save(update_fields=["message_retention_days"])
    RealmAuditLog.objects.create(
        realm=stream.realm,
        acting_user=acting_user,
        modified_stream=stream,
        event_type=AuditLogEventType.CHANNEL_MESSAGE_RETENTION_DAYS_CHANGED,
        event_time=timezone_now(),
        extra_data={
            RealmAuditLog.OLD_VALUE: old_message_retention_days_value,
            RealmAuditLog.NEW_VALUE: message_retention_days,
        },
    )

    event = dict(
        op="update",
        type="stream",
        property="message_retention_days",
        value=message_retention_days,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event_on_commit(stream.realm, event, can_access_stream_metadata_user_ids(stream))
    send_change_stream_message_retention_days_notification(
        user_profile=acting_user,
        stream=stream,
        old_value=old_message_retention_days_value,
        new_value=message_retention_days,
    )


def do_change_stream_group_based_setting(
    stream: Stream,
    setting_name: str,
    new_setting_value: NamedUserGroup | UserGroupMembersData,
    *,
    old_setting_api_value: int | UserGroupMembersData | None = None,
    acting_user: UserProfile,
) -> None:
    old_user_group = getattr(stream, setting_name)

    if old_setting_api_value is None:
        # Most production callers will have computed this as part of
        # verifying whether there's an actual change to make, but it
        # feels quite clumsy to have to pass it from unit tests, so we
        # compute it here if not provided by the caller.
        old_setting_api_value = get_group_setting_value_for_api(old_user_group)

    old_user_ids_with_metadata_access: set[int] = set()
    if setting_name in Stream.stream_permission_group_settings_granting_metadata_access:
        old_user_ids_with_metadata_access = can_access_stream_metadata_user_ids(stream)

    if isinstance(new_setting_value, NamedUserGroup):
        user_group: UserGroup = new_setting_value
    else:
        user_group = update_or_create_user_group_for_setting(
            acting_user,
            new_setting_value.direct_members,
            new_setting_value.direct_subgroups,
            old_user_group,
        )

    setattr(stream, setting_name, user_group)
    stream.save(update_fields=[setting_name, "name"])

    new_setting_api_value = get_group_setting_value_for_api(user_group)
    RealmAuditLog.objects.create(
        realm=stream.realm,
        acting_user=acting_user,
        modified_stream=stream,
        event_type=AuditLogEventType.CHANNEL_GROUP_BASED_SETTING_CHANGED,
        event_time=timezone_now(),
        extra_data={
            RealmAuditLog.OLD_VALUE: get_group_setting_value_for_audit_log_data(
                old_setting_api_value
            ),
            RealmAuditLog.NEW_VALUE: get_group_setting_value_for_audit_log_data(
                new_setting_api_value
            ),
            "property": setting_name,
        },
    )
    update_event = dict(
        op="update",
        type="stream",
        property=setting_name,
        value=convert_to_user_group_members_dict(new_setting_api_value),
        stream_id=stream.id,
        name=stream.name,
    )
    current_user_ids_with_metadata_access = can_access_stream_metadata_user_ids(stream)

    if setting_name in Stream.stream_permission_group_settings_granting_metadata_access:
        user_ids_gaining_metadata_access = (
            current_user_ids_with_metadata_access - old_user_ids_with_metadata_access
        )
        user_ids_losing_metadata_access = (
            old_user_ids_with_metadata_access - current_user_ids_with_metadata_access
        )
        send_event_on_commit(
            stream.realm,
            update_event,
            current_user_ids_with_metadata_access - user_ids_gaining_metadata_access,
        )

        if len(user_ids_gaining_metadata_access) > 0:
            recent_traffic = get_streams_traffic({stream.id}, stream.realm)
            anonymous_group_membership = get_anonymous_group_membership_dict_for_streams([stream])
            send_stream_creation_event(
                stream.realm,
                stream,
                list(user_ids_gaining_metadata_access),
                recent_traffic,
                anonymous_group_membership,
            )
            subscriber_ids = get_active_subscriptions_for_stream_id(
                stream.id, include_deactivated_users=False
            ).values_list("user_profile_id", flat=True)
            peer_add_event = dict(
                type="subscription",
                op="peer_add",
                stream_ids=[stream.id],
                user_ids=sorted(subscriber_ids),
            )
            send_event_on_commit(
                stream.realm,
                peer_add_event,
                user_ids_gaining_metadata_access,
            )
        if len(user_ids_losing_metadata_access) > 0:
            send_stream_deletion_event(stream.realm, user_ids_losing_metadata_access, [stream])
    else:
        send_event_on_commit(stream.realm, update_event, current_user_ids_with_metadata_access)

    if setting_name == "can_send_message_group":
        old_stream_post_policy = get_stream_post_policy_value_based_on_group_setting(old_user_group)
        stream_post_policy = get_stream_post_policy_value_based_on_group_setting(user_group)

        if old_stream_post_policy != stream_post_policy:
            event = dict(
                op="update",
                type="stream",
                property="stream_post_policy",
                value=stream_post_policy,
                stream_id=stream.id,
                name=stream.name,
            )
            send_event_on_commit(stream.realm, event, current_user_ids_with_metadata_access)

            # Backwards-compatibility code: We removed the
            # is_announcement_only property in early 2020, but we send a
            # duplicate event for legacy mobile clients that might want the
            # data.
            event = dict(
                op="update",
                type="stream",
                property="is_announcement_only",
                value=stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS,
                stream_id=stream.id,
                name=stream.name,
            )
            send_event_on_commit(stream.realm, event, current_user_ids_with_metadata_access)

        assert acting_user is not None
        send_stream_posting_permission_update_notification(
            stream,
            old_setting_value=old_setting_api_value,
            new_setting_value=new_setting_api_value,
            acting_user=acting_user,
        )

    if not hasattr(old_user_group, "named_user_group") and hasattr(user_group, "named_user_group"):
        # We delete the UserGroup which the setting was set to
        # previously if it does not have any linked NamedUserGroup
        # object, as it is not used anywhere else. A new UserGroup
        # object would be created if the setting is later set to
        # a combination of users and groups.
        old_user_group.delete()

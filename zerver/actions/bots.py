from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.actions.create_user import created_bot_event
from zerver.models import RealmAuditLog, Stream, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.users import active_user_ids, bot_owner_user_ids
from zerver.tornado.django_api import send_event_on_commit


def send_bot_owner_update_events(
    user_profile: UserProfile, bot_owner: UserProfile, previous_owner: UserProfile | None
) -> None:
    update_users = bot_owner_user_ids(user_profile)

    # For admins, update event is sent instead of delete/add
    # event. bot_data of admin contains all the
    # bots and none of them should be removed/(added again).

    # Delete the bot from previous owner's bot data.
    if previous_owner and not previous_owner.is_realm_admin:
        delete_event = dict(
            type="realm_bot",
            op="delete",
            bot=dict(
                user_id=user_profile.id,
            ),
        )
        previous_owner_id = previous_owner.id
        send_event_on_commit(
            user_profile.realm,
            delete_event,
            {previous_owner_id},
        )
        # Do not send update event for previous bot owner.
        update_users.discard(previous_owner.id)

    # Notify the new owner that the bot has been added.
    if not bot_owner.is_realm_admin:
        add_event = created_bot_event(user_profile)
        send_event_on_commit(user_profile.realm, add_event, {bot_owner.id})
        # Do not send update event for bot_owner.
        update_users.discard(bot_owner.id)

    bot_event = dict(
        type="realm_bot",
        op="update",
        bot=dict(
            user_id=user_profile.id,
            owner_id=bot_owner.id,
        ),
    )
    send_event_on_commit(
        user_profile.realm,
        bot_event,
        update_users,
    )

    # Since `bot_owner_id` is included in the user profile dict we need
    # to update the users dict with the new bot owner id
    event = dict(
        type="realm_user",
        op="update",
        person=dict(
            user_id=user_profile.id,
            bot_owner_id=bot_owner.id,
        ),
    )
    send_event_on_commit(user_profile.realm, event, active_user_ids(user_profile.realm_id))


@transaction.atomic(durable=True)
def do_change_bot_owner(
    user_profile: UserProfile, bot_owner: UserProfile, acting_user: UserProfile | None
) -> None:
    previous_owner = user_profile.bot_owner
    user_profile.bot_owner = bot_owner
    user_profile.save()  # Can't use update_fields because of how the foreign key works.
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=AuditLogEventType.USER_BOT_OWNER_CHANGED,
        event_time=event_time,
    )

    send_bot_owner_update_events(user_profile, bot_owner, previous_owner)


@transaction.atomic(durable=True)
def do_change_default_sending_stream(
    user_profile: UserProfile, stream: Stream | None, *, acting_user: UserProfile | None
) -> None:
    old_value = user_profile.default_sending_stream_id
    user_profile.default_sending_stream = stream
    user_profile.save(update_fields=["default_sending_stream"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=AuditLogEventType.USER_DEFAULT_SENDING_STREAM_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: None if stream is None else stream.id,
        },
    )

    if user_profile.is_bot:
        if stream:
            stream_name: str | None = stream.name
        else:
            stream_name = None
        event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                default_sending_stream=stream_name,
            ),
        )
        send_event_on_commit(
            user_profile.realm,
            event,
            bot_owner_user_ids(user_profile),
        )


@transaction.atomic(durable=True)
def do_change_default_events_register_stream(
    user_profile: UserProfile, stream: Stream | None, *, acting_user: UserProfile | None
) -> None:
    old_value = user_profile.default_events_register_stream_id
    user_profile.default_events_register_stream = stream
    user_profile.save(update_fields=["default_events_register_stream"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=AuditLogEventType.USER_DEFAULT_REGISTER_STREAM_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: None if stream is None else stream.id,
        },
    )

    if user_profile.is_bot:
        if stream:
            stream_name: str | None = stream.name
        else:
            stream_name = None

        event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                default_events_register_stream=stream_name,
            ),
        )
        send_event_on_commit(
            user_profile.realm,
            event,
            bot_owner_user_ids(user_profile),
        )


@transaction.atomic(durable=True)
def do_change_default_all_public_streams(
    user_profile: UserProfile, value: bool, *, acting_user: UserProfile | None
) -> None:
    old_value = user_profile.default_all_public_streams
    user_profile.default_all_public_streams = value
    user_profile.save(update_fields=["default_all_public_streams"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=AuditLogEventType.USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: value,
        },
    )

    if user_profile.is_bot:
        event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                default_all_public_streams=user_profile.default_all_public_streams,
            ),
        )
        send_event_on_commit(
            user_profile.realm,
            event,
            bot_owner_user_ids(user_profile),
        )

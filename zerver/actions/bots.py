from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.create_user import created_bot_event
from zerver.actions.message_send import internal_send_private_message
from zerver.lib.event_types import (
    BotTypeForDelete,
    BotTypeForUpdate,
    PersonBotOwnerId,
    RealmBotDeleteEvent,
    RealmBotUpdateEvent,
    RealmUserUpdateEvent,
)
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.models import RealmAuditLog, Stream, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.users import active_user_ids, bot_owner_user_ids, get_system_bot
from zerver.tornado.django_api import send_event_on_commit


def send_bot_owner_update_events(
    user_profile: UserProfile, bot_owner: UserProfile, previous_owner: UserProfile | None
) -> None:
    # Since `bot_owner_id` is included in the user profile dict we need
    # to update the users dict with the new bot owner id
    event = RealmUserUpdateEvent(
        person=PersonBotOwnerId(user_id=user_profile.id, bot_owner_id=bot_owner.id),
    )
    send_event_on_commit(user_profile.realm, event, active_user_ids(user_profile.realm_id))

    # Delete the bot from previous owner's bot data.
    if previous_owner and previous_owner.is_active and not previous_owner.is_realm_admin:
        delete_event = RealmBotDeleteEvent(bot=BotTypeForDelete(user_id=user_profile.id))
        previous_owner_id = previous_owner.id
        send_event_on_commit(
            user_profile.realm,
            delete_event,
            {previous_owner_id},
        )

    # Notify the new owner that the bot has been added.
    if not bot_owner.is_realm_admin:
        add_event = created_bot_event(user_profile)
        send_event_on_commit(user_profile.realm, add_event, {bot_owner.id})


def send_bot_owner_change_notification(
    bot: UserProfile,
    bot_owner: UserProfile,
    previous_owner: UserProfile | None,
    acting_user: UserProfile | None,
) -> None:
    bot_mention = silent_mention_syntax_for_user(bot)
    with override_language(bot_owner.default_language):
        if acting_user is not None and acting_user.id != bot_owner.id:
            message = _("{user} made you the owner of {bot}.").format(
                user=silent_mention_syntax_for_user(acting_user), bot=bot_mention
            )
        elif previous_owner is not None:
            # Users don't need to be told about a change they made
            # themselves, unless the previous owner may still have the
            # bot's API key.
            message = _("You are now the owner of {bot}.").format(bot=bot_mention)
        else:
            return

        if previous_owner is not None:
            message += "\n\n"
            message += _(
                "The bot's previous owner, {previous_owner}, may still have a copy of its API key. You can [generate a new API key]({help_link}) to revoke their access, but any integrations using the current key will stop working until they're updated."
            ).format(
                previous_owner=silent_mention_syntax_for_user(previous_owner),
                help_link="/help/manage-a-bot#get-a-bots-api-key",
            )

    notification_bot = get_system_bot(settings.NOTIFICATION_BOT, bot_owner.realm_id)
    internal_send_private_message(notification_bot, bot_owner, message)


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
        extra_data={
            RealmAuditLog.OLD_VALUE: None if previous_owner is None else previous_owner.id,
            RealmAuditLog.NEW_VALUE: bot_owner.id,
        },
    )

    send_bot_owner_update_events(user_profile, bot_owner, previous_owner)
    send_bot_owner_change_notification(user_profile, bot_owner, previous_owner, acting_user)


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
        event = RealmBotUpdateEvent(
            bot=BotTypeForUpdate(user_id=user_profile.id, default_sending_stream=stream_name),
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

        event = RealmBotUpdateEvent(
            bot=BotTypeForUpdate(
                user_id=user_profile.id, default_events_register_stream=stream_name
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
        event = RealmBotUpdateEvent(
            bot=BotTypeForUpdate(
                user_id=user_profile.id,
                default_all_public_streams=user_profile.default_all_public_streams,
            ),
        )
        send_event_on_commit(
            user_profile.realm,
            event,
            bot_owner_user_ids(user_profile),
        )

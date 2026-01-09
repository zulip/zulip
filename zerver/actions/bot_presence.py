import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils.timezone import now as timezone_now
from psycopg2 import sql

from zerver.models import UserPresence, UserProfile

logger = logging.getLogger(__name__)


# This function takes a very hot lock on the PresenceSequence row for the user's realm.
# Since all presence updates in the realm all compete for this lock, we need to be
# maximally efficient and only hold it as briefly as possible.
# For that reason, we need durable=True to ensure we're not running inside a larger
# transaction, which may stay alive longer than we'd like, holding the lock.
@transaction.atomic(durable=True)
def do_update_bot_presence(
    bot: UserProfile,
    is_connected: bool,
    *,
    log_time: datetime | None = None,
) -> None:
    """Update a bot's presence status using the UserPresence table.

    For bots, we use a simple 2-state model:
    - Connected: last_active_time = last_connected_time = log_time (shows as "active")
    - Disconnected: last_active_time = None (shows as "offline")

    This is called either:
    1. Automatically when a bot's event queue is allocated/garbage collected
    2. Explicitly via the API for webhook bots
    """
    if not bot.is_bot:
        raise ValueError("do_update_bot_presence called with non-bot user")

    if log_time is None:
        log_time = timezone_now()

    # For bots:
    # - Connected: set both last_active_time and last_connected_time
    # - Disconnected: set last_active_time = None (preserve last_connected_time)
    defaults = dict(
        realm_id=bot.realm_id,
        last_connected_time=log_time,
        last_active_time=log_time if is_connected else None,
    )

    try:
        presence = UserPresence.objects.select_for_update().get(user_profile=bot)
        creating = False
    except UserPresence.DoesNotExist:
        # Create the presence object in-memory only for now
        presence = UserPresence(**defaults, user_profile=bot)
        creating = True

    # Apply rate limiting similar to user presence
    time_since_last_connected = timedelta(days=1)
    if presence.last_connected_time is not None:
        time_since_last_connected = log_time - presence.last_connected_time

    update_fields = []

    if not creating and time_since_last_connected > timedelta(
        seconds=settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS
    ):
        presence.last_connected_time = log_time
        update_fields.append("last_connected_time")

        if is_connected:
            presence.last_active_time = log_time
            update_fields.append("last_active_time")
        else:
            # Disconnecting: set last_active_time to None
            presence.last_active_time = None
            update_fields.append("last_active_time")
    elif not creating:
        # Even if we're within the rate limit window, we still need to update
        # the active state when connecting/disconnecting
        if is_connected and presence.last_active_time is None:
            # Transitioning from disconnected to connected
            presence.last_active_time = log_time
            presence.last_connected_time = log_time
            update_fields.extend(["last_active_time", "last_connected_time"])
        elif not is_connected and presence.last_active_time is not None:
            # Transitioning from connected to disconnected
            presence.last_active_time = None
            update_fields.append("last_active_time")

    # Use PresenceSequence for last_update_id, same as user presence
    if creating or len(update_fields) > 0:
        query = sql.SQL("""
            WITH new_last_update_id AS (
                UPDATE zerver_presencesequence
                SET last_update_id = last_update_id + 1
                WHERE realm_id = {realm_id}
                RETURNING last_update_id
            )
        """).format(realm_id=sql.Literal(bot.realm_id))

        if creating:
            query += sql.SQL("""
                INSERT INTO zerver_userpresence (user_profile_id, last_active_time, last_connected_time, realm_id, last_update_id)
                VALUES ({user_profile_id}, {last_active_time}, {last_connected_time}, {realm_id}, (SELECT last_update_id FROM new_last_update_id))
                ON CONFLICT (user_profile_id) DO NOTHING
                """).format(
                user_profile_id=sql.Literal(bot.id),
                last_active_time=sql.Literal(presence.last_active_time),
                last_connected_time=sql.Literal(presence.last_connected_time),
                realm_id=sql.Literal(bot.realm_id),
            )
        else:
            assert len(update_fields) > 0
            update_fields_segment = sql.SQL(", ").join(
                sql.SQL("{field} = {value}").format(
                    field=sql.Identifier(field), value=sql.Literal(getattr(presence, field))
                )
                for field in update_fields
            )
            query += sql.SQL("""
                UPDATE zerver_userpresence
                SET {update_fields_segment}, last_update_id = (SELECT last_update_id FROM new_last_update_id)
                WHERE id = {presence_id}
            """).format(
                update_fields_segment=update_fields_segment, presence_id=sql.Literal(presence.id)
            )

        with connection.cursor() as cursor:
            cursor.execute(query)
            if creating:
                actually_created = cursor.rowcount > 0

        if creating and not actually_created:
            logger.info("UserPresence row already created for bot %s, returning.", bot.id)
            return

    # Send presence changed event using the unified presence system
    from zerver.actions.presence import send_presence_changed

    if not bot.realm.presence_disabled:
        transaction.on_commit(lambda: send_presence_changed(bot, presence, force_send_update=True))

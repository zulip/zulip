import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from psycopg2 import sql

from zerver.actions.user_activity import update_user_activity_interval
from zerver.lib.presence import (
    format_legacy_presence_dict,
    user_presence_datetime_with_date_joined_default,
)
from zerver.lib.users import get_user_ids_who_can_access_user
from zerver.models import Client, UserPresence, UserProfile
from zerver.models.clients import get_client
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_rollback_unsafe

logger = logging.getLogger(__name__)


def send_presence_changed(
    user_profile: UserProfile, presence: UserPresence, *, force_send_update: bool = False
) -> None:
    # Most presence data is sent to clients in the main presence
    # endpoint in response to the user's own presence; this results
    # data that is 1-2 minutes stale for who is online.  The flaw with
    # this plan is when a user comes back online and then immediately
    # sends a message, recipients may still see that user as offline!
    # We solve that by sending an immediate presence update clients.
    #
    # The API documentation explains this interaction in more detail.
    if settings.CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE:
        user_ids = get_user_ids_who_can_access_user(user_profile)
    else:
        user_ids = active_user_ids(user_profile.realm_id)

    if (
        len(user_ids) > settings.USER_LIMIT_FOR_SENDING_PRESENCE_UPDATE_EVENTS
        and not force_send_update
    ):
        # These immediate presence generate quadratic work for Tornado
        # (linear number of users in each event and the frequency of
        # users coming online grows linearly with userbase too).  In
        # organizations with thousands of users, this can overload
        # Tornado, especially if much of the realm comes online at the
        # same time.
        #
        # The utility of these live-presence updates goes down as
        # organizations get bigger (since one is much less likely to
        # be paying attention to the sidebar); so beyond a limit, we
        # stop sending them at all.
        return

    last_active_time = user_presence_datetime_with_date_joined_default(
        presence.last_active_time, user_profile.date_joined
    )
    last_connected_time = user_presence_datetime_with_date_joined_default(
        presence.last_connected_time, user_profile.date_joined
    )

    # The mobile app handles these events so we need to use the old format.
    # The format of the event should also account for the slim_presence
    # API parameter when this becomes possible in the future.
    presence_dict = format_legacy_presence_dict(last_active_time, last_connected_time)
    event = dict(
        type="presence",
        email=user_profile.email,
        user_id=user_profile.id,
        server_timestamp=time.time(),
        presence={presence_dict["client"]: presence_dict},
    )
    send_event_rollback_unsafe(user_profile.realm, event, user_ids)


def consolidate_client(client: Client) -> Client:
    # The web app reports a client as 'website'
    # The desktop app reports a client as ZulipDesktop
    # due to it setting a custom user agent. We want both
    # to count as web users

    # Alias ZulipDesktop to website
    if client.name in ["ZulipDesktop"]:
        return get_client("website")
    else:
        return client


# This function takes a very hot lock on the PresenceSequence row for the user's realm.
# Since all presence updates in the realm all compete for this lock, we need to be
# maximally efficient and only hold it as briefly as possible.
# For that reason, we need durable=True to ensure we're not running inside a larger
# transaction, which may stay alive longer than we'd like, holding the lock.
@transaction.atomic(durable=True)
def do_update_user_presence(
    user_profile: UserProfile,
    client: Client,
    log_time: datetime,
    status: int,
    *,
    force_send_update: bool = False,
) -> None:
    # This function requires some careful handling around setting the
    # last_update_id field when updatng UserPresence objects. See the
    # PresenceSequence model and the comments throughout the code for more details.

    client = consolidate_client(client)

    # If the user doesn't have a UserPresence row yet, we create one with
    # sensible defaults. If we're getting a presence update, clearly the user
    # at least connected, so last_connected_time should be set. last_active_time
    # will depend on whether the status sent is idle or active.
    defaults = dict(
        last_active_time=None,
        last_connected_time=log_time,
        realm_id=user_profile.realm_id,
    )
    if status == UserPresence.LEGACY_STATUS_ACTIVE_INT:
        defaults["last_active_time"] = log_time

    try:
        presence = UserPresence.objects.select_for_update().get(user_profile=user_profile)
        creating = False
    except UserPresence.DoesNotExist:
        # We're not ready to write until we know the next last_update_id value.
        # We don't want to hold the lock on PresenceSequence for too long,
        # so we defer that until the last moment.
        # Create the presence object in-memory only for now.
        presence = UserPresence(**defaults, user_profile=user_profile)
        creating = True

    # We initialize these values as a large delta so that if the user
    # was never active, we always treat the user as newly online.
    time_since_last_active_for_comparison = timedelta(days=1)
    time_since_last_connected_for_comparison = timedelta(days=1)
    if presence.last_active_time is not None:
        time_since_last_active_for_comparison = log_time - presence.last_active_time
    if presence.last_connected_time is not None:
        time_since_last_connected_for_comparison = log_time - presence.last_connected_time

    assert (3 * settings.PRESENCE_PING_INTERVAL_SECS + 20) <= settings.OFFLINE_THRESHOLD_SECS
    now_online = time_since_last_active_for_comparison > timedelta(
        # Here, we decide whether the user is newly online, and we need to consider
        # sending an immediate presence update via the events system that this user is now online,
        # rather than waiting for other clients to poll the presence update.
        # Sending these presence update events adds load to the system, so we only want to do this
        # if the user has missed a couple regular presence check-ins
        # (so their state is at least 2 * PRESENCE_PING_INTERVAL_SECS + 10 old),
        # and also is under the risk of being shown by clients as offline before the next regular presence check-in
        # (so at least `settings.OFFLINE_THRESHOLD_SECS - settings.PRESENCE_PING_INTERVAL_SECS - 10`).
        # These two values happen to be the same in the default configuration.
        seconds=settings.OFFLINE_THRESHOLD_SECS - settings.PRESENCE_PING_INTERVAL_SECS - 10
    )
    became_online = status == UserPresence.LEGACY_STATUS_ACTIVE_INT and now_online

    update_fields = []

    # This check is to prevent updating `last_connected_time` several
    # times per minute with multiple connected browser windows.
    # We also need to be careful not to wrongly "update" the timestamp if we actually already
    # have newer presence than the reported log_time.
    if not creating and time_since_last_connected_for_comparison > timedelta(
        seconds=settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS
    ):
        presence.last_connected_time = log_time
        update_fields.append("last_connected_time")
    if (
        not creating
        and status == UserPresence.LEGACY_STATUS_ACTIVE_INT
        and time_since_last_active_for_comparison
        > timedelta(seconds=settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS)
    ):
        presence.last_active_time = log_time
        update_fields.append("last_active_time")
        if presence.last_connected_time is None or log_time > presence.last_connected_time:
            # Update last_connected_time as well to ensure
            # last_connected_time >= last_active_time.
            presence.last_connected_time = log_time
            update_fields.append("last_connected_time")

    # WARNING: Delicate, performance-sensitive block.

    # It's time to determine last_update_id and update the presence object in the database.
    # This briefly takes the crucial lock on the PresenceSequence row for the user's realm.
    # We're doing this in a single SQL query to avoid any unnecessary overhead, in particular
    # database round-trips.
    # We're also intentionally doing this at the very end of the function, at the last step
    # before the transaction commits. This ensures the lock is held for the shortest
    # time possible.
    # Note: The lock isn't acquired explicitly via something like SELECT FOR UPDATE,
    # but rather we rely on the UPDATE statement taking an implicit row lock.

    # Equivalent Python code:
    # if creating or len(update_fields) > 0:
    #     presence_sequence = PresenceSequence.objects.select_for_update().get(realm_id=user_profile.realm_id)
    #     new_last_update_id = presence_sequence.last_update_id + 1
    #     presence_sequence.last_update_id = new_last_update_id
    #     if creating:
    #         presence.last_update_id = new_last_update_id
    #         presence.save()
    #     elif len(update_fields) > 0:
    #         presence.last_update_id = new_last_update_id
    #         presence.save(update_fields=[*update_fields, "last_update_id"])
    #     presence_sequence.save(update_fields=["last_update_id"])
    # But let's do it in a single, direct SQL query instead.

    if creating or len(update_fields) > 0:
        query = sql.SQL("""
            WITH new_last_update_id AS (
                UPDATE zerver_presencesequence
                SET last_update_id = last_update_id + 1
                WHERE realm_id = {realm_id}
                RETURNING last_update_id
            )
        """).format(realm_id=sql.Literal(user_profile.realm_id))

        if creating:
            # There's a small possibility of a race where a different process may have
            # already created a row for this user. Given the extremely close timing
            # of these events, there's no clear reason to prefer one over the other,
            # so we choose the simplest option of DO NOTHING here and let the other
            # concurrent transaction win.
            # This also allows us to avoid sending a spurious presence update event,
            # by checking if the row was actually created.
            query += sql.SQL("""
                INSERT INTO zerver_userpresence (user_profile_id, last_active_time, last_connected_time, realm_id, last_update_id)
                VALUES ({user_profile_id}, {last_active_time}, {last_connected_time}, {realm_id}, (SELECT last_update_id FROM new_last_update_id))
                ON CONFLICT (user_profile_id) DO NOTHING
                """).format(
                user_profile_id=sql.Literal(user_profile.id),
                last_active_time=sql.Literal(presence.last_active_time),
                last_connected_time=sql.Literal(presence.last_connected_time),
                realm_id=sql.Literal(user_profile.realm_id),
            )
        else:
            assert len(update_fields) > 0
            update_fields_segment = sql.SQL(", ").join(
                sql.SQL("{field} = {value}  ").format(
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
                # Check if the row was actually created or if we
                # hit the ON CONFLICT DO NOTHING case.
                actually_created = cursor.rowcount > 0

    if creating and not actually_created:
        # If we ended up doing nothing due to something else creating the row
        # in the meantime, then we shouldn't send an event here.
        logger.info("UserPresence row already created for %s, returning.", user_profile.id)
        return

    if force_send_update or (
        not user_profile.realm.presence_disabled and (creating or became_online)
    ):
        # We do the transaction.on_commit here, rather than inside
        # send_presence_changed, to help keep presence transactions
        # brief; the active_user_ids call there is more expensive than
        # this whole function.
        transaction.on_commit(
            lambda: send_presence_changed(
                user_profile, presence, force_send_update=force_send_update
            )
        )


def update_user_presence(
    user_profile: UserProfile,
    client: Client,
    log_time: datetime,
    status: int,
    new_user_input: bool,
) -> None:
    logger.debug(
        "Processing presence update for user %s, client %s, status %s",
        user_profile.id,
        client,
        status,
    )
    if user_profile.presence_enabled:
        do_update_user_presence(user_profile, client, log_time, status)
    if new_user_input:
        update_user_activity_interval(user_profile, log_time)

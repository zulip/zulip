import time
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction

from zerver.actions.user_activity import update_user_activity_interval
from zerver.lib.presence import (
    format_legacy_presence_dict,
    user_presence_datetime_with_date_joined_default,
)
from zerver.lib.queue import queue_json_publish
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.users import get_user_ids_who_can_access_user
from zerver.models import Client, UserPresence, UserProfile
from zerver.models.clients import get_client
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event


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
    # See https://zulip.readthedocs.io/en/latest/subsystems/presence.html for
    # internals documentation on presence.
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
    send_event(user_profile.realm, event, user_ids)


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


@transaction.atomic(savepoint=False)
def do_update_user_presence(
    user_profile: UserProfile,
    client: Client,
    log_time: datetime,
    status: int,
    *,
    force_send_update: bool = False,
) -> None:
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

    (presence, created) = UserPresence.objects.get_or_create(
        user_profile=user_profile,
        defaults=defaults,
    )

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
        # if the user has missed a couple regular presence checkins
        # (so their state is at least 2 * PRESENCE_PING_INTERVAL_SECS + 10 old),
        # and also is under the risk of being shown by clients as offline before the next regular presence checkin
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
    if not created and time_since_last_connected_for_comparison > timedelta(
        seconds=settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS
    ):
        presence.last_connected_time = log_time
        update_fields.append("last_connected_time")
    if (
        not created
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
    if len(update_fields) > 0:
        presence.save(update_fields=update_fields)

    if force_send_update or (
        not user_profile.realm.presence_disabled and (created or became_online)
    ):
        # We do a the transaction.on_commit here, rather than inside
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
    event = {
        "user_profile_id": user_profile.id,
        "status": status,
        "time": datetime_to_timestamp(log_time),
        "client": client.name,
    }

    queue_json_publish("user_presence", event)

    if new_user_input:
        update_user_activity_interval(user_profile, log_time)

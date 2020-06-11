import datetime
import time

from django.conf import settings
from django.db import transaction

from zerver.actions.user_activity import update_user_activity_interval
from zerver.lib.presence import format_legacy_presence_dict
from zerver.lib.queue import queue_json_publish
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import Client, UserPresence, UserProfile, active_user_ids, get_client
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

    # The mobile app handles these events so we need to use the old format.
    # The format of the event should also account for the slim_presence
    # API parameter when this becomes possible in the future.
    presence_dict = format_legacy_presence_dict(presence)
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


def do_update_user_presence(
    user_profile: UserProfile,
    client: Client,
    log_time: datetime.datetime,
    status: int,
    *,
    force_send_update: bool = False,
) -> None:
    client = consolidate_client(client)

    # TODO: While we probably DO want creating an account to
    # automatically create a first `UserPresence` object with
    # last_connected_time and last_active_time as the current time,
    # our presence tests don't understand this, and it'd be perhaps
    # wrong for some cases of account creation via the API.  So we may
    # want a "never" value here as the default.
    defaults = dict(
        # Given that these are defaults for creation of a UserPresence row
        # if one doesn't yet exist, the most sensible way to do this
        # is to set both last_active_time and last_connected_time
        # to log_time.
        last_active_time=log_time,
        last_connected_time=log_time,
        realm_id=user_profile.realm_id,
    )
    if status == UserPresence.LEGACY_STATUS_IDLE_INT:
        # If the presence entry for the user is just to be created, and
        # we want it to be created as idle, then there needs to be an appropriate
        # offset between last_active_time and last_connected_time, since that's
        # what the event-sending system calculates the status based on, via
        # format_legacy_presence_dict.
        defaults["last_active_time"] = log_time - datetime.timedelta(
            seconds=settings.PRESENCE_LEGACY_EVENT_OFFSET_FOR_ACTIVITY_SECONDS + 1
        )

    (presence, created) = UserPresence.objects.get_or_create(
        user_profile=user_profile,
        defaults=defaults,
    )

    time_since_last_active = log_time - presence.last_active_time

    assert (3 * settings.PRESENCE_PING_INTERVAL_SECS + 20) <= settings.OFFLINE_THRESHOLD_SECS
    now_online = time_since_last_active > datetime.timedelta(
        # Here, we decide whether the user is newly online, and we need to consider
        # sending an immediate presence update via the events system that this user is now online,
        # rather than waiting for other clients to poll the presence update.
        # Sending these presence update events adds load to the system, so we only want to do this
        # if the user has missed a couple regular presence checkins
        # (so their state is at least 2 * PRESENCE_PING_INTERVAL_SECS + 10 old),
        # and also is under the risk of being shown by clients as offline before the next regular presence checkin
        # (so at least `settings.OFFLINE_THRESHOLD_SECS - settings.PRESENCE_PING_INTERVAL_SECS - 10`).
        # These two values happen to be the same in the default configuration.
        seconds=settings.OFFLINE_THRESHOLD_SECS
        - settings.PRESENCE_PING_INTERVAL_SECS
        - 10
    )
    became_online = status == UserPresence.LEGACY_STATUS_ACTIVE_INT and now_online

    update_fields = []

    # This check is to prevent updating `last_connected_time` several
    # times per minute with multiple connected browser windows.
    # We also need to be careful not to wrongly "update" the timestamp if we actually already
    # have newer presence than the reported log_time.
    if not created and log_time - presence.last_connected_time > datetime.timedelta(
        seconds=settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS
    ):
        presence.last_connected_time = log_time
        update_fields.append("last_connected_time")
    if (
        not created
        and status == UserPresence.LEGACY_STATUS_ACTIVE_INT
        and time_since_last_active
        > datetime.timedelta(seconds=settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS)
    ):
        presence.last_active_time = log_time
        update_fields.append("last_active_time")
        if log_time > presence.last_connected_time:
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
    log_time: datetime.datetime,
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

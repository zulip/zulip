import datetime
import time
from typing import Optional

from django.conf import settings

from zerver.actions.user_activity import update_user_activity_interval
from zerver.decorator import statsd_increment
from zerver.lib.queue import queue_json_publish
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_status import update_user_status
from zerver.models import Client, UserPresence, UserProfile, UserStatus, active_user_ids, get_client
from zerver.tornado.django_api import send_event


def send_presence_changed(user_profile: UserProfile, presence: UserPresence) -> None:
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
    if len(user_ids) > settings.USER_LIMIT_FOR_SENDING_PRESENCE_UPDATE_EVENTS:
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

    presence_dict = presence.to_dict()
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


@statsd_increment("user_presence")
def do_update_user_presence(
    user_profile: UserProfile, client: Client, log_time: datetime.datetime, status: int
) -> None:
    client = consolidate_client(client)

    defaults = dict(
        timestamp=log_time,
        status=status,
        realm_id=user_profile.realm_id,
    )

    (presence, created) = UserPresence.objects.get_or_create(
        user_profile=user_profile,
        client=client,
        defaults=defaults,
    )

    stale_status = (log_time - presence.timestamp) > datetime.timedelta(minutes=1, seconds=10)
    was_idle = presence.status == UserPresence.IDLE
    became_online = (status == UserPresence.ACTIVE) and (stale_status or was_idle)

    # If an object was created, it has already been saved.
    #
    # We suppress changes from ACTIVE to IDLE before stale_status is reached;
    # this protects us from the user having two clients open: one active, the
    # other idle. Without this check, we would constantly toggle their status
    # between the two states.
    if not created and stale_status or was_idle or status == presence.status:
        # The following block attempts to only update the "status"
        # field in the event that it actually changed.  This is
        # important to avoid flushing the UserPresence cache when the
        # data it would return to a client hasn't actually changed
        # (see the UserPresence post_save hook for details).
        presence.timestamp = log_time
        update_fields = ["timestamp"]
        if presence.status != status:
            presence.status = status
            update_fields.append("status")
        presence.save(update_fields=update_fields)

    if not user_profile.realm.presence_disabled and (created or became_online):
        send_presence_changed(user_profile, presence)


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


def do_update_user_status(
    user_profile: UserProfile,
    away: Optional[bool],
    status_text: Optional[str],
    client_id: int,
    emoji_name: Optional[str],
    emoji_code: Optional[str],
    reaction_type: Optional[str],
) -> None:
    if away is None:
        status = None
    elif away:
        status = UserStatus.AWAY
    else:
        status = UserStatus.NORMAL

    realm = user_profile.realm

    update_user_status(
        user_profile_id=user_profile.id,
        status=status,
        status_text=status_text,
        client_id=client_id,
        emoji_name=emoji_name,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
    )

    event = dict(
        type="user_status",
        user_id=user_profile.id,
    )

    if away is not None:
        event["away"] = away

    if status_text is not None:
        event["status_text"] = status_text

    if emoji_name is not None:
        event["emoji_name"] = emoji_name
        event["emoji_code"] = emoji_code
        event["reaction_type"] = reaction_type
    send_event(realm, event, active_user_ids(realm.id))

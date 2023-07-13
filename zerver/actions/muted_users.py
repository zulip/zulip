import datetime
from typing import Optional

from django.utils.timezone import now as timezone_now

from zerver.actions.message_flags import do_mark_muted_user_messages_as_read
from zerver.lib.muted_users import add_user_mute, get_user_mutes
from zerver.models import MutedUser, RealmAuditLog, UserProfile
from zerver.tornado.django_api import send_event


def do_mute_user(
    user_profile: UserProfile,
    muted_user: UserProfile,
    date_muted: Optional[datetime.datetime] = None,
) -> None:
    if date_muted is None:
        date_muted = timezone_now()
    add_user_mute(user_profile, muted_user, date_muted)
    do_mark_muted_user_messages_as_read(user_profile, muted_user)
    event = dict(type="muted_users", muted_users=get_user_mutes(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])

    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_MUTED,
        event_time=date_muted,
        extra_data={"muted_user_id": muted_user.id},
    )


def do_unmute_user(mute_object: MutedUser) -> None:
    user_profile = mute_object.user_profile
    muted_user = mute_object.muted_user
    mute_object.delete()
    event = dict(type="muted_users", muted_users=get_user_mutes(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])

    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_UNMUTED,
        event_time=timezone_now(),
        extra_data={"unmuted_user_id": muted_user.id},
    )

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.user_status import check_only_scheduled_end_time_updated, update_user_status
from zerver.lib.users import get_user_ids_who_can_access_user
from zerver.models import UserProfile, UserStatus
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_update_user_status(
    user_profile: UserProfile,
    away: bool | None,
    status_text: str | None,
    client_id: int,
    emoji_name: str | None,
    emoji_code: str | None,
    reaction_type: str | None,
    scheduled_end_time: int | None,
) -> None:
    # Deprecated way for clients to access the user's `presence_enabled`
    # setting, with away != presence_enabled. Can be removed when clients
    # migrate "away" (also referred to as "unavailable") feature to directly
    # use and update the user's presence_enabled setting.
    if away is not None:
        user_setting = "presence_enabled"
        value = not away
        do_change_user_setting(user_profile, user_setting, value, acting_user=user_profile)

    realm = user_profile.realm
    only_scheduled_end_time_updated = False

    if scheduled_end_time is not None:
        only_scheduled_end_time_updated = check_only_scheduled_end_time_updated(
            user_profile, status_text, emoji_name, scheduled_end_time
        )

    update_user_status(
        user_profile_id=user_profile.id,
        status_text=status_text,
        client_id=client_id,
        emoji_name=emoji_name,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
        scheduled_end_time=scheduled_end_time,
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

    user_ids_to_send_event = get_user_ids_who_can_access_user(user_profile)

    if scheduled_end_time is not None:
        send_event_on_commit(
            realm, {**event, "scheduled_end_time": scheduled_end_time}, [user_profile.id]
        )
        user_ids_to_send_event.remove(user_profile.id)

    if not only_scheduled_end_time_updated:
        send_event_on_commit(realm, event, user_ids_to_send_event)


def try_clear_scheduled_user_status() -> bool:
    user_status = (
        UserStatus.objects.filter(scheduled_end_time__lte=timezone_now())
        .order_by("scheduled_end_time")
        .first()
    )
    if user_status is not None:
        do_update_user_status(
            user_profile=user_status.user_profile,
            away=None,
            status_text="",
            client_id=user_status.client_id,
            emoji_name="",
            emoji_code="",
            reaction_type=UserStatus.UNICODE_EMOJI,
            scheduled_end_time=None,
        )
        return True

    return False

from datetime import datetime
from typing import TypedDict

from django.db.models import Q
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.users import check_user_can_access_all_users, get_accessible_user_ids
from zerver.models import Realm, UserProfile, UserStatus


class UserInfoDict(TypedDict, total=False):
    status_text: str
    emoji_name: str
    emoji_code: str
    reaction_type: str
    scheduled_end_time: int
    away: bool


class RawUserInfoDict(TypedDict):
    user_profile_id: int
    user_profile__presence_enabled: bool
    status_text: str
    emoji_name: str
    emoji_code: str
    reaction_type: str
    scheduled_end_time: datetime | None


def format_user_status(user_id: int, row: RawUserInfoDict) -> UserInfoDict:
    # Deprecated way for clients to access the user's `presence_enabled`
    # setting, with away != presence_enabled. Can be removed when clients
    # migrate "away" (also referred to as "unavailable") feature to directly
    # use and update the user's presence_enabled setting.
    presence_enabled = row["user_profile__presence_enabled"]
    away = not presence_enabled
    status_text = row["status_text"]
    scheduled_end_time = row["scheduled_end_time"]
    emoji_name = row["emoji_name"]
    emoji_code = row["emoji_code"]
    reaction_type = row["reaction_type"]

    dct: UserInfoDict = {}
    if away:
        dct["away"] = away
    if status_text:
        dct["status_text"] = status_text
    if emoji_name:
        dct["emoji_name"] = emoji_name
        dct["emoji_code"] = emoji_code
        dct["reaction_type"] = reaction_type
    if row["user_profile_id"] == user_id and scheduled_end_time:
        dct["scheduled_end_time"] = datetime_to_timestamp(scheduled_end_time)

    return dct


def get_all_users_status_dict(realm: Realm, user_profile: UserProfile) -> dict[str, UserInfoDict]:
    query = UserStatus.objects.filter(
        user_profile__realm_id=realm.id,
        user_profile__is_active=True,
    ).exclude(
        Q(user_profile__presence_enabled=True)
        & Q(status_text="")
        & Q(emoji_name="")
        & Q(emoji_code="")
        & Q(reaction_type=UserStatus.UNICODE_EMOJI),
    )

    if not check_user_can_access_all_users(user_profile):
        accessible_user_ids = get_accessible_user_ids(realm, user_profile)
        query = query.filter(user_profile_id__in=accessible_user_ids)

    rows = query.values(
        "user_profile_id",
        "user_profile__presence_enabled",
        "status_text",
        "emoji_name",
        "emoji_code",
        "reaction_type",
        "scheduled_end_time",
    )

    user_dict: dict[str, UserInfoDict] = {}
    for row in rows:
        user_id = row["user_profile_id"]
        user_dict[str(user_id)] = format_user_status(user_profile.id, row)

    return user_dict


def update_user_status(
    user_profile_id: int,
    status_text: str | None,
    client_id: int,
    emoji_name: str | None,
    emoji_code: str | None,
    reaction_type: str | None,
    scheduled_end_time: int | None,
) -> None:
    timestamp = timezone_now()

    defaults = dict(
        client_id=client_id,
        timestamp=timestamp,
    )

    if status_text is not None:
        defaults["status_text"] = status_text

    if emoji_name is not None:
        defaults["emoji_name"] = emoji_name

        if emoji_code is not None:
            defaults["emoji_code"] = emoji_code

        if reaction_type is not None:
            defaults["reaction_type"] = reaction_type

    if scheduled_end_time is not None:
        defaults["scheduled_end_time"] = timestamp_to_datetime(scheduled_end_time)
    else:
        defaults["scheduled_end_time"] = None

    UserStatus.objects.update_or_create(
        user_profile_id=user_profile_id,
        defaults=defaults,
    )


def get_user_status(user_profile: UserProfile) -> UserInfoDict:
    status_set_by_user = (
        UserStatus.objects.filter(user_profile=user_profile)
        .values(
            "user_profile_id",
            "user_profile__presence_enabled",
            "status_text",
            "emoji_name",
            "emoji_code",
            "reaction_type",
            "scheduled_end_time",
        )
        .first()
    )

    if not status_set_by_user:
        return {}
    return format_user_status(user_profile.id, status_set_by_user)


def user_has_status_set(status_text: str | None, emoji_name: str | None) -> bool:
    no_status_emoji_values = ["", None]
    if status_text in no_status_emoji_values and emoji_name in no_status_emoji_values:
        return False
    return True


def check_only_scheduled_end_time_updated(
    user_profile: UserProfile,
    status_text: str | None,
    emoji_name: str | None,
    scheduled_end_time: int | None,
) -> bool:
    current_status = get_user_status(user_profile)
    old_status_text = current_status.get("status_text")
    old_emoji_name = current_status.get("emoji_name")

    if (
        status_text is None
        and emoji_name is None
        and not user_has_status_set(old_status_text, old_emoji_name)
    ):
        raise JsonableError(_("Client does not have any status set."))

    if (status_text is not None and status_text != old_status_text) or (
        emoji_name is not None and emoji_name != old_emoji_name
    ):
        return False

    return True

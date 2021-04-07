import datetime
from typing import Dict, List

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import MutedUser, UserProfile


def get_user_mutes(user_profile: UserProfile) -> List[Dict[str, int]]:
    rows = MutedUser.objects.filter(user_profile=user_profile).values(
        "muted_user__id",
        "date_muted",
    )
    return [
        {
            "id": row["muted_user__id"],
            "timestamp": datetime_to_timestamp(row["date_muted"]),
        }
        for row in rows
    ]


def add_user_mute(
    user_profile: UserProfile, muted_user: UserProfile, date_muted: datetime.datetime
) -> None:
    MutedUser.objects.create(
        user_profile=user_profile,
        muted_user=muted_user,
        date_muted=date_muted,
    )


def remove_user_mute(user_profile: UserProfile, muted_user: UserProfile) -> None:
    MutedUser.objects.get(user_profile=user_profile, muted_user=muted_user).delete()


def user_is_muted(user_profile: UserProfile, muted_user: UserProfile) -> bool:
    return MutedUser.objects.filter(user_profile=user_profile, muted_user=muted_user).exists()

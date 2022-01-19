import datetime
from typing import Dict, List, Optional, Set

from zerver.lib.cache import cache_with_key, get_muting_users_cache_key
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.utils import assert_is_not_none
from zerver.models import MutedUser, UserProfile


def get_user_mutes(user_profile: UserProfile) -> List[Dict[str, int]]:
    rows = MutedUser.objects.filter(user_profile=user_profile).values(
        "muted_user_id",
        "date_muted",
    )
    return [
        {
            "id": row["muted_user_id"],
            "timestamp": datetime_to_timestamp(assert_is_not_none(row["date_muted"])),
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


def get_mute_object(user_profile: UserProfile, muted_user: UserProfile) -> Optional[MutedUser]:
    try:
        return MutedUser.objects.get(user_profile=user_profile, muted_user=muted_user)
    except MutedUser.DoesNotExist:
        return None


@cache_with_key(get_muting_users_cache_key, timeout=3600 * 24 * 7)
def get_muting_users(muted_user_id: int) -> Set[int]:
    """
    This is kind of the inverse of `get_user_mutes` above.
    While `get_user_mutes` is mainly used for event system work,
    this is used in the message send codepath, to get a list
    of IDs of users who have muted a particular user.
    The result will also include deactivated users.
    """
    rows = MutedUser.objects.filter(
        muted_user_id=muted_user_id,
    ).values("user_profile_id")
    return {row["user_profile_id"] for row in rows}

from datetime import datetime

from zerver.lib.cache import cache_with_key, get_followed_users_cache_key
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import FollowedUser, UserProfile


def get_user_follows(user_profile: UserProfile) -> list[dict[str, int]]:
    return [
        {"id": follow.followed_user_id, "timestamp": datetime_to_timestamp(follow.date_followed)}
        for follow in FollowedUser.objects.filter(user_profile=user_profile)
    ]


def add_user_follow(
    user_profile: UserProfile, followed_user: UserProfile, date_followed: datetime
) -> None:
    FollowedUser.objects.create(
        user_profile=user_profile, followed_user=followed_user, date_followed=date_followed
    )


def get_follow_object(user_profile: UserProfile, followed_user: UserProfile) -> FollowedUser | None:
    return FollowedUser.objects.filter(
        user_profile=user_profile, followed_user=followed_user
    ).first()


@cache_with_key(get_followed_users_cache_key, timeout=3600 * 24 * 7)
def get_following_users(followed_user_id: int) -> set[int]:
    return set(
        FollowedUser.objects.filter(followed_user_id=followed_user_id).values_list(
            "user_profile_id", flat=True
        )
    )


def get_following_user_ids(user_profile_id: int) -> list[int]:
    """Return the IDs of all users that user_profile_id is following.

    This is the inverse of get_following_users(): instead of returning who
    follows a given user, this returns who a given user follows.

    Used by the `is:followed-user` narrow to filter messages by sender.
    """
    return list(
        FollowedUser.objects.filter(user_profile_id=user_profile_id).values_list(
            "followed_user_id", flat=True
        )
    )

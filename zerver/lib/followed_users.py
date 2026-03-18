from datetime import datetime
from zerver.lib.cache import cache_with_key, get_followed_users_cache_key
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import UserProfile, FollowedUser

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

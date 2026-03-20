from datetime import datetime

from zerver.lib.cache import cache_with_key, get_followed_users_cache_key
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import FollowedUser, Recipient, Subscription, UserProfile


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


def get_followers_who_can_see_stream_message(
    followed_user_id: int, stream_id: int, realm_id: int
) -> set[int]:
    """
    Get followers of a user who have followed user push notifications enabled
    and have access to a specific stream.

    This is used to determine which users should receive notifications when
    the followed user posts a message to a stream.

    Args:
        followed_user_id: ID of the user being followed
        stream_id: ID of the stream where message is being posted
        realm_id: ID of the realm (for permission filtering)

    Returns:
        Set of user IDs (followers) who should be notified
    """
    # Get all followers with push notifications enabled
    followers_with_push = FollowedUser.objects.filter(
        followed_user_id=followed_user_id,
        user_profile__enable_followed_user_push_notifications=True,
    ).values_list("user_profile_id", flat=True)

    # Get the stream recipient and its subscribers
    try:
        recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream_id)
    except Recipient.DoesNotExist:
        # Stream doesn't exist or was deleted
        return set()

    # Get subscribers to the stream
    stream_subscribers = Subscription.objects.filter(recipient=recipient, active=True).values_list(
        "user_profile_id", flat=True
    )

    # Return intersection: followers with push notifications AND subscribers to the stream
    return set(followers_with_push) & set(stream_subscribers)

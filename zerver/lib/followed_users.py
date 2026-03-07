from datetime import datetime
from zerver.models import UserProfile

def get_user_follows(user_profile: UserProfile) -> list[dict[str, int]]:
    # TODO: Fetch follows from database once model is implemented
    return []

def add_user_follow(
    user_profile: UserProfile, followed_user: UserProfile, date_followed: datetime
) -> None:
    # TODO: Save follow to database once model is implemented
    pass

def get_follow_object(user_profile: UserProfile, followed_user: UserProfile) -> object | None:
    # TODO: Fetch follow object from database once model is implemented
    return None

def get_following_users(followed_user_id: int) -> set[int]:
    # TODO: Fetch followers from database once model is implemented
    return set()

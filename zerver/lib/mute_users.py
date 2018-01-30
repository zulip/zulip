from typing import Any, Tuple, Callable, Dict, List, Optional, Text

from zerver.models import (
    MutedUser,
    UserProfile
)
from sqlalchemy.sql import (
    and_,
    column,
    func,
    not_,
    or_,
    Selectable
)

def get_user_mutes(user_profile: UserProfile) -> List[List[Any]]:
    rows = MutedUser.objects.filter(
        user_profile=user_profile,
    )
    return [
        [row.muted_user_profile.id, row.muted_user_profile.full_name]
        for row in rows
    ]

def add_user_mute(user_profile: UserProfile, muted_user_profile: UserProfile) -> None:
    MutedUser.objects.create(
        user_profile=user_profile,
        muted_user_profile=muted_user_profile
    )

def remove_user_mute(user_profile: UserProfile, muted_user_profile: UserProfile) -> None:
    row = MutedUser.objects.get(
        user_profile=user_profile,
        muted_user_profile=muted_user_profile
    )
    row.delete()

def user_is_muted(user_profile: UserProfile, muted_user_profile: UserProfile) -> bool:
    is_muted = MutedUser.objects.filter(
        user_profile=user_profile,
        muted_user_profile=muted_user_profile
    ).exists()
    return is_muted

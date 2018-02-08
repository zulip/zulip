from typing import Any, Tuple, Callable, Dict, List, Optional, Text

from zerver.models import (
    MutedUser,
    UserProfile
)

def get_user_mutes(user_profile: UserProfile) -> List[Dict[Text, Any]]:
    rows = MutedUser.objects.filter(
        user_profile=user_profile,
    )
    return [
        {'id': row.muted_user_profile.id, 'name': row.muted_user_profile.full_name}
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

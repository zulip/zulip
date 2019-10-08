from django.utils.timezone import now as timezone_now

from zerver.models import (
    UserStatus,
)

from typing import Set

def get_away_user_ids(realm_id: int) -> Set[int]:
    user_ids = UserStatus.objects.filter(
        status=UserStatus.AWAY,
        user_profile__realm_id=realm_id,
        user_profile__is_active=True,
    ).values_list('user_profile_id', flat=True)

    return set(user_ids)

def set_away_status(user_profile_id: int,
                    client_id: int) -> None:

    timestamp = timezone_now()
    status = UserStatus.AWAY

    UserStatus.objects.update_or_create(
        user_profile_id=user_profile_id,
        defaults=dict(
            client_id=client_id,
            timestamp=timestamp,
            status=status,
        ),
    )

def revoke_away_status(user_profile_id: int) -> None:
    UserStatus.objects.filter(
        user_profile_id=user_profile_id,
    ).delete()

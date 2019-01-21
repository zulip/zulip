from django.db.models import Q
from django.utils.timezone import now as timezone_now

from zerver.models import (
    UserStatus,
)

from typing import Any, Dict, Optional

def get_user_info_dict(realm_id: int) -> Dict[int, Dict[str, Any]]:
    rows = UserStatus.objects.filter(
        user_profile__realm_id=realm_id,
        user_profile__is_active=True,
    ).exclude(
        Q(status=UserStatus.NORMAL) &
        Q(status_text='')
    ).values(
        'user_profile_id',
        'status',
        'status_text',
    )

    user_dict = dict()  # type: Dict[int, Dict[str, Any]]
    for row in rows:
        away = row['status'] == UserStatus.AWAY
        status_text = row['status_text']
        user_id = row['user_profile_id']

        dct = dict()
        if away:
            dct['away'] = away
        if status_text:
            dct['status_text'] = status_text

        user_dict[user_id] = dct

    return user_dict

def update_user_status(user_profile_id: int,
                       status: Optional[int],
                       status_text: Optional[str],
                       client_id: int) -> None:

    timestamp = timezone_now()

    defaults = dict(
        client_id=client_id,
        timestamp=timestamp,
    )

    if status is not None:
        defaults['status'] = status

    if status_text is not None:
        defaults['status_text'] = status_text

    UserStatus.objects.update_or_create(
        user_profile_id=user_profile_id,
        defaults=defaults,
    )

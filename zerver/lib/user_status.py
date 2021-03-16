from typing import Any, Dict, Optional

from django.db.models import Q
from django.utils.timezone import now as timezone_now

from zerver.models import UserStatus


def get_user_info_dict(realm_id: int) -> Dict[str, Dict[str, Any]]:
    rows = (
        UserStatus.objects.filter(
            user_profile__realm_id=realm_id,
            user_profile__is_active=True,
        )
        .exclude(
            Q(status=UserStatus.NORMAL) & Q(status_text="") & Q(status_emoji=""),
        )
        .values(
            "user_profile_id",
            "status",
            "status_text",
            "status_emoji",
        )
    )

    user_dict: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        away = row["status"] == UserStatus.AWAY
        status_text = row["status_text"]
        status_emoji = row["status_emoji"]
        user_id = row["user_profile_id"]

        dct = {}
        if away:
            dct["away"] = away
        if status_text:
            dct["status_text"] = status_text
        if status_emoji:
            dct["status_emoji"] = status_emoji

        user_dict[str(user_id)] = dct

    return user_dict


def update_user_status(
    user_profile_id: int,
    status: Optional[int],
    status_text: Optional[str],
    status_emoji: Optional[str],
    client_id: int,
) -> None:

    timestamp = timezone_now()

    defaults = dict(
        client_id=client_id,
        timestamp=timestamp,
    )

    if status is not None:
        defaults["status"] = status

    if status_text is not None:
        defaults["status_text"] = status_text

    if status_emoji is not None:
        defaults["status_emoji"] = status_emoji

    UserStatus.objects.update_or_create(
        user_profile_id=user_profile_id,
        defaults=defaults,
    )

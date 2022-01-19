from typing import Any, Dict, Optional

from django.db.models import Q
from django.utils.timezone import now as timezone_now

from zerver.models import UserStatus


def format_user_status(row: Dict[str, Any]) -> Dict[str, Any]:
    away = row["status"] == UserStatus.AWAY
    status_text = row["status_text"]
    emoji_name = row["emoji_name"]
    emoji_code = row["emoji_code"]
    reaction_type = row["reaction_type"]

    dct = {}
    if away:
        dct["away"] = away
    if status_text:
        dct["status_text"] = status_text
    if emoji_name:
        dct["emoji_name"] = emoji_name
        dct["emoji_code"] = emoji_code
        dct["reaction_type"] = reaction_type

    return dct


def get_user_info_dict(realm_id: int) -> Dict[str, Dict[str, Any]]:
    rows = (
        UserStatus.objects.filter(
            user_profile__realm_id=realm_id,
            user_profile__is_active=True,
        )
        .exclude(
            Q(status=UserStatus.NORMAL)
            & Q(status_text="")
            & Q(emoji_name="")
            & Q(emoji_code="")
            & Q(reaction_type=UserStatus.UNICODE_EMOJI),
        )
        .values(
            "user_profile_id",
            "status",
            "status_text",
            "emoji_name",
            "emoji_code",
            "reaction_type",
        )
    )

    user_dict: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        user_id = row["user_profile_id"]
        user_dict[str(user_id)] = format_user_status(row)

    return user_dict


def update_user_status(
    user_profile_id: int,
    status: Optional[int],
    status_text: Optional[str],
    client_id: int,
    emoji_name: Optional[str],
    emoji_code: Optional[str],
    reaction_type: Optional[str],
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

    if emoji_name is not None:
        defaults["emoji_name"] = emoji_name

        if emoji_code is not None:
            defaults["emoji_code"] = emoji_code

        if reaction_type is not None:
            defaults["reaction_type"] = reaction_type

    UserStatus.objects.update_or_create(
        user_profile_id=user_profile_id,
        defaults=defaults,
    )

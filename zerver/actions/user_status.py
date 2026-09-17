from typing import cast

from django.db import transaction
from typing_extensions import Required, TypedDict

from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.event_types import ReactionType, UserStatusEvent
from zerver.lib.user_status import update_user_status
from zerver.lib.users import get_user_ids_who_can_access_user
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


class UserStatusEventDict(TypedDict, total=False):
    user_id: Required[int]
    away: bool
    status_text: str
    emoji_name: str
    emoji_code: str | None
    reaction_type: ReactionType | None


@transaction.atomic(durable=True)
def do_update_user_status(
    user_profile: UserProfile,
    away: bool | None,
    status_text: str | None,
    client_id: int,
    emoji_name: str | None,
    emoji_code: str | None,
    reaction_type: str | None,
) -> None:
    # Deprecated way for clients to access the user's `presence_enabled`
    # setting, with away != presence_enabled. Can be removed when clients
    # migrate "away" (also referred to as "unavailable") feature to directly
    # use and update the user's presence_enabled setting.
    if away is not None:
        user_setting = "presence_enabled"
        value = not away
        do_change_user_setting(user_profile, user_setting, value, acting_user=user_profile)

    realm = user_profile.realm

    update_user_status(
        user_profile_id=user_profile.id,
        status_text=status_text,
        client_id=client_id,
        emoji_name=emoji_name,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
    )

    # Only fields the caller explicitly opted into go on the event, so
    # that the serialized event omits keys that weren't requested.
    event: UserStatusEventDict = {"user_id": user_profile.id}

    if away is not None:
        event["away"] = away

    if status_text is not None:
        event["status_text"] = status_text

    if emoji_name is not None:
        event["emoji_name"] = emoji_name
        event["emoji_code"] = emoji_code
        # The Reaction.reaction_type column is restricted to these values via
        # CharField choices, so the cast is safe.
        event["reaction_type"] = cast(ReactionType | None, reaction_type)
    send_event_on_commit(
        realm, UserStatusEvent(**event), get_user_ids_who_can_access_user(user_profile)
    )

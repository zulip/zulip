from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models import Subscription, UserProfile
from zerver.models.recipients import get_direct_message_group
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(savepoint=False)
def do_set_direct_message_group_pin(
    user_profile: UserProfile, other_user_ids: list[int], *, pinned: bool
) -> None:
    # Clients identify a conversation by its other participants ([] for a
    # self-conversation), so add the current user to get the full membership.
    member_ids = {user_profile.id, *other_user_ids}
    direct_message_group = get_direct_message_group(sorted(member_ids))
    if direct_message_group is None or direct_message_group.recipient is None:
        raise JsonableError(_("No such direct message conversation."))

    try:
        subscription = Subscription.objects.get(
            user_profile=user_profile,
            recipient=direct_message_group.recipient,
            active=True,
        )
    except Subscription.DoesNotExist:
        raise JsonableError(_("No such direct message conversation."))

    if subscription.pin_to_top == pinned:
        return

    subscription.pin_to_top = pinned
    subscription.save(update_fields=["pin_to_top"])

    event: dict[str, Any] = {
        "type": "direct_message_conversation",
        "user_ids": sorted(member_ids - {user_profile.id}),
        "pinned": pinned,
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])

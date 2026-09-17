from typing import Literal

from django.db import transaction

from zerver.lib.event_types import BaseEvent, HasWebexTokenEvent, HasZoomTokenEvent
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_set_video_call_provider_token(
    user: UserProfile, token_key: Literal["zoom", "webex"], /, token: dict[str, object] | None
) -> None:
    user.third_party_api_state[token_key] = token
    user.save(update_fields=["third_party_api_state"])
    event: BaseEvent
    if token_key == "zoom":
        event = HasZoomTokenEvent(value=token is not None)
    else:
        event = HasWebexTokenEvent(value=token is not None)
    send_event_on_commit(user.realm, event, [user.id])

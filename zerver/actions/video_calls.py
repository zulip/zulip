from django.db import transaction

from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_set_video_call_provider_token(
    user: UserProfile, token_key: str, /, token: dict[str, object] | None
) -> None:
    user.third_party_api_state[token_key] = token
    user.save(update_fields=["third_party_api_state"])
    send_event_on_commit(
        user.realm,
        dict(type=f"has_{token_key}_token", value=token is not None),
        [user.id],
    )

from django.db import transaction

from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_set_zoom_token(user: UserProfile, /, token: dict[str, object] | None) -> None:
    user.third_party_api_state["zoom"] = token
    user.save(update_fields=["third_party_api_state"])
    send_event_on_commit(
        user.realm,
        dict(type="has_zoom_token", value=token is not None),
        [user.id],
    )

from django.db import transaction

from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_set_zoom_token(user: UserProfile, /, token: dict[str, object] | None) -> None:
    user.zoom_token = token
    user.save(update_fields=["zoom_token"])
    send_event_on_commit(
        user.realm,
        dict(type="has_zoom_token", value=token is not None),
        [user.id],
    )

from typing import Dict, Optional

from zerver.models import UserProfile
from zerver.tornado.django_api import send_event


def do_set_zoom_token(user: UserProfile, token: Optional[Dict[str, object]]) -> None:
    user.zoom_token = token
    user.save(update_fields=["zoom_token"])
    send_event(
        user.realm,
        dict(type="has_zoom_token", value=token is not None),
        [user.id],
    )

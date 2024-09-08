from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic_settings import set_topic_settings_in_database
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(savepoint=False)
def do_set_topic_settings(
    user_profile: UserProfile,
    stream_id: int,
    topic_name: str,
    *,
    is_topic_locked: bool,
    users_to_notify: set[int],
    last_updated: datetime | None = None,
) -> None:
    if last_updated is None:
        last_updated = timezone_now()

    set_topic_settings_in_database(
        user_profile.id,
        user_profile.realm.id,
        stream_id,
        topic_name,
        is_topic_locked,
        last_updated=last_updated,
    )

    topic_settings_event: dict[str, Any] = {
        "type": "topic_settings",
        "stream_id": stream_id,
        "topic_name": topic_name,
        "last_updated": datetime_to_timestamp(last_updated),
        "is_locked": is_topic_locked,
    }

    send_event_on_commit(user_profile.realm, topic_settings_event, users_to_notify)

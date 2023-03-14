import datetime
from typing import Any, Dict, Optional

from django.utils.timezone import now as timezone_now

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_topics import (
    get_topic_mutes,
    set_user_topic_visibility_policy_in_database,
)
from zerver.models import Stream, UserProfile
from zerver.tornado.django_api import send_event


def do_set_user_topic_visibility_policy(
    user_profile: UserProfile,
    stream: Stream,
    topic: str,
    *,
    visibility_policy: int,
    last_updated: Optional[datetime.datetime] = None,
    skip_muted_topics_event: bool = False,
) -> None:
    if last_updated is None:
        last_updated = timezone_now()

    database_changed = set_user_topic_visibility_policy_in_database(
        user_profile,
        stream.id,
        topic,
        visibility_policy=visibility_policy,
        recipient_id=stream.recipient_id,
        last_updated=last_updated,
    )

    # Requests to set the visibility_policy to its current value
    # or to delete a UserTopic row that doesn't exist shouldn't
    # send an unnecessary event.
    if not database_changed:
        return

    # This first muted_topics event is deprecated and will be removed
    # once clients are migrated to handle the user_topic event type
    # instead.
    if not skip_muted_topics_event:
        muted_topics_event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
        send_event(user_profile.realm, muted_topics_event, [user_profile.id])

    user_topic_event: Dict[str, Any] = {
        "type": "user_topic",
        "stream_id": stream.id,
        "topic_name": topic,
        "last_updated": datetime_to_timestamp(last_updated),
        "visibility_policy": visibility_policy,
    }

    send_event(user_profile.realm, user_topic_event, [user_profile.id])

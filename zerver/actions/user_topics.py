import datetime
from typing import Any, Dict, Optional

from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_topics import (
    get_topic_mutes,
    remove_topic_mute,
    set_user_topic_visibility_policy_in_database,
)
from zerver.models import Stream, UserProfile, UserTopic
from zerver.tornado.django_api import send_event


def do_set_user_topic_visibility_policy(
    user_profile: UserProfile,
    stream: Stream,
    topic: str,
    *,
    visibility_policy: int,
    last_updated: Optional[datetime.datetime] = None,
    ignore_duplicate: bool = False,
    skip_muted_topics_event: bool = False,
) -> None:
    if last_updated is None:
        last_updated = timezone_now()

    if visibility_policy == UserTopic.VISIBILITY_POLICY_INHERIT:
        try:
            remove_topic_mute(user_profile, stream.id, topic)
        except UserTopic.DoesNotExist:
            raise JsonableError(_("Topic is not muted"))
    else:
        assert stream.recipient_id is not None
        set_user_topic_visibility_policy_in_database(
            user_profile,
            stream.id,
            topic,
            visibility_policy=visibility_policy,
            recipient_id=stream.recipient_id,
            last_updated=last_updated,
            ignore_duplicate=ignore_duplicate,
        )

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

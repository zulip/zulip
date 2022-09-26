import datetime
from typing import Any, Dict, Optional

from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_topics import add_topic_mute, get_topic_mutes, remove_topic_mute
from zerver.models import Stream, UserProfile, UserTopic
from zerver.tornado.django_api import send_event


def do_mute_topic(
    user_profile: UserProfile,
    stream: Stream,
    topic: str,
    date_muted: Optional[datetime.datetime] = None,
    ignore_duplicate: bool = False,
) -> None:
    if date_muted is None:
        date_muted = timezone_now()
    assert stream.recipient_id is not None
    add_topic_mute(
        user_profile,
        stream.id,
        stream.recipient_id,
        topic,
        date_muted,
        ignore_duplicate=ignore_duplicate,
    )

    # This first muted_topics event is deprecated and will be removed
    # once clients are migrated to handle the user_topic event type
    # instead.
    muted_topics_event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
    send_event(user_profile.realm, muted_topics_event, [user_profile.id])

    user_topic_event: Dict[str, Any] = {
        "type": "user_topic",
        "stream_id": stream.id,
        "topic_name": topic,
        "last_updated": datetime_to_timestamp(date_muted),
        "visibility_policy": UserTopic.MUTED,
    }

    send_event(user_profile.realm, user_topic_event, [user_profile.id])


def do_unmute_topic(
    user_profile: UserProfile, stream: Stream, topic: str, *, skip_muted_topics_event: bool = False
) -> None:
    # Note: If you add any new code to this function, the
    # remove_topic_mute call in do_update_message will need to be
    # updated for correctness.
    try:
        remove_topic_mute(user_profile, stream.id, topic)
    except UserTopic.DoesNotExist:
        raise JsonableError(_("Topic is not muted"))

    # This first muted_topics event is deprecated and will be removed
    # once clients are migrated to handle the user_topic event type
    # instead.
    if not skip_muted_topics_event:
        muted_topics_event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
        send_event(user_profile.realm, muted_topics_event, [user_profile.id])

    date_unmuted = timezone_now()

    user_topic_event: Dict[str, Any] = {
        "type": "user_topic",
        "stream_id": stream.id,
        "topic_name": topic,
        "last_updated": datetime_to_timestamp(date_unmuted),
        "visibility_policy": UserTopic.VISIBILITY_POLICY_INHERIT,
    }

    send_event(user_profile.realm, user_topic_event, [user_profile.id])

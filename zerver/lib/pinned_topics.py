from typing import Any, Dict, List

from zerver.lib.stream_subscription import (
    get_subscribed_stream_ids_for_user,
    get_user_ids_for_stream,
)
from zerver.models import PinnedTopic, UserProfile
from zerver.tornado.django_api import send_event


def get_pinned_topics(user: UserProfile) -> List[Dict[str, Any]]:
    stream_ids = get_subscribed_stream_ids_for_user(user)
    pinned_topics = [
        dict(stream_id=row.stream_id, topic_name=row.topic_name)
        for row in PinnedTopic.objects.filter(stream_id__in=stream_ids)
    ]
    pinned_topics.sort(key=lambda d: (d["stream_id"], d["topic_name"]))
    return pinned_topics


def do_add_pinned_topic(*, user: UserProfile, stream_id: int, topic_name: str) -> None:
    PinnedTopic.objects.create(
        stream_id=stream_id,
        topic_name=topic_name,
    )
    event = dict(type="pinned_topics", op="add", stream_id=stream_id, topic_name=topic_name)
    user_ids = get_user_ids_for_stream(stream_id)
    send_event(user.realm, event, user_ids)


def do_remove_pinned_topic(*, user: UserProfile, stream_id: int, topic_name: str) -> None:
    PinnedTopic.objects.filter(
        stream_id=stream_id,
        topic_name=topic_name,
    ).delete()
    event = dict(type="pinned_topics", op="remove", stream_id=stream_id, topic_name=topic_name)
    user_ids = get_user_ids_for_stream(stream_id)
    send_event(user.realm, event, user_ids)

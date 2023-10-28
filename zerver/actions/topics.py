from zerver.lib.streams import (
    can_access_stream_user_ids,
)
from zerver.models import (
    Topic,
    UserProfile,
    get_stream_by_id_in_realm,
)
from zerver.tornado.django_api import send_event


def notify_topic_locked_status(topic: Topic, user_profile: UserProfile) -> None:

    stream = get_stream_by_id_in_realm(topic.stream.id, user_profile.realm)

    event = dict(
        op="update",
        type="topic",
        property="topic_locked",
        value=topic.locked,
        stream_id=stream.id,
        name=topic.topic_name,
    )

    send_event(topic.realm, event, can_access_stream_user_ids(stream))

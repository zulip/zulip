from django.http import HttpRequest, HttpResponse
from zerver.actions.topics import notify_topic_locked_status
from zerver.decorator import require_realm_moderator

from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.topic import update_topic
from zerver.lib.validator import to_non_negative_int
from zerver.models import UserProfile


@require_realm_moderator
@has_request_variables
def toggle_topic_locked_status(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int = REQ("stream_id", converter=to_non_negative_int),
    topic_name: str = REQ("topic_name"),
) -> HttpResponse:
    updated_topic = update_topic(
        realm_id=user_profile.realm_id,
        stream_id=stream_id,
        topic_name=topic_name,
        toggle_locked=True
    )

    if updated_topic is not None:
        notify_topic_locked_status(
            topic=updated_topic,
            user_profile=user_profile
        )

    return json_success(request)

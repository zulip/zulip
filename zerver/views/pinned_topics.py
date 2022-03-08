from django.http import HttpRequest, HttpResponse

from zerver.lib.pinned_topics import do_add_pinned_topic, do_remove_pinned_topic
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_int
from zerver.models import UserProfile


@has_request_variables
def pin_topic(
    request: HttpRequest,
    user: UserProfile,
    stream_id: int = REQ(json_validator=check_int),
    topic_name: str = REQ(),
) -> HttpResponse:
    do_add_pinned_topic(user=user, stream_id=stream_id, topic_name=topic_name)
    return json_success(request)


@has_request_variables
def unpin_topic(
    request: HttpRequest,
    user: UserProfile,
    stream_id: int = REQ(json_validator=check_int),
    topic_name: str = REQ(),
) -> HttpResponse:
    do_remove_pinned_topic(user=user, stream_id=stream_id, topic_name=topic_name)
    return json_success(request)

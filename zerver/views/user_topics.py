from datetime import datetime
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.streams import (
    access_stream_by_id,
    access_stream_by_name,
    access_stream_to_remove_visibility_policy_by_id,
    access_stream_to_remove_visibility_policy_by_name,
    check_for_exactly_one_stream_arg,
)
from zerver.lib.validator import check_capped_string, check_int, check_int_in, check_string_in
from zerver.models import UserProfile, UserTopic
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH


def mute_topic(
    user_profile: UserProfile,
    stream_id: Optional[int],
    stream_name: Optional[str],
    topic_name: str,
    date_muted: datetime,
) -> None:
    if stream_name is not None:
        (stream, sub) = access_stream_by_name(user_profile, stream_name)
    else:
        assert stream_id is not None
        (stream, sub) = access_stream_by_id(user_profile, stream_id)

    do_set_user_topic_visibility_policy(
        user_profile,
        stream,
        topic_name,
        visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        last_updated=date_muted,
    )


def unmute_topic(
    user_profile: UserProfile,
    stream_id: Optional[int],
    stream_name: Optional[str],
    topic_name: str,
) -> None:
    error = _("Topic is not muted")

    if stream_name is not None:
        stream = access_stream_to_remove_visibility_policy_by_name(user_profile, stream_name, error)
    else:
        assert stream_id is not None
        stream = access_stream_to_remove_visibility_policy_by_id(user_profile, stream_id, error)

    do_set_user_topic_visibility_policy(
        user_profile, stream, topic_name, visibility_policy=UserTopic.VisibilityPolicy.INHERIT
    )


@has_request_variables
def update_muted_topic(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: Optional[int] = REQ(json_validator=check_int, default=None),
    stream: Optional[str] = REQ(default=None),
    topic: str = REQ(str_validator=check_capped_string(MAX_TOPIC_NAME_LENGTH)),
    op: str = REQ(str_validator=check_string_in(["add", "remove"])),
) -> HttpResponse:
    check_for_exactly_one_stream_arg(stream_id=stream_id, stream=stream)

    if op == "add":
        mute_topic(
            user_profile=user_profile,
            stream_id=stream_id,
            stream_name=stream,
            topic_name=topic,
            date_muted=timezone_now(),
        )
    elif op == "remove":
        unmute_topic(
            user_profile=user_profile,
            stream_id=stream_id,
            stream_name=stream,
            topic_name=topic,
        )
    return json_success(request)


@has_request_variables
def update_user_topic(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int = REQ(json_validator=check_int),
    topic: str = REQ(str_validator=check_capped_string(MAX_TOPIC_NAME_LENGTH)),
    visibility_policy: int = REQ(json_validator=check_int_in(UserTopic.VisibilityPolicy.values)),
) -> HttpResponse:
    if visibility_policy == UserTopic.VisibilityPolicy.INHERIT:
        error = _("Invalid channel ID")
        stream = access_stream_to_remove_visibility_policy_by_id(user_profile, stream_id, error)
    else:
        (stream, sub) = access_stream_by_id(user_profile, stream_id)

    do_set_user_topic_visibility_policy(
        user_profile, stream, topic, visibility_policy=visibility_policy
    )
    return json_success(request)

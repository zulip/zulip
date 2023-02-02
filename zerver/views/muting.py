import datetime
from typing import Optional

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.muted_users import do_mute_user, do_unmute_user
from zerver.actions.user_topics import do_mute_topic, do_unmute_topic
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.streams import (
    access_stream_by_id,
    access_stream_by_name,
    access_stream_for_unmute_topic_by_id,
    access_stream_for_unmute_topic_by_name,
    check_for_exactly_one_stream_arg,
)
from zerver.lib.user_mutes import get_mute_object
from zerver.lib.user_topics import topic_is_muted
from zerver.lib.users import access_user_by_id
from zerver.lib.validator import check_int, check_string_in
from zerver.models import UserProfile


def mute_topic(
    user_profile: UserProfile,
    stream_id: Optional[int],
    stream_name: Optional[str],
    topic_name: str,
    date_muted: datetime.datetime,
) -> None:
    if stream_name is not None:
        (stream, sub) = access_stream_by_name(user_profile, stream_name)
    else:
        assert stream_id is not None
        (stream, sub) = access_stream_by_id(user_profile, stream_id)

    if topic_is_muted(user_profile, stream.id, topic_name):
        raise JsonableError(_("Topic already muted"))

    try:
        do_mute_topic(user_profile, stream, topic_name, date_muted)
    except IntegrityError:
        raise JsonableError(_("Topic already muted"))


def unmute_topic(
    user_profile: UserProfile,
    stream_id: Optional[int],
    stream_name: Optional[str],
    topic_name: str,
) -> None:
    error = _("Topic is not muted")

    if stream_name is not None:
        stream = access_stream_for_unmute_topic_by_name(user_profile, stream_name, error)
    else:
        assert stream_id is not None
        stream = access_stream_for_unmute_topic_by_id(user_profile, stream_id, error)

    do_unmute_topic(user_profile, stream, topic_name)


@has_request_variables
def update_muted_topic(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: Optional[int] = REQ(json_validator=check_int, default=None),
    stream: Optional[str] = REQ(default=None),
    topic: str = REQ(),
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


def mute_user(request: HttpRequest, user_profile: UserProfile, muted_user_id: int) -> HttpResponse:
    if user_profile.id == muted_user_id:
        raise JsonableError(_("Cannot mute self"))

    muted_user = access_user_by_id(
        user_profile, muted_user_id, allow_bots=False, allow_deactivated=True, for_admin=False
    )
    date_muted = timezone_now()

    if get_mute_object(user_profile, muted_user) is not None:
        raise JsonableError(_("User already muted"))

    try:
        do_mute_user(user_profile, muted_user, date_muted)
    except IntegrityError:
        raise JsonableError(_("User already muted"))

    return json_success(request)


def unmute_user(
    request: HttpRequest, user_profile: UserProfile, muted_user_id: int
) -> HttpResponse:
    muted_user = access_user_by_id(
        user_profile, muted_user_id, allow_bots=False, allow_deactivated=True, for_admin=False
    )
    mute_object = get_mute_object(user_profile, muted_user)

    if mute_object is None:
        raise JsonableError(_("User is not muted"))

    do_unmute_user(mute_object)
    return json_success(request)

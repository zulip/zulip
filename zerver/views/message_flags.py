from typing import List, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_flags import (
    do_mark_all_as_read,
    do_mark_stream_messages_as_read,
    do_update_message_flags,
)
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.narrow import (
    OptionalNarrowListT,
    fetch_messages,
    narrow_parameter,
    parse_anchor_value,
)
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_partial_success, json_success
from zerver.lib.streams import access_stream_by_id
from zerver.lib.timeout import TimeoutExpiredError, timeout
from zerver.lib.topic import user_message_exists_for_topic
from zerver.lib.validator import check_bool, check_int, check_list, to_non_negative_int
from zerver.models import UserActivity, UserProfile


def get_latest_update_message_flag_activity(user_profile: UserProfile) -> Optional[UserActivity]:
    return (
        UserActivity.objects.filter(
            user_profile=user_profile,
            query__in=["update_message_flags", "update_message_flags_for_narrow"],
        )
        .order_by("last_visit")
        .last()
    )


# NOTE: If this function name is changed, add the new name to the
# query in get_latest_update_message_flag_activity
@has_request_variables
def update_message_flags(
    request: HttpRequest,
    user_profile: UserProfile,
    messages: List[int] = REQ(json_validator=check_list(check_int)),
    operation: str = REQ("op"),
    flag: str = REQ(),
) -> HttpResponse:
    request_notes = RequestNotes.get_notes(request)
    assert request_notes.log_data is not None

    count = do_update_message_flags(user_profile, operation, flag, messages)

    target_count_str = str(len(messages))
    log_data_str = f"[{operation} {flag}/{target_count_str}] actually {count}"
    request_notes.log_data["extra"] = log_data_str

    return json_success(
        request,
        data={
            "messages": messages,  # Useless, but included for backwards compatibility.
        },
    )


MAX_MESSAGES_PER_UPDATE = 5000


# NOTE: If this function name is changed, add the new name to the
# query in get_latest_update_message_flag_activity
@has_request_variables
def update_message_flags_for_narrow(
    request: HttpRequest,
    user_profile: UserProfile,
    anchor_val: str = REQ("anchor"),
    include_anchor: bool = REQ(json_validator=check_bool, default=True),
    num_before: int = REQ(converter=to_non_negative_int),
    num_after: int = REQ(converter=to_non_negative_int),
    narrow: OptionalNarrowListT = REQ("narrow", converter=narrow_parameter),
    operation: str = REQ("op"),
    flag: str = REQ(),
) -> HttpResponse:
    anchor = parse_anchor_value(anchor_val, use_first_unread_anchor=False)

    if num_before > 0 and num_after > 0 and not include_anchor:
        raise JsonableError(_("The anchor can only be excluded at an end of the range"))

    # Clamp such that num_before + num_after <= MAX_MESSAGES_PER_UPDATE.
    num_before = min(
        num_before, max(MAX_MESSAGES_PER_UPDATE - num_after, MAX_MESSAGES_PER_UPDATE // 2)
    )
    num_after = min(num_after, MAX_MESSAGES_PER_UPDATE - num_before)

    query_info = fetch_messages(
        narrow=narrow,
        user_profile=user_profile,
        realm=user_profile.realm,
        is_web_public_query=False,
        anchor=anchor,
        include_anchor=include_anchor,
        num_before=num_before,
        num_after=num_after,
    )

    messages = [row[0] for row in query_info.rows]
    updated_count = do_update_message_flags(user_profile, operation, flag, messages)

    return json_success(
        request,
        data={
            "processed_count": len(messages),
            "updated_count": updated_count,
            "first_processed_id": messages[0] if messages else None,
            "last_processed_id": messages[-1] if messages else None,
            "found_oldest": query_info.found_oldest,
            "found_newest": query_info.found_newest,
        },
    )


@has_request_variables
def mark_all_as_read(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    request_notes = RequestNotes.get_notes(request)
    try:
        count = timeout(50, lambda: do_mark_all_as_read(user_profile))
    except TimeoutExpiredError:
        return json_partial_success(request, data={"code": ErrorCode.REQUEST_TIMEOUT.name})

    log_data_str = f"[{count} updated]"
    assert request_notes.log_data is not None
    request_notes.log_data["extra"] = log_data_str

    return json_success(request)


@has_request_variables
def mark_stream_as_read(
    request: HttpRequest, user_profile: UserProfile, stream_id: int = REQ(json_validator=check_int)
) -> HttpResponse:
    stream, sub = access_stream_by_id(user_profile, stream_id)
    assert stream.recipient_id is not None
    count = do_mark_stream_messages_as_read(user_profile, stream.recipient_id)

    log_data_str = f"[{count} updated]"
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = log_data_str

    return json_success(request)


@has_request_variables
def mark_topic_as_read(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int = REQ(json_validator=check_int),
    topic_name: str = REQ(),
) -> HttpResponse:
    stream, sub = access_stream_by_id(user_profile, stream_id)
    assert stream.recipient_id is not None

    if topic_name:
        topic_exists = user_message_exists_for_topic(
            user_profile=user_profile,
            recipient_id=stream.recipient_id,
            topic_name=topic_name,
        )

        if not topic_exists:
            raise JsonableError(_("No such topic '{}'").format(topic_name))

    count = do_mark_stream_messages_as_read(user_profile, stream.recipient_id, topic_name)

    log_data_str = f"[{count} updated]"
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = log_data_str

    return json_success(request)

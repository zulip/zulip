from typing import List, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt
from typing_extensions import Annotated

from zerver.actions.message_flags import (
    do_mark_all_as_read,
    do_mark_stream_messages_as_read,
    do_update_message_flags,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.narrow import NarrowParameter, fetch_messages, parse_anchor_value
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id
from zerver.lib.topic import user_message_exists_for_topic
from zerver.lib.typed_endpoint import (
    ApiParamConfig,
    typed_endpoint,
    typed_endpoint_without_parameters,
)
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
@typed_endpoint
def update_message_flags(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    messages: Json[List[int]],
    operation: Annotated[str, ApiParamConfig("op")],
    flag: str,
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
@typed_endpoint
def update_message_flags_for_narrow(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    anchor_val: Annotated[str, ApiParamConfig("anchor")],
    include_anchor: Json[bool] = True,
    num_before: Json[NonNegativeInt],
    num_after: Json[NonNegativeInt],
    narrow: Json[Optional[List[NarrowParameter]]],
    operation: Annotated[str, ApiParamConfig("op")],
    flag: str,
) -> HttpResponse:
    anchor = parse_anchor_value(anchor_val, use_first_unread_anchor=False)

    if num_before > 0 and num_after > 0 and not include_anchor:
        raise JsonableError(_("The anchor can only be excluded at an end of the range"))

    # Clamp such that num_before + num_after <= MAX_MESSAGES_PER_UPDATE.
    num_before = min(
        num_before, max(MAX_MESSAGES_PER_UPDATE - num_after, MAX_MESSAGES_PER_UPDATE // 2)
    )
    num_after = min(num_after, MAX_MESSAGES_PER_UPDATE - num_before)

    if narrow is not None and len(narrow) > 0:
        narrow_dict = [x.model_dump() for x in narrow]
    else:
        narrow_dict = None

    query_info = fetch_messages(
        narrow=narrow_dict,
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


@typed_endpoint_without_parameters
def mark_all_as_read(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    request_notes = RequestNotes.get_notes(request)
    count = do_mark_all_as_read(user_profile, timeout=50)
    if count is None:
        return json_success(request, data={"complete": False})

    log_data_str = f"[{count} updated]"
    assert request_notes.log_data is not None
    request_notes.log_data["extra"] = log_data_str

    return json_success(request, data={"complete": True})


@typed_endpoint
def mark_stream_as_read(
    request: HttpRequest, user_profile: UserProfile, *, stream_id: Json[int]
) -> HttpResponse:
    stream, sub = access_stream_by_id(user_profile, stream_id)
    assert stream.recipient_id is not None
    count = do_mark_stream_messages_as_read(user_profile, stream.recipient_id)

    log_data_str = f"[{count} updated]"
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = log_data_str

    return json_success(request)


@typed_endpoint
def mark_topic_as_read(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    stream_id: Json[int],
    topic_name: str,
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
            raise JsonableError(_("No such topic '{topic}'").format(topic=topic_name))

    count = do_mark_stream_messages_as_read(user_profile, stream.recipient_id, topic_name)

    log_data_str = f"[{count} updated]"
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = log_data_str

    return json_success(request)

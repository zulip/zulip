from datetime import datetime, timezone

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.lib.exceptions import JsonableError
from zerver.lib.meeting_actions import (
    access_meeting_for_user,
    do_confirm_meeting,
    do_create_meeting,
    do_upsert_responses,
    get_ranked_slots,
    get_realm_users,
    get_stream_subscribers,
)
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id, access_stream_for_send_message
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import Stream, UserProfile


def _parse_iso_datetime_to_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@typed_endpoint
def get_meeting_candidates(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    stream_name: str | None = None,
) -> HttpResponse:
    """GET /json/meetings/candidates

    Returns the invite candidate list for the proposal modal.
    If stream_name is given, returns that stream's subscribers (the common case
    when the organizer is already in a channel). Otherwise returns all realm users.
    """
    if stream_name is not None:
        users = get_stream_subscribers(user_profile, stream_name)
    else:
        users = get_realm_users(user_profile.realm)
    return json_success(request, data={"users": users})


@typed_endpoint
def create_meeting(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    topic: str,
    slots: Json[list[dict[str, str]]],
    deadline: str,
    invite_user_ids: Json[list[int]],
    create_channel: Json[bool] = False,
    stream_id: Json[int] | None = None,
) -> HttpResponse:
    """POST /json/meetings"""
    parsed_deadline = _parse_iso_datetime_to_utc(deadline)

    parsed_slots: list[tuple[datetime, datetime | None]] = []
    for slot in slots:
        start = _parse_iso_datetime_to_utc(slot["start_time"])
        end = _parse_iso_datetime_to_utc(slot["end_time"]) if slot.get("end_time") else None
        parsed_slots.append((start, end))

    stream: Stream | None = None
    if not create_channel:
        if stream_id is None:
            raise JsonableError("stream_id is required when create_channel is False.")
        stream, _sub = access_stream_by_id(user_profile, stream_id)
        access_stream_for_send_message(user_profile, stream, None)

    meeting = do_create_meeting(
        owner=user_profile,
        topic=topic,
        slots=parsed_slots,
        deadline=parsed_deadline,
        invite_user_ids=invite_user_ids,
        create_channel=create_channel,
        stream=stream,
    )

    return json_success(request, data={"meeting_id": meeting.id, "stream_id": meeting.stream_id})


@typed_endpoint
def get_meeting(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    meeting_id: PathOnly[int],
) -> HttpResponse:
    """GET /json/meetings/<meeting_id>"""
    meeting = access_meeting_for_user(user_profile, meeting_id)

    slots = [
        {
            "slot_id": slot.id,
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat() if slot.end_time else None,
        }
        for slot in meeting.slots.all()
    ]

    return json_success(
        request,
        data={
            "meeting_id": meeting.id,
            "topic": meeting.topic,
            "owner_id": meeting.owner_id,
            "stream_id": meeting.stream_id,
            "deadline": meeting.deadline.isoformat(),
            "status": meeting.status,
            "confirmed_slot_id": meeting.confirmed_slot_id,
            "slots": slots,
        },
    )


@typed_endpoint
def upsert_meeting_responses(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    meeting_id: PathOnly[int],
    slot_responses: Json[dict[str, bool]],
) -> HttpResponse:
    """PATCH /json/meetings/<meeting_id>/responses"""
    meeting = access_meeting_for_user(user_profile, meeting_id)

    try:
        parsed: dict[int, bool] = {int(k): v for k, v in slot_responses.items()}
    except ValueError:
        raise JsonableError("slot_responses keys must be integer slot IDs.")

    do_upsert_responses(user_profile, meeting, parsed)
    return json_success(request)


@typed_endpoint
def get_meeting_responses(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    meeting_id: PathOnly[int],
) -> HttpResponse:
    """GET /json/meetings/<meeting_id>/responses"""
    meeting = access_meeting_for_user(user_profile, meeting_id)
    return json_success(request, data={"slots": get_ranked_slots(meeting)})


@typed_endpoint
def confirm_meeting(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    meeting_id: PathOnly[int],
    winning_slot_id: Json[int],
) -> HttpResponse:
    """POST /json/meetings/<meeting_id>/confirm"""
    meeting = access_meeting_for_user(user_profile, meeting_id)
    do_confirm_meeting(user_profile, meeting, winning_slot_id)
    return json_success(request)
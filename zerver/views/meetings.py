from datetime import datetime

from django.http import HttpRequest, HttpResponse

from zerver.lib.exceptions import JsonableError
from zerver.lib.meeting_actions import (
    check_meeting_deadlines,
    do_confirm_meeting,
    do_create_meeting,
    do_upsert_responses,
    get_ranked_slots,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import Stream, UserProfile
from zerver.models.meetings import Meeting


def _get_meeting_or_error(meeting_id: int, realm_id: int) -> Meeting:
    try:
        return Meeting.objects.select_related("owner", "stream").get(
            id=meeting_id, stream__realm_id=realm_id
        )
    except Meeting.DoesNotExist:
        raise JsonableError("Meeting not found.")


@typed_endpoint
def create_meeting(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    topic: str,
    # ISO-8601 strings; the frontend sends these as strings.
    slots: list[dict[str, str]],
    deadline: str,
    invite_user_ids: list[int],
    create_channel: bool = False,
    stream_id: int | None = None,
) -> HttpResponse:
    """POST /json/meetings"""
    parsed_deadline = datetime.fromisoformat(deadline)

    parsed_slots: list[tuple[datetime, datetime | None]] = []
    for slot in slots:
        start = datetime.fromisoformat(slot["start_time"])
        end = datetime.fromisoformat(slot["end_time"]) if slot.get("end_time") else None
        parsed_slots.append((start, end))

    stream: Stream | None = None
    if not create_channel:
        if stream_id is None:
            raise JsonableError("stream_id is required when create_channel is False.")
        try:
            stream = Stream.objects.get(id=stream_id, realm=user_profile.realm)
        except Stream.DoesNotExist:
            raise JsonableError("Stream not found.")

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
    meeting = _get_meeting_or_error(meeting_id, user_profile.realm_id)

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
    # Maps slot_id (as string key from JSON) → available bool.
    slot_responses: dict[str, bool],
) -> HttpResponse:
    """PATCH /json/meetings/<meeting_id>/responses"""
    meeting = _get_meeting_or_error(meeting_id, user_profile.realm_id)

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
    meeting = _get_meeting_or_error(meeting_id, user_profile.realm_id)
    return json_success(request, data={"slots": get_ranked_slots(meeting)})


@typed_endpoint
def confirm_meeting(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    meeting_id: PathOnly[int],
    winning_slot_id: int,
) -> HttpResponse:
    """POST /json/meetings/<meeting_id>/confirm"""
    meeting = _get_meeting_or_error(meeting_id, user_profile.realm_id)
    do_confirm_meeting(user_profile, meeting, winning_slot_id)
    return json_success(request)

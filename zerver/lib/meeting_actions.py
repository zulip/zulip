"""
Business logic for the meeting scheduling feature.

Flow summary:
  1. Organizer calls get_stream_subscribers() or get_realm_users() to build
     the invite candidate list shown in the proposal modal.
  2. Organizer calls do_create_meeting() — creates Meeting + MeetingSlots,
     creates a private stream in the "meetings" folder (or reuses an existing
     one), subscribes invitees, and posts a proposal message.
  3. Attendees call do_upsert_responses() to record availability per slot.
  4. After the deadline, check_meeting_deadlines() (management command) transitions
     status to DEADLINE_PASSED and notifies the owner via DM.
  5. Organizer calls do_confirm_meeting() to pick the winning slot and broadcast
     the result.
"""

from datetime import datetime, timezone

from django.db.models import Count, Q

from zerver.actions.message_send import internal_send_private_message, internal_send_stream_message
from zerver.actions.streams import bulk_add_subscriptions, get_subscriber_ids
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import access_stream_by_name, create_stream_if_needed
from zerver.models import Stream, UserProfile
from zerver.models.channel_folders import ChannelFolder
from zerver.models.meetings import Meeting, MeetingResponse, MeetingSlot
from zerver.models.realms import Realm


# ---------------------------------------------------------------------------
# Candidate-list helpers (used by the proposal modal to populate invitee picker)
# ---------------------------------------------------------------------------

def get_realm_users(realm: Realm) -> list[dict[str, object]]:
    """Return id + name for every active non-bot user in the realm."""
    return list(
        UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)
        .order_by("full_name")
        .values("id", "full_name")
    )


def get_stream_subscribers(requesting_user: UserProfile, stream_name: str) -> list[dict[str, object]]:
    """Return id + name for every active subscriber of the named stream."""
    stream, _ = access_stream_by_name(requesting_user, stream_name)
    user_ids = get_subscriber_ids(stream, requesting_user=requesting_user)
    return list(
        UserProfile.objects.filter(id__in=user_ids, is_active=True)
        .order_by("full_name")
        .values("id", "full_name")
    )


# ---------------------------------------------------------------------------
# Meeting lifecycle
# ---------------------------------------------------------------------------

def do_create_meeting(
    owner: UserProfile,
    topic: str,
    # Each slot is a (start_time, end_time | None) pair.
    slots: list[tuple[datetime, datetime | None]],
    deadline: datetime,
    invite_user_ids: list[int],
    # When True the server creates a new private stream in the "meetings" folder
    # and subscribes all invitees. When False the owner must supply an existing stream.
    create_channel: bool,
    stream: Stream | None = None,
) -> Meeting:
    realm = owner.realm
    now = datetime.now(tz=timezone.utc)

    if deadline <= now:
        raise JsonableError("Deadline must be in the future.")
    if not slots:
        raise JsonableError("At least one time slot is required.")

    if create_channel:
        # All meeting streams live in a shared "meetings" folder for discoverability.
        folder, _ = ChannelFolder.objects.get_or_create(realm=realm, name="meetings")
        stream_name = f"meeting: {topic}"
        stream, _created = create_stream_if_needed(
            realm,
            stream_name,
            invite_only=True,
            folder=folder,
            acting_user=owner,
        )
        invited_users = list(
            UserProfile.objects.filter(id__in=invite_user_ids, realm=realm, is_active=True)
        )
        bulk_add_subscriptions(realm, [stream], invited_users, acting_user=owner)
    elif stream is None:
        raise JsonableError("Either create_channel must be True or a stream must be provided.")

    meeting = Meeting.objects.create(
        owner=owner,
        stream=stream,
        topic=topic,
        deadline=deadline,
    )

    MeetingSlot.objects.bulk_create(
        MeetingSlot(meeting=meeting, start_time=start, end_time=end) for start, end in slots
    )

    slot_lines = "\n".join(
        f"- {slot.start_time.strftime('%Y-%m-%d %H:%M UTC')}"
        + (f" – {slot.end_time.strftime('%H:%M UTC')}" if slot.end_time else "")
        for slot in meeting.slots.all()
    )
    content = (
        f"**Meeting proposed:** {topic}\n\n"
        f"**Time options:**\n{slot_lines}\n\n"
        f"**RSVP deadline:** {deadline.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"Reply to this thread with your availability. (Meeting ID: {meeting.id})"
    )
    internal_send_stream_message(owner, stream, topic, content, acting_user=owner)

    return meeting


def do_upsert_responses(
    user: UserProfile,
    meeting: Meeting,
    # Maps slot_id → available (True/False).
    slot_responses: dict[int, bool],
) -> None:
    now = datetime.now(tz=timezone.utc)

    if meeting.status == Meeting.Status.CONFIRMED:
        raise JsonableError("This meeting has already been confirmed.")
    if meeting.deadline <= now:
        raise JsonableError("The RSVP deadline has passed.")

    # Verify all slot_ids belong to this meeting.
    valid_slot_ids = set(meeting.slots.values_list("id", flat=True))
    unknown = set(slot_responses) - valid_slot_ids
    if unknown:
        raise JsonableError(f"Unknown slot IDs: {sorted(unknown)}")

    for slot_id, available in slot_responses.items():
        MeetingResponse.objects.update_or_create(
            slot_id=slot_id,
            user=user,
            defaults={"available": available},
        )


def get_ranked_slots(meeting: Meeting) -> list[dict[str, object]]:
    """Return slots ranked by the number of available responses, descending."""
    slots = meeting.slots.annotate(
        available_count=Count("responses", filter=Q(responses__available=True))
    ).order_by("-available_count", "start_time")
    return [
        {
            "slot_id": slot.id,
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat() if slot.end_time else None,
            "available_count": slot.available_count,
        }
        for slot in slots
    ]


def do_confirm_meeting(owner: UserProfile, meeting: Meeting, winning_slot_id: int) -> None:
    if meeting.owner_id != owner.id:
        raise JsonableError("Only the meeting owner can confirm a time.")
    if meeting.status == Meeting.Status.CONFIRMED:
        raise JsonableError("Meeting is already confirmed.")

    try:
        winning_slot = meeting.slots.get(id=winning_slot_id)
    except MeetingSlot.DoesNotExist:
        raise JsonableError("Invalid slot ID.")

    meeting.confirmed_slot = winning_slot
    meeting.status = Meeting.Status.CONFIRMED
    meeting.save(update_fields=["confirmed_slot", "status"])

    time_str = winning_slot.start_time.strftime("%Y-%m-%d %H:%M UTC")
    if winning_slot.end_time:
        time_str += f" – {winning_slot.end_time.strftime('%H:%M UTC')}"

    content = f"**Meeting confirmed:** {meeting.topic}\n\n**Time:** {time_str}"
    internal_send_stream_message(owner, meeting.stream, meeting.topic, content, acting_user=owner)


def check_meeting_deadlines() -> None:
    """
    Transition overdue proposed meetings to DEADLINE_PASSED and notify owners.
    Intended to be called from a management command on a periodic schedule.
    """
    now = datetime.now(tz=timezone.utc)
    overdue = Meeting.objects.filter(status=Meeting.Status.PROPOSED, deadline__lte=now)

    for meeting in overdue.select_related("owner", "stream"):
        meeting.status = Meeting.Status.DEADLINE_PASSED
        meeting.save(update_fields=["status"])

        internal_send_stream_message(
            meeting.owner,
            meeting.stream,
            meeting.topic,
            "The RSVP deadline has passed. The meeting owner will confirm a time shortly.",
            acting_user=meeting.owner,
        )

        ranked = get_ranked_slots(meeting)
        slot_lines = "\n".join(
            f"{i + 1}. {s['start_time']} — {s['available_count']} available"
            for i, s in enumerate(ranked)
        )
        internal_send_private_message(
            meeting.owner,
            meeting.owner,
            f"The RSVP deadline for **{meeting.topic}** (meeting {meeting.id}) has passed.\n\n"
            f"**Ranked availability:**\n{slot_lines}\n\n"
            f"Confirm a time: POST /json/meetings/{meeting.id}/confirm",
        )

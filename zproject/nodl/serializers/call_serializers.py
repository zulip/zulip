from typing import Any


def serialize_call_record(call: Any, requesting_user_id: int | None = None) -> dict:
    """Serialize a CallRecord to a dict with snake_case JSON fields.

    When requesting_user_id is provided, derives remote_name, remote_avatar_url,
    and is_incoming from the caller/callee relationship.
    """
    is_incoming = requesting_user_id is not None and call.callee_id == requesting_user_id
    if is_incoming:
        remote = getattr(call, "caller", None)
        remote_id = call.caller_id
    else:
        remote = getattr(call, "callee", None)
        remote_id = call.callee_id

    remote_name = remote.full_name if remote else f"User {remote_id}"

    return {
        "call_id": str(call.id),
        "room_name": call.room_name,
        "caller_id": call.caller_id,
        "callee_id": call.callee_id,
        "status": call.status,
        "initiated_at": call.initiated_at.isoformat() if call.initiated_at else None,
        "answered_at": call.answered_at.isoformat() if call.answered_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "end_reason": call.end_reason,
        "remote_name": remote_name,
        "remote_avatar_url": None,
        "is_incoming": is_incoming,
    }


def serialize_call_initiate_response(
    call: Any, room_name: str, livekit_url: str, token: str
) -> dict:
    """Serialize the response for POST /nodl/calls/initiate."""
    return {
        "call_id": str(call.id),
        "room_name": room_name,
        "livekit_url": livekit_url,
        "token": token,
    }


def serialize_call_accept_response(
    call: Any, room_name: str, livekit_url: str, token: str
) -> dict:
    """Serialize the response for POST /nodl/calls/{call_id}/accept."""
    return {
        "token": token,
        "call_id": str(call.id),
        "room_name": room_name,
        "livekit_url": livekit_url,
    }

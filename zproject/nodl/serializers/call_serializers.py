from typing import Any


def serialize_call_record(call: Any) -> dict:
    """Serialize a CallRecord to a dict with snake_case JSON fields."""
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

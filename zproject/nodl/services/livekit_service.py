import logging
import os

from livekit import api

logger = logging.getLogger(__name__)

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")


def generate_token(identity: str, room_name: str) -> str:
    """Generate a LiveKit access token for the given identity and room.

    Args:
        identity: Participant identity (user email or ID string).
        room_name: LiveKit room name to grant access to.

    Returns:
        JWT access token string.

    Raises:
        ValueError: If LiveKit credentials are not configured.
    """
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise ValueError("LiveKit API credentials not configured")

    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
    )
    return token.to_jwt()


async def create_room(
    room_name: str,
    max_participants: int = 2,
    empty_timeout: int = 35,
) -> dict:
    """Create a LiveKit room via the Room Service API.

    Args:
        room_name: Unique room name.
        max_participants: Max participants allowed (default 2 for 1-to-1 calls).
        empty_timeout: Seconds before empty room is closed (default 35 — server timeout).

    Returns:
        Dict with room details (name, sid).

    Raises:
        ValueError: If LiveKit credentials are not configured.
    """
    if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise ValueError("LiveKit credentials not configured")

    lkapi = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        room = await lkapi.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                max_participants=max_participants,
                empty_timeout=empty_timeout,
            )
        )
        return {"name": room.name, "sid": room.sid}
    finally:
        await lkapi.aclose()

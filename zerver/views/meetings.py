"""Video meeting creation endpoint that integrates with nodl-backend JaaS service."""

import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.actions.message_send import check_send_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.nodl_backend import NodlBackendService
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

logger = logging.getLogger(__name__)


@typed_endpoint
def create_instant_meeting(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    title: str = "Video Meeting",
    stream_id: Json[int] | None = None,
    topic: str | None = None,
    private_message_recipient_ids: Json[list[int]] | None = None,
) -> HttpResponse:
    """Create an instant video meeting and post a meeting widget to the chat.

    This endpoint:
    1. Calls nodl-backend to create a JaaS meeting
    2. Sends a message with a meeting widget to the specified stream/DM
    3. Returns the meeting join URL and message ID

    Args:
        title: Optional meeting title (default: "Video Meeting")
        stream_id: Stream ID to post the meeting to (for channel messages)
        topic: Topic name for channel messages
        private_message_recipient_ids: List of user IDs for direct messages
    """
    # Get workspace ID from realm settings or use realm UUID
    workspace_id = getattr(settings, "NODL_WORKSPACE_ID", None)
    if not workspace_id:
        # Fall back to using the realm's string_id as workspace identifier
        workspace_id = user_profile.realm.string_id

    # Create meeting via nodl-backend
    try:
        service = NodlBackendService()
        meeting = service.create_instant_meeting(workspace_id, user_profile)
    except Exception as e:
        logger.exception("Failed to create meeting")
        raise JsonableError(str(e)) from e

    # Build widget content for the meeting card
    widget_content = json.dumps({
        "widget_type": "meeting",
        "extra_data": {
            "room_name": meeting.room_name,
            "title": title,
            "host_id": user_profile.id,
            "host_name": user_profile.full_name,
            "domain": meeting.domain,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "join_url": meeting.join_url,
        },
    })

    # Build message content (visible text)
    message_content = f"**{title}**\n\nJoin the video meeting: {meeting.join_url}"

    # Determine recipient type and send message
    client = RequestNotes.get_notes(request).client
    assert client is not None

    if stream_id is not None:
        # Channel message
        # Verify stream access
        stream = access_stream_by_id(user_profile, stream_id)[0]

        sent_message = check_send_message(
            sender=user_profile,
            client=client,
            recipient_type_name="stream",
            message_to=[stream.id],
            topic_name=topic or "meetings",
            message_content=message_content,
            widget_content=widget_content,
        )
    elif private_message_recipient_ids:
        # Direct message
        sent_message = check_send_message(
            sender=user_profile,
            client=client,
            recipient_type_name="private",
            message_to=private_message_recipient_ids,
            topic_name=None,
            message_content=message_content,
            widget_content=widget_content,
        )
    else:
        raise JsonableError("Either stream_id or private_message_recipient_ids is required")

    logger.info(
        "Meeting created: room=%s, message_id=%d, user=%s",
        meeting.room_name,
        sent_message.message_id,
        user_profile.delivery_email,
    )

    return json_success(
        request,
        data={
            "message_id": sent_message.message_id,
            "room_name": meeting.room_name,
            "join_url": meeting.join_url,
            "domain": meeting.domain,
            "jwt": meeting.jwt,
        },
    )

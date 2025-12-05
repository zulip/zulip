"""Serializers for message-related API responses."""

from datetime import datetime
from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field

from zerver.models import Message
from zerver.models.recipients import Recipient


class ReactionSerializer(BaseModel):
    """Serializer for reaction data."""

    emoji_name: Annotated[str, Field(description="Name of the emoji")]
    emoji_code: Annotated[str, Field(description="Code for the emoji")]
    user_ids: Annotated[list[int], Field(default=[], description="List of user IDs who reacted")]


class MessageSerializer(BaseModel):
    """Serializer for full message details."""

    id: Annotated[int, Field(description="Message ID")]
    sender_id: Annotated[int, Field(description="Sender user ID")]
    sender_full_name: Annotated[str, Field(description="Sender's full name")]
    sender_email: Annotated[str, Field(description="Sender's email")]
    sender_avatar_url: Annotated[Optional[str], Field(description="Sender's avatar URL")]
    stream_id: Annotated[Optional[int], Field(description="Stream ID (if channel message)")]
    topic: Annotated[str, Field(description="Message topic")]
    content: Annotated[str, Field(description="Raw Markdown content")]
    rendered_content: Annotated[str, Field(description="HTML rendered content")]
    timestamp: Annotated[int, Field(description="Unix timestamp when sent")]
    last_edit_timestamp: Annotated[Optional[int], Field(description="Unix timestamp of last edit")]
    reactions: Annotated[list[ReactionSerializer], Field(default=[], description="Message reactions")]
    is_me_message: Annotated[bool, Field(default=False, description="Whether this is a /me message")]
    flags: Annotated[list[str], Field(default=[], description="Message flags (e.g., read, starred)")]

    @classmethod
    def from_message(
        cls,
        message: Message,
        reactions: Optional[list[ReactionSerializer]] = None,
        flags: Optional[list[str]] = None,
    ) -> "MessageSerializer":
        """Create serializer from Message model."""
        # Get stream_id from recipient if this is a channel message
        stream_id = None
        if message.is_channel_message and message.recipient:
            stream_id = message.recipient.type_id

        # Get avatar URL if sender has one
        avatar_url = None
        if hasattr(message.sender, "avatar_source") and message.sender.avatar_source:
            # Build avatar URL - simplified version
            avatar_url = f"/avatar/{message.sender_id}"

        # Convert timestamps
        timestamp = int(message.date_sent.timestamp())
        last_edit_timestamp = None
        if message.last_edit_time:
            last_edit_timestamp = int(message.last_edit_time.timestamp())

        return cls(
            id=message.id,
            sender_id=message.sender_id,
            sender_full_name=message.sender.full_name,
            sender_email=message.sender.delivery_email,
            sender_avatar_url=avatar_url,
            stream_id=stream_id,
            topic=message.topic_name(),
            content=message.content,
            rendered_content=message.rendered_content or "",
            timestamp=timestamp,
            last_edit_timestamp=last_edit_timestamp,
            reactions=reactions or [],
            is_me_message=message.content.startswith("/me "),
            flags=flags or [],
        )


class MessageListSerializer(BaseModel):
    """Serializer for message list responses."""

    id: Annotated[int, Field(description="Message ID")]
    sender_id: Annotated[int, Field(description="Sender user ID")]
    sender_full_name: Annotated[str, Field(description="Sender's full name")]
    stream_id: Annotated[Optional[int], Field(description="Stream ID")]
    topic: Annotated[str, Field(description="Message topic")]
    content: Annotated[str, Field(description="Raw Markdown content")]
    rendered_content: Annotated[str, Field(description="HTML rendered content")]
    timestamp: Annotated[int, Field(description="Unix timestamp when sent")]

    @classmethod
    def from_message(cls, message: Message) -> "MessageListSerializer":
        """Create serializer from Message model."""
        stream_id = None
        if message.is_channel_message and message.recipient:
            stream_id = message.recipient.type_id

        return cls(
            id=message.id,
            sender_id=message.sender_id,
            sender_full_name=message.sender.full_name,
            stream_id=stream_id,
            topic=message.topic_name(),
            content=message.content,
            rendered_content=message.rendered_content or "",
            timestamp=int(message.date_sent.timestamp()),
        )

    @classmethod
    def from_dict(cls, msg_dict: dict[str, Any]) -> "MessageListSerializer":
        """Create serializer from cached message dict (from messages_for_ids).

        The dict format comes from Zulip's MessageDict after hydration.
        """
        # Get stream_id from display_recipient if this is a stream message
        stream_id = None
        if msg_dict.get("type") == "stream":
            stream_id = msg_dict.get("stream_id")

        # Zulip cache uses "timestamp" field (already Unix timestamp)
        timestamp = msg_dict.get("timestamp", 0)

        # When apply_markdown=True, "content" has the rendered HTML
        # rendered_content may be deleted by Zulip's finalize_payload, so fallback to content
        rendered_content = msg_dict.get("rendered_content") or msg_dict.get("content", "")

        return cls(
            id=msg_dict["id"],
            sender_id=msg_dict["sender_id"],
            sender_full_name=msg_dict.get("sender_full_name", "Unknown"),
            stream_id=stream_id,
            topic=msg_dict.get("subject", ""),  # Zulip uses 'subject' for topic
            content=msg_dict.get("content", ""),
            rendered_content=rendered_content,
            timestamp=timestamp,
        )


class MessageCreatePayload(BaseModel):
    """Request payload for sending a message."""

    stream_id: Annotated[int, Field(description="Stream ID to post to")]
    topic: Annotated[str, Field(min_length=1, max_length=60, description="Message topic")]
    content: Annotated[str, Field(min_length=1, max_length=10000, description="Message content")]


class MessageUpdatePayload(BaseModel):
    """Request payload for editing a message."""

    content: Annotated[str, Field(min_length=1, max_length=10000, description="New message content")]

"""Serializers for message-related API responses."""

from typing import Annotated, Any

from pydantic import BaseModel, Field

from zerver.models import Message
from zerver.models.recipients import Recipient


class ReactionSerializer(BaseModel):
    """Serializer for reaction data."""

    emoji_name: Annotated[str, Field(description="Name of the emoji")]
    emoji_code: Annotated[str, Field(description="Code for the emoji")]
    user_ids: Annotated[list[int], Field(default=[], description="List of user IDs who reacted")]


class DMRecipient(BaseModel):
    """Recipient info for direct messages."""

    id: Annotated[int, Field(description="User ID")]
    email: Annotated[str, Field(description="User email")]
    full_name: Annotated[str, Field(description="User full name")]


class MessageSerializer(BaseModel):
    """Serializer for full message details."""

    id: Annotated[int, Field(description="Message ID")]
    type: Annotated[str, Field(description="Message type: 'stream' or 'private'")]
    sender_id: Annotated[int, Field(description="Sender user ID")]
    sender_full_name: Annotated[str, Field(description="Sender's full name")]
    sender_email: Annotated[str, Field(description="Sender's email")]
    sender_avatar_url: Annotated[str | None, Field(description="Sender's avatar URL")]
    stream_id: Annotated[int | None, Field(description="Stream ID (if channel message)")]
    display_recipient: Annotated[
        list[DMRecipient] | None, Field(default=None, description="Recipients (for DMs)")
    ]
    topic: Annotated[str, Field(description="Message topic")]
    content: Annotated[str, Field(description="Raw Markdown content")]
    rendered_content: Annotated[str, Field(description="HTML rendered content")]
    timestamp: Annotated[int, Field(description="Unix timestamp when sent")]
    last_edit_timestamp: Annotated[int | None, Field(description="Unix timestamp of last edit")]
    reactions: Annotated[
        list[ReactionSerializer], Field(default=[], description="Message reactions")
    ]
    is_me_message: Annotated[
        bool, Field(default=False, description="Whether this is a /me message")
    ]
    flags: Annotated[
        list[str], Field(default=[], description="Message flags (e.g., read, starred)")
    ]

    @classmethod
    def from_message(
        cls,
        message: Message,
        reactions: list[ReactionSerializer] | None = None,
        flags: list[str] | None = None,
        recipient_users: list[Any] | None = None,
    ) -> "MessageSerializer":
        """Create serializer from Message model.

        Args:
            message: The Message model instance
            reactions: Optional list of reactions
            flags: Optional list of flags
            recipient_users: For DMs, list of UserProfile objects for all recipients
        """
        # Determine message type
        is_dm = message.recipient and message.recipient.type != Recipient.STREAM
        msg_type = "private" if is_dm else "stream"

        # Get stream_id from recipient if this is a channel message
        stream_id = None
        display_recipient = None
        if message.is_channel_message and message.recipient:
            stream_id = message.recipient.type_id
        elif is_dm and recipient_users:
            # For DMs, include recipient user info
            display_recipient = [
                DMRecipient(
                    id=u.id,
                    email=u.delivery_email,
                    full_name=u.full_name,
                )
                for u in recipient_users
            ]

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
            type=msg_type,
            sender_id=message.sender_id,
            sender_full_name=message.sender.full_name,
            sender_email=message.sender.delivery_email,
            sender_avatar_url=avatar_url,
            stream_id=stream_id,
            display_recipient=display_recipient,
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
    type: Annotated[str, Field(description="Message type: 'stream' or 'private'")]
    sender_id: Annotated[int, Field(description="Sender user ID")]
    sender_full_name: Annotated[str, Field(description="Sender's full name")]
    stream_id: Annotated[int | None, Field(description="Stream ID")]
    display_recipient: Annotated[
        list[DMRecipient] | None, Field(default=None, description="Recipients (for DMs)")
    ]
    topic: Annotated[str, Field(description="Message topic")]
    content: Annotated[str, Field(description="Raw Markdown content")]
    rendered_content: Annotated[str, Field(description="HTML rendered content")]
    timestamp: Annotated[int, Field(description="Unix timestamp when sent")]
    reactions: Annotated[
        list[ReactionSerializer], Field(default=[], description="Message reactions")
    ]

    @classmethod
    def from_message(cls, message: Message) -> "MessageListSerializer":
        """Create serializer from Message model."""
        is_dm = message.recipient and message.recipient.type != Recipient.STREAM
        msg_type = "private" if is_dm else "stream"

        stream_id = None
        if message.is_channel_message and message.recipient:
            stream_id = message.recipient.type_id

        return cls(
            id=message.id,
            type=msg_type,
            sender_id=message.sender_id,
            sender_full_name=message.sender.full_name,
            stream_id=stream_id,
            display_recipient=None,  # Will be populated separately for DMs
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
        msg_type = msg_dict.get("type", "stream")

        # Get stream_id from display_recipient if this is a stream message
        stream_id = None
        display_recipient = None
        if msg_type == "stream":
            stream_id = msg_dict.get("stream_id")
        else:
            # For DMs, display_recipient is a list of user dicts
            raw_recipients = msg_dict.get("display_recipient", [])
            if isinstance(raw_recipients, list):
                display_recipient = [
                    DMRecipient(
                        id=r.get("id", 0),
                        email=r.get("email", ""),
                        full_name=r.get("full_name", "Unknown"),
                    )
                    for r in raw_recipients
                    if isinstance(r, dict)
                ]

        # Zulip cache uses "timestamp" field (already Unix timestamp)
        timestamp = msg_dict.get("timestamp", 0)

        # When apply_markdown=True, "content" has the rendered HTML
        # rendered_content may be deleted by Zulip's finalize_payload, so fallback to content
        rendered_content = msg_dict.get("rendered_content") or msg_dict.get("content", "")

        # Extract reactions from the message dict
        # Zulip format: [{"emoji_name": "thumbs_up", "emoji_code": "1f44d", "user_id": 8, ...}]
        raw_reactions = msg_dict.get("reactions", [])
        # Group by emoji to aggregate user_ids
        emoji_users: dict[tuple[str, str], list[int]] = {}
        for r in raw_reactions:
            key = (r.get("emoji_name", ""), r.get("emoji_code", ""))
            if key not in emoji_users:
                emoji_users[key] = []
            emoji_users[key].append(r.get("user_id"))

        reactions = [
            ReactionSerializer(emoji_name=name, emoji_code=code, user_ids=user_ids)
            for (name, code), user_ids in emoji_users.items()
        ]

        return cls(
            id=msg_dict["id"],
            type=msg_type,
            sender_id=msg_dict["sender_id"],
            sender_full_name=msg_dict.get("sender_full_name", "Unknown"),
            stream_id=stream_id,
            display_recipient=display_recipient,
            topic=msg_dict.get("subject", ""),  # Zulip uses 'subject' for topic
            content=msg_dict.get("content", ""),
            rendered_content=rendered_content,
            timestamp=timestamp,
            reactions=reactions,
        )


class MessageCreatePayload(BaseModel):
    """Request payload for sending a message.

    For stream messages:
        - type: "stream" (default)
        - stream_id: Required
        - topic: Required
        - content: Required

    For direct messages:
        - type: "direct"
        - to: Required (list of user IDs)
        - content: Required
    """

    type: Annotated[str, Field(default="stream", description="Message type: 'stream' or 'direct'")]
    stream_id: Annotated[
        int | None, Field(default=None, description="Stream ID to post to (for stream messages)")
    ]
    topic: Annotated[
        str | None,
        Field(default=None, max_length=60, description="Message topic (for stream messages)"),
    ]
    to: Annotated[
        list[int] | None,
        Field(default=None, description="Recipient user IDs (for direct messages)"),
    ]
    content: Annotated[str, Field(min_length=1, max_length=10000, description="Message content")]


class MessageUpdatePayload(BaseModel):
    """Request payload for editing a message."""

    content: Annotated[
        str, Field(min_length=1, max_length=10000, description="New message content")
    ]

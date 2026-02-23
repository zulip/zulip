"""Serializers for stream-related API responses."""

from typing import Annotated

from pydantic import BaseModel, Field

from zerver.models import Stream


class TopicSerializer(BaseModel):
    """Serializer for topic data."""

    name: Annotated[str, Field(description="Topic name")]
    max_id: Annotated[int, Field(description="ID of the most recent message in the topic")]
    unread_count: Annotated[int, Field(default=0, description="Number of unread messages")]


class StreamSerializer(BaseModel):
    """Serializer for stream details."""

    id: Annotated[int, Field(description="Stream ID")]
    name: Annotated[str, Field(description="Stream name")]
    description: Annotated[str, Field(description="Stream description")]
    is_private: Annotated[bool, Field(description="Whether the stream is private")]
    is_announcement_only: Annotated[bool, Field(description="Whether only admins can post")]
    stream_post_policy: Annotated[int, Field(description="Who can post to the stream")]
    history_public_to_subscribers: Annotated[
        bool, Field(description="Whether history is visible to new subscribers")
    ]
    first_message_id: Annotated[int | None, Field(description="ID of first message")]
    subscribers: Annotated[list[int], Field(default=[], description="List of subscriber user IDs")]

    @classmethod
    def from_stream(
        cls,
        stream: Stream,
        subscribers: list[int] | None = None,
    ) -> "StreamSerializer":
        """Create serializer from Stream model."""
        return cls(
            id=stream.id,
            name=stream.name,
            description=stream.description,
            is_private=stream.invite_only,
            is_announcement_only=False,  # Simplified - group permissions not exposed via REST API
            stream_post_policy=Stream.STREAM_POST_POLICY_EVERYONE,  # Default value
            history_public_to_subscribers=stream.history_public_to_subscribers,
            first_message_id=stream.first_message_id,
            subscribers=subscribers or [],
        )


class StreamListSerializer(StreamSerializer):
    """Serializer for stream list with unread counts and user preferences."""

    unread_count: Annotated[int, Field(default=0, description="Number of unread messages")]
    is_muted: Annotated[
        bool, Field(default=False, description="Whether the stream is muted for the user")
    ]
    pin_to_top: Annotated[
        bool, Field(default=False, description="Whether the stream is pinned to the top")
    ]
    topics: Annotated[list[TopicSerializer], Field(default=[], description="Topics in the stream")]

    @classmethod
    def from_stream_with_unread(
        cls,
        stream: Stream,
        unread_count: int = 0,
        subscribers: list[int] | None = None,
        topics: list[TopicSerializer] | None = None,
        is_muted: bool = False,
        pin_to_top: bool = False,
    ) -> "StreamListSerializer":
        """Create serializer from Stream model with unread count and user preferences."""
        return cls(
            id=stream.id,
            name=stream.name,
            description=stream.description,
            is_private=stream.invite_only,
            is_announcement_only=False,  # Simplified - group permissions not exposed via REST API
            stream_post_policy=Stream.STREAM_POST_POLICY_EVERYONE,  # Default value
            history_public_to_subscribers=stream.history_public_to_subscribers,
            first_message_id=stream.first_message_id,
            subscribers=subscribers or [],
            unread_count=unread_count,
            is_muted=is_muted,
            pin_to_top=pin_to_top,
            topics=topics or [],
        )


class StreamCreatePayload(BaseModel):
    """Request payload for stream creation."""

    name: Annotated[str, Field(min_length=1, max_length=60, description="Stream name")]
    description: Annotated[
        str, Field(default="", max_length=1024, description="Stream description")
    ]
    is_private: Annotated[bool, Field(default=False, description="Whether the stream is private")]
    is_announcement_only: Annotated[
        bool, Field(default=False, description="Whether only admins can post")
    ]
    history_public_to_subscribers: Annotated[
        bool | None,
        Field(default=None, description="Whether history is visible to new subscribers"),
    ]


class StreamUpdatePayload(BaseModel):
    """Request payload for stream update."""

    name: Annotated[
        str | None, Field(default=None, min_length=1, max_length=60, description="New stream name")
    ]
    description: Annotated[
        str | None, Field(default=None, max_length=1024, description="New stream description")
    ]
    is_private: Annotated[
        bool | None, Field(default=None, description="Whether the stream is private")
    ]
    is_announcement_only: Annotated[
        bool | None, Field(default=None, description="Whether only admins can post")
    ]

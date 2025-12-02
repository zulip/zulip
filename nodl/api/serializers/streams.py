"""Serializers for stream-related API responses."""

from typing import Annotated, Optional

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
    first_message_id: Annotated[Optional[int], Field(description="ID of first message")]
    subscribers: Annotated[list[int], Field(default=[], description="List of subscriber user IDs")]

    @classmethod
    def from_stream(
        cls,
        stream: Stream,
        subscribers: Optional[list[int]] = None,
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
    """Serializer for stream list with unread counts."""

    unread_count: Annotated[int, Field(default=0, description="Number of unread messages")]
    topics: Annotated[
        list[TopicSerializer], Field(default=[], description="Topics in the stream")
    ]

    @classmethod
    def from_stream_with_unread(
        cls,
        stream: Stream,
        unread_count: int = 0,
        subscribers: Optional[list[int]] = None,
        topics: Optional[list[TopicSerializer]] = None,
    ) -> "StreamListSerializer":
        """Create serializer from Stream model with unread count."""
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
            topics=topics or [],
        )


class StreamCreatePayload(BaseModel):
    """Request payload for stream creation."""

    name: Annotated[str, Field(min_length=1, max_length=60, description="Stream name")]
    description: Annotated[str, Field(default="", max_length=1024, description="Stream description")]
    is_private: Annotated[bool, Field(default=False, description="Whether the stream is private")]
    is_announcement_only: Annotated[
        bool, Field(default=False, description="Whether only admins can post")
    ]
    history_public_to_subscribers: Annotated[
        Optional[bool], Field(default=None, description="Whether history is visible to new subscribers")
    ]


class StreamUpdatePayload(BaseModel):
    """Request payload for stream update."""

    name: Annotated[Optional[str], Field(default=None, min_length=1, max_length=60, description="New stream name")]
    description: Annotated[Optional[str], Field(default=None, max_length=1024, description="New stream description")]
    is_private: Annotated[Optional[bool], Field(default=None, description="Whether the stream is private")]
    is_announcement_only: Annotated[
        Optional[bool], Field(default=None, description="Whether only admins can post")
    ]

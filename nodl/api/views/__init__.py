"""API views for nodl endpoints."""

from nodl.api.views.internal import (
    deactivate_realm,
    sync_realm,
    sync_user,
)
from nodl.api.views.streams import (
    archive_stream,
    create_stream,
    get_stream,
    get_stream_topics,
    list_streams,
    subscribe_to_stream,
    unsubscribe_from_stream,
    update_stream,
)

__all__ = [
    # Internal sync views
    "deactivate_realm",
    "sync_realm",
    "sync_user",
    # Stream views
    "archive_stream",
    "create_stream",
    "get_stream",
    "get_stream_topics",
    "list_streams",
    "subscribe_to_stream",
    "unsubscribe_from_stream",
    "update_stream",
]

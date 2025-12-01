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
from nodl.api.views.users import (
    get_current_user,
    get_user,
    list_users,
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
    # User views
    "get_current_user",
    "get_user",
    "list_users",
]

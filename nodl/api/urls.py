"""URL configuration for nodl API endpoints."""

from django.urls import path

from nodl.api.views import deactivate_realm, sync_realm, sync_user
from nodl.api.views.events import (
    events_view,
    register_queue,
    send_typing,
    update_presence,
)
from nodl.api.views.messages import (
    delete_message,
    edit_message,
    get_message,
    get_unread_counts,
    list_dm_conversations,
    mark_messages_as_read,
    messages_dispatch,
    mute_dm_user,
    send_message,
    unmute_dm_user,
    update_flags,
    update_flags_narrow,
)
from nodl.api.views.streams import (
    archive_stream,
    create_stream,
    get_stream,
    get_stream_topics,
    list_streams,
    mute_stream,
    pin_stream,
    subscribe_to_stream,
    unmute_stream,
    unpin_stream,
    unsubscribe_from_stream,
    update_stream,
)
from nodl.api.views.task_streams import (
    archive_task_stream,
    sync_task_stream,
    sync_task_stream_subscribers,
)
from nodl.api.views.uploads import upload_file
from nodl.api.views.users import (
    get_current_user,
    get_user,
    list_users,
)

# Real-time API endpoints - authenticated via JWT
# These MUST come first to intercept before Zulip's HTTP Basic Auth endpoints
urlpatterns = [
    # Event queue registration and polling
    path("api/v1/register", register_queue, name="nodl_register_queue"),
    path("api/v1/events", events_view, name="nodl_events"),
    # Typing indicators
    path("api/v1/typing", send_typing, name="nodl_typing"),
    # Internal API endpoints - authenticated via service key
    # These are prefixed with /api/v1/internal/ by convention
    path("api/v1/internal/users/sync", sync_user, name="nodl_sync_user"),
    path("api/v1/internal/realms/sync", sync_realm, name="nodl_sync_realm"),
    path("api/v1/internal/realms/deactivate", deactivate_realm, name="nodl_deactivate_realm"),
    path("api/v1/internal/task-streams/sync", sync_task_stream, name="nodl_sync_task_stream"),
    path(
        "api/v1/internal/task-streams/subscribers",
        sync_task_stream_subscribers,
        name="nodl_sync_task_stream_subscribers",
    ),
    path(
        "api/v1/internal/task-streams/archive",
        archive_task_stream,
        name="nodl_archive_task_stream",
    ),
    # User REST API endpoints - authenticated via JWT
    # Presence endpoint - authenticated via JWT
    path("api/v1/users/me/presence", update_presence, name="nodl_presence"),
    # IMPORTANT: /users/me MUST come BEFORE /users to match correctly
    path("api/v1/users/me", get_current_user, name="nodl_current_user"),
    path("api/v1/users", list_users, name="nodl_list_users"),
    path("api/v1/users/<int:user_id>", get_user, name="nodl_get_user"),
    # Stream REST API endpoints - authenticated via JWT
    path("api/v1/streams", list_streams, name="nodl_list_streams"),
    path("api/v1/streams/create", create_stream, name="nodl_create_stream"),
    path("api/v1/streams/<int:stream_id>", get_stream, name="nodl_get_stream"),
    path("api/v1/streams/<int:stream_id>/update", update_stream, name="nodl_update_stream"),
    path("api/v1/streams/<int:stream_id>/archive", archive_stream, name="nodl_archive_stream"),
    path("api/v1/streams/<int:stream_id>/topics", get_stream_topics, name="nodl_get_stream_topics"),
    path(
        "api/v1/streams/<int:stream_id>/subscribe",
        subscribe_to_stream,
        name="nodl_subscribe_stream",
    ),
    path(
        "api/v1/streams/<int:stream_id>/unsubscribe",
        unsubscribe_from_stream,
        name="nodl_unsubscribe_stream",
    ),
    path("api/v1/streams/<int:stream_id>/mute", mute_stream, name="nodl_mute_stream"),
    path("api/v1/streams/<int:stream_id>/unmute", unmute_stream, name="nodl_unmute_stream"),
    path("api/v1/streams/<int:stream_id>/pin", pin_stream, name="nodl_pin_stream"),
    path("api/v1/streams/<int:stream_id>/unpin", unpin_stream, name="nodl_unpin_stream"),
    # Message flags endpoints - authenticated via JWT (MUST come before /messages)
    path("api/v1/messages/flags/narrow", update_flags_narrow, name="nodl_update_flags_narrow"),
    path("api/v1/messages/flags", update_flags, name="nodl_update_flags"),
    # Message REST API endpoints - authenticated via JWT
    path("api/v1/messages", messages_dispatch, name="nodl_messages"),
    path("api/v1/messages/send", send_message, name="nodl_send_message"),
    path("api/v1/messages/<int:message_id>", get_message, name="nodl_get_message"),
    path("api/v1/messages/<int:message_id>/edit", edit_message, name="nodl_edit_message"),
    path("api/v1/messages/<int:message_id>/delete", delete_message, name="nodl_delete_message"),
    # Reactions: Handled by Zulip's native rest_dispatch (POST/DELETE on same URL).
    # JWT auth supported via the _jwt_wrapper branch in rest_dispatch (zerver/lib/rest.py).
    # Frontend sends emoji params as query params (request.GET), not JSON body.
    # DM REST API endpoints - authenticated via JWT
    path("api/v1/dm/conversations", list_dm_conversations, name="nodl_list_dm_conversations"),
    path("api/v1/dm/<int:user_id>/mute", mute_dm_user, name="nodl_mute_dm_user"),
    path("api/v1/dm/<int:user_id>/unmute", unmute_dm_user, name="nodl_unmute_dm_user"),
    # Unread counts and mark-as-read endpoints - authenticated via JWT
    path("api/v1/unread", get_unread_counts, name="nodl_unread_counts"),
    path("api/v1/messages/read", mark_messages_as_read, name="nodl_mark_read"),
    # File upload endpoint - authenticated via JWT
    path("api/v1/uploads", upload_file, name="nodl_upload_file"),
]

# i18n URL patterns (empty for API endpoints)
i18n_urlpatterns: list = []

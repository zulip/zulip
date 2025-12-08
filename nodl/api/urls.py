"""URL configuration for nodl API endpoints."""

from django.urls import path

from nodl.api.views import deactivate_realm, sync_realm, sync_user
from nodl.api.views.events import (
    events_view,
    register_queue,
    send_typing,
)
from nodl.api.views.messages import (
    delete_message,
    edit_message,
    get_message,
    list_dm_conversations,
    list_messages,
    send_message,
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
    # User REST API endpoints - authenticated via JWT
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
    path("api/v1/streams/<int:stream_id>/subscribe", subscribe_to_stream, name="nodl_subscribe_stream"),
    path("api/v1/streams/<int:stream_id>/unsubscribe", unsubscribe_from_stream, name="nodl_unsubscribe_stream"),
    # Message REST API endpoints - authenticated via JWT
    path("api/v1/messages", list_messages, name="nodl_list_messages"),
    path("api/v1/messages/send", send_message, name="nodl_send_message"),
    path("api/v1/messages/<int:message_id>", get_message, name="nodl_get_message"),
    path("api/v1/messages/<int:message_id>/edit", edit_message, name="nodl_edit_message"),
    path("api/v1/messages/<int:message_id>/delete", delete_message, name="nodl_delete_message"),
    # DM REST API endpoints - authenticated via JWT
    path("api/v1/dm/conversations", list_dm_conversations, name="nodl_list_dm_conversations"),
]

# i18n URL patterns (empty for API endpoints)
i18n_urlpatterns: list = []

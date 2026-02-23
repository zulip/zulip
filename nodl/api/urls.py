"""URL configuration for nodl API endpoints."""

from django.urls import path

from nodl.api.views import deactivate_realm, sync_realm, sync_user
from nodl.api.views.events import (
    events_view,
    register_queue,
    send_typing,
)
from nodl.api.views.messages import (
    add_reaction,
    delete_message,
    edit_message,
    get_message,
    get_unread_counts,
    list_dm_conversations,
    list_messages,
    mark_messages_as_read,
    mute_dm_user,
    remove_reaction,
    send_message,
    unmute_dm_user,
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
    # Message REST API endpoints - authenticated via JWT
    path("api/v1/messages", list_messages, name="nodl_list_messages"),
    path("api/v1/messages/send", send_message, name="nodl_send_message"),
    path("api/v1/messages/<int:message_id>", get_message, name="nodl_get_message"),
    path("api/v1/messages/<int:message_id>/edit", edit_message, name="nodl_edit_message"),
    path("api/v1/messages/<int:message_id>/delete", delete_message, name="nodl_delete_message"),
    # Reaction REST API endpoints - authenticated via JWT
    path("api/v1/messages/<int:message_id>/reactions", add_reaction, name="nodl_add_reaction"),
    path(
        "api/v1/messages/<int:message_id>/reactions/<str:emoji_name>",
        remove_reaction,
        name="nodl_remove_reaction",
    ),
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

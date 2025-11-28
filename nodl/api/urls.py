"""URL configuration for nodl API endpoints."""

from django.urls import path

from nodl.api.views import deactivate_realm, sync_realm, sync_user
from nodl.api.views.messages import (
    delete_message,
    edit_message,
    get_message,
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

# Internal API endpoints - authenticated via service key
# These are prefixed with /api/v1/internal/ by convention
urlpatterns = [
    path("api/v1/internal/users/sync", sync_user, name="nodl_sync_user"),
    path("api/v1/internal/realms/sync", sync_realm, name="nodl_sync_realm"),
    path("api/v1/internal/realms/deactivate", deactivate_realm, name="nodl_deactivate_realm"),
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
]

# i18n URL patterns (empty for API endpoints)
i18n_urlpatterns: list = []

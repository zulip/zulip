from django.conf.urls import include
from django.urls import path

from zerver.lib.rest import rest_path
from zerver.tornado.views import (
    cleanup_event_queue,
    get_events,
    get_events_internal,
    notify,
    web_reload_clients,
)

# Minimal URL configuration for Tornado.  Tornado only serves 5
# endpoints, but without a dedicated urlconf it resolves every request
# against the full Django URL configuration (~800 patterns), wasting
# significant CPU on regex matching.

api_and_json_patterns = [
    rest_path(
        "events",
        GET=(get_events, {"narrow_user_session_cache"}),
        DELETE=(cleanup_event_queue, {"narrow_user_session_cache"}),
    ),
]

urlpatterns = [
    path("api/v1/", include(api_and_json_patterns)),
    path("json/", include(api_and_json_patterns)),
    path("api/internal/notify_tornado", notify),
    path("api/internal/web_reload_clients", web_reload_clients),
    path("api/v1/events/internal", get_events_internal),
]

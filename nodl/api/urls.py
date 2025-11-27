"""URL configuration for nodl API endpoints."""

from django.urls import path

from nodl.api.views import deactivate_realm, sync_realm, sync_user

# Internal API endpoints - authenticated via service key
# These are prefixed with /api/v1/internal/ by convention
urlpatterns = [
    path("api/v1/internal/users/sync", sync_user, name="nodl_sync_user"),
    path("api/v1/internal/realms/sync", sync_realm, name="nodl_sync_realm"),
    path("api/v1/internal/realms/deactivate", deactivate_realm, name="nodl_deactivate_realm"),
]

# i18n URL patterns (empty for API endpoints)
i18n_urlpatterns: list = []

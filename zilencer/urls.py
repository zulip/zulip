from typing import Any

from django.conf.urls import include
from django.urls import path

from zilencer.auth import remote_server_path
from zilencer.views import (
    deactivate_remote_server,
    register_remote_push_device,
    register_remote_server,
    remote_server_check_analytics,
    remote_server_notify_push,
    remote_server_post_analytics,
    unregister_all_remote_push_devices,
    unregister_remote_push_device,
)

i18n_urlpatterns: Any = []

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    remote_server_path("remotes/push/register", POST=register_remote_push_device),
    remote_server_path("remotes/push/unregister", POST=unregister_remote_push_device),
    remote_server_path("remotes/push/unregister/all", POST=unregister_all_remote_push_devices),
    remote_server_path("remotes/push/notify", POST=remote_server_notify_push),
    # Push signup doesn't use the REST API, since there's no auth.
    path("remotes/server/register", register_remote_server),
    remote_server_path("remotes/server/deactivate", POST=deactivate_remote_server),
    # For receiving table data used in analytics and billing
    remote_server_path("remotes/server/analytics", POST=remote_server_post_analytics),
    remote_server_path("remotes/server/analytics/status", GET=remote_server_check_analytics),
]

urlpatterns = [
    path("api/v1/", include(v1_api_and_json_patterns)),
    path("json/", include(v1_api_and_json_patterns)),
]

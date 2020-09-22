from typing import Any

from django.conf.urls import include
from django.urls import path

from zerver.lib.rest import rest_path
from zilencer.views import (
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
    rest_path('remotes/push/register',
              POST=register_remote_push_device),
    rest_path('remotes/push/unregister',
              POST=unregister_remote_push_device),
    rest_path('remotes/push/unregister/all',
              POST=unregister_all_remote_push_devices),
    rest_path('remotes/push/notify',
              POST=remote_server_notify_push),

    # Push signup doesn't use the REST API, since there's no auth.
    path('remotes/server/register', register_remote_server),

    # For receiving table data used in analytics and billing
    rest_path('remotes/server/analytics',
              POST=remote_server_post_analytics),
    rest_path('remotes/server/analytics/status',
              GET=remote_server_check_analytics),
]

urlpatterns = [
    path('api/v1/', include(v1_api_and_json_patterns)),
    path('json/', include(v1_api_and_json_patterns)),
]

from typing import Any

from django.conf.urls import include
from django.urls import path

import zilencer.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns: Any = []

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    path('remotes/push/register', rest_dispatch,
         {'POST': 'zilencer.views.register_remote_push_device'}),
    path('remotes/push/unregister', rest_dispatch,
         {'POST': 'zilencer.views.unregister_remote_push_device'}),
    path('remotes/push/unregister/all', rest_dispatch,
         {'POST': 'zilencer.views.unregister_all_remote_push_devices'}),
    path('remotes/push/notify', rest_dispatch,
         {'POST': 'zilencer.views.remote_server_notify_push'}),

    # Push signup doesn't use the REST API, since there's no auth.
    path('remotes/server/register', zilencer.views.register_remote_server),

    # For receiving table data used in analytics and billing
    path('remotes/server/analytics', rest_dispatch,
         {'POST': 'zilencer.views.remote_server_post_analytics'}),
    path('remotes/server/analytics/status', rest_dispatch,
         {'GET': 'zilencer.views.remote_server_check_analytics'}),
]

urlpatterns = [
    path('api/v1/', include(v1_api_and_json_patterns)),
    path('json/', include(v1_api_and_json_patterns)),
]

from typing import Any

from django.conf.urls import include, url

import zilencer.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns = []  # type: Any

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    url('^remotes/push/register$', rest_dispatch,
        {'POST': 'zilencer.views.register_remote_push_device'}),
    url('^remotes/push/unregister$', rest_dispatch,
        {'POST': 'zilencer.views.unregister_remote_push_device'}),
    url('^remotes/push/notify$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_notify_push'}),

    # Push signup doesn't use the REST API, since there's no auth.
    url('^remotes/server/register$', zilencer.views.register_remote_server),

    # For receiving InstallationCount data and similar analytics.
    url('^remotes/server/analytics$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_post_analytics'}),
    url('^remotes/server/analytics/status$', rest_dispatch,
        {'GET': 'zilencer.views.remote_server_check_analytics'}),
]

urlpatterns = [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

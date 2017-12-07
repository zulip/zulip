from typing import Any

from django.conf.urls import include, url

import zilencer.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns = []  # type: Any

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    url('^remotes/push/register$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_register_push'}),
    url('^remotes/push/register_server$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_register_server'}),
    url('^remotes/push/unregister$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_unregister_push'}),
    url('^remotes/push/notify$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_notify_push'}),
]

urlpatterns = [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

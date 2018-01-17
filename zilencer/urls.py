from typing import Any

from django.conf.urls import include, url

import zilencer.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns = [
    url(r'^billing/$', zilencer.views.add_payment_method),
]  # type: Any

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    url('^remotes/push/register$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_register_push'}),
    url('^remotes/push/unregister$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_unregister_push'}),
    url('^remotes/push/notify$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_notify_push'}),
]

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

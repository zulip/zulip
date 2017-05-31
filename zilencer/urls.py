from django.conf.urls import url, include
from typing import Any

from zerver.lib.rest import rest_dispatch

import zilencer.views
import zerver.views.report

i18n_urlpatterns = []  # type: Any

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    url('^deployment/report_error$', rest_dispatch,
        {'POST': 'zerver.views.report.report_error'}),
    url('^remotes/push/register$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_register_push'}),
    url('^remotes/push/unregister$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_unregister_push'}),
    url('^remotes/push/notify$', rest_dispatch,
        {'POST': 'zilencer.views.remote_server_notify_push'}),
]

urlpatterns = [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

from typing import Any

from django.conf.urls import url, include
from django.views.generic import TemplateView

from zerver.lib.rest import rest_dispatch

import zilencer.views
import zerver.views.report

i18n_urlpatterns = [
    url(r'^remotes/register/$',
        zilencer.views.register_remote_server,
        name='zilencer.views.register_remote_server'),
    url(r'^remotes/register/confirm/(?P<confirmation_key>[\w]+)',
        zilencer.views.confirm,
        name='zilencer.views.confirm'),
    url(r'^remotes/send_confirm/(?P<email>[\S]+)?',
        TemplateView.as_view(template_name='zilencer/send_confirm.html'),
        name='remotes_send_confirm'),
]  # type: Any

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
    url(r'', include(i18n_urlpatterns)),
]

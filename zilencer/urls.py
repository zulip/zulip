from django.conf.urls import url, include
from zerver.lib.rest import rest_dispatch
import zilencer.views
import zerver.views.report

i18n_urlpatterns = [
]

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    url('^deployment/feedback$', rest_dispatch,
        {'POST': 'zilencer.views.submit_feedback'}),
    url('^deployment/report_error$', rest_dispatch,
        {'POST': 'zerver.views.report.report_error'}),
]

urlpatterns = [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

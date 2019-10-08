from typing import Any

from django.views.generic import TemplateView
from django.conf.urls import include, url

import corporate.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns = [
    # Zephyr/MIT
    url(r'^zephyr/$', TemplateView.as_view(template_name='corporate/zephyr.html')),
    url(r'^zephyr-mirror/$', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),

    # Billing
    url(r'^billing/$', corporate.views.billing_home, name='corporate.views.billing_home'),
    url(r'^upgrade/$', corporate.views.initial_upgrade, name='corporate.views.initial_upgrade'),
]  # type: Any

v1_api_and_json_patterns = [
    url(r'^billing/upgrade$', rest_dispatch,
        {'POST': 'corporate.views.upgrade'}),
    url(r'^billing/downgrade$', rest_dispatch,
        {'POST': 'corporate.views.downgrade'}),
    url(r'^billing/sources/change', rest_dispatch,
        {'POST': 'corporate.views.replace_payment_source'}),
]

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

from typing import Any

from django.conf.urls import include
from django.urls import path
from django.views.generic import TemplateView

import corporate.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns: Any = [
    # Zephyr/MIT
    path('zephyr/', TemplateView.as_view(template_name='corporate/zephyr.html')),
    path('zephyr-mirror/', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),

    path('jobs/', TemplateView.as_view(template_name='corporate/jobs.html')),

    # Billing
    path('billing/', corporate.views.billing_home, name='corporate.views.billing_home'),
    path('upgrade/', corporate.views.initial_upgrade, name='corporate.views.initial_upgrade'),
]

v1_api_and_json_patterns = [
    path('billing/upgrade', rest_dispatch,
         {'POST': 'corporate.views.upgrade'}),
    path('billing/plan/change', rest_dispatch,
         {'POST': 'corporate.views.change_plan_status'}),
    path('billing/sources/change', rest_dispatch,
         {'POST': 'corporate.views.replace_payment_source'}),
]

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    path('api/v1/', include(v1_api_and_json_patterns)),
    path('json/', include(v1_api_and_json_patterns)),
]

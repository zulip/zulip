from typing import Any

from django.conf.urls import include
from django.urls import path
from django.views.generic import TemplateView

from corporate.views import (
    billing_home,
    change_plan_status,
    initial_upgrade,
    replace_payment_source,
    sponsorship,
    upgrade,
)
from zerver.lib.rest import rest_path

i18n_urlpatterns: Any = [
    # Zephyr/MIT
    path('zephyr/', TemplateView.as_view(template_name='corporate/zephyr.html')),
    path('zephyr-mirror/', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),

    path('jobs/', TemplateView.as_view(template_name='corporate/jobs.html')),

    # Billing
    path('billing/', billing_home),
    path('upgrade/', initial_upgrade, name='initial_upgrade'),
]

v1_api_and_json_patterns = [
    rest_path('billing/upgrade',
              POST=upgrade),
    rest_path('billing/sponsorship',
              POST=sponsorship),
    rest_path('billing/plan/change',
              POST=change_plan_status),
    rest_path('billing/sources/change',
              POST=replace_payment_source),
]

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    path('api/v1/', include(v1_api_and_json_patterns)),
    path('json/', include(v1_api_and_json_patterns)),
]

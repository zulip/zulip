from typing import Any

from django.conf.urls import include, url
from django.urls import path
from django.views.generic import RedirectView, TemplateView

import corporate.landing
import corporate.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns: Any = [
    url(r'^$', corporate.landing.home, name='corporate.landing.home'),

    # Landing page, features pages, signup form, etc.
    url(r'^hello/$', corporate.landing.hello_view, name='landing-page'),
    url(r'^new-user/$', RedirectView.as_view(url='/hello', permanent=True)),
    url(r'^features/$', corporate.landing.landing_view, {'template_name': 'features.html'}),
    url(r'^plans/$', corporate.landing.plans_view, name='plans'),
    url(r'^apps/(.*)$', corporate.landing.apps_view, name='corporate.landingps_view'),
    url(r'^team/$', corporate.landing.team_view),
    url(r'^history/$', corporate.landing.landing_view, {'template_name': 'history.html'}),
    url(r'^why-zulip/$', corporate.landing.landing_view, {'template_name': 'why-zulip.html'}),
    url(r'^for/open-source/$', corporate.landing.landing_view,
        {'template_name': 'for-open-source.html'}),
    url(r'^for/research/$', corporate.landing.landing_view,
        {'template_name': 'for-research.html'}),
    url(r'^for/companies/$', corporate.landing.landing_view,
        {'template_name': 'for-companies.html'}),
    url(r'^for/working-groups-and-communities/$', corporate.landing.landing_view,
        {'template_name': 'for-working-groups-and-communities.html'}),
    url(r'^security/$', corporate.landing.landing_view, {'template_name': 'security.html'}),
    url(r'^atlassian/$', corporate.landing.landing_view, {'template_name': 'atlassian.html'}),

    # Zephyr/MIT
    path('zephyr/', TemplateView.as_view(template_name='zephyr.html')),
    path('zephyr-mirror/', TemplateView.as_view(template_name='zephyr-mirror.html')),

    path('jobs/', TemplateView.as_view(template_name='jobs.html')),

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

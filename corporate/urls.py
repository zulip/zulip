from typing import Any

from django.views.generic import TemplateView
from django.conf.urls import include, url

import corporate.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns = [
    # Zephyr/MIT
    url(r'^zephyr/$', TemplateView.as_view(template_name='corporate/zephyr.html')),
    url(r'^zephyr-mirror/$', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),

    url(r'^jobs/$', TemplateView.as_view(template_name='corporate/jobs.html')),

    # Billing pages
    url(r'^billing/$', corporate.views.billing_home,
        name='corporate.views.billing_home'),
    url(r'^upgrade/$', corporate.views.initial_upgrade,
        name='corporate.views.initial_upgrade'),

    # Billing pages for self-hosted orgs
    # These should be in 1-to-1 correspondence with the "Billing pages" section above.
    # 16 comes from RemoteZulipServer.URL_KEY_LENGTH
    url(r'^billing/(?P<url_key>[\S]{16})/$', corporate.views.billing_home,
        name='corporate.views.billing_home__server'),
    url(r'^billing/(?P<url_key>[\S]{16})/upgrade/$', corporate.views.initial_upgrade,
        name='corporate.views.initial_upgrade__server'),
]  # type: Any

v1_api_and_json_patterns = [
    # These billing URLs have allow_anonymous_user_web set in order to
    # support billing for the remote server use case; if one isn't
    # authenticated via cookie, one will need to pass the required
    # url_key in the arguments.
    url(r'^billing/upgrade$', rest_dispatch,
        {'POST': ('corporate.views.upgrade', {'allow_anonymous_user_web'})}),
    url(r'^billing/plan/change$', rest_dispatch,
        {'POST': ('corporate.views.change_plan_at_end_of_cycle', {'allow_anonymous_user_web'})}),
    url(r'^billing/sources/change', rest_dispatch,
        {'POST': ('corporate.views.replace_payment_source', {'allow_anonymous_user_web'})}),
]

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

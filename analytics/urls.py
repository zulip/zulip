from django.conf.urls import include, url

import analytics.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns = [
    # Server admin (user_profile.is_staff) visible stats pages
    url(r'^activity$', analytics.views.get_activity,
        name='analytics.views.get_activity'),
    url(r'^realm_activity/(?P<realm_str>[\S]+)/$', analytics.views.get_realm_activity,
        name='analytics.views.get_realm_activity'),
    url(r'^user_activity/(?P<email>[\S]+)/$', analytics.views.get_user_activity,
        name='analytics.views.get_user_activity'),

    url(r'^stats/realm/(?P<realm_str>[\S]+)/$', analytics.views.stats_for_realm,
        name='analytics.views.stats_for_realm'),
    url(r'^stats/installation$', analytics.views.stats_for_installation,
        name='analytics.views.stats_for_installation'),
    url(r'^stats/remote/(?P<remote_server_id>[\S]+)/installation$',
        analytics.views.stats_for_remote_installation,
        name='analytics.views.stats_for_remote_installation'),
    url(r'^stats/remote/(?P<remote_server_id>[\S]+)/realm/(?P<remote_realm_id>[\S]+)/$',
        analytics.views.stats_for_remote_realm,
        name='analytics.views.stats_for_remote_realm'),

    # User-visible stats page
    url(r'^stats$', analytics.views.stats,
        name='analytics.views.stats'),
]

# These endpoints are a part of the API (V1), which uses:
# * REST verbs
# * Basic auth (username:password is email:apiKey)
# * Takes and returns json-formatted data
#
# See rest_dispatch in zerver.lib.rest for an explanation of auth methods used
#
# All of these paths are accessed by either a /json or /api prefix
v1_api_and_json_patterns = [
    # get data for the graphs at /stats
    url(r'^analytics/chart_data$', rest_dispatch,
        {'GET': 'analytics.views.get_chart_data'}),
    url(r'^analytics/chart_data/realm/(?P<realm_str>[\S]+)$', rest_dispatch,
        {'GET': 'analytics.views.get_chart_data_for_realm'}),
    url(r'^analytics/chart_data/installation$', rest_dispatch,
        {'GET': 'analytics.views.get_chart_data_for_installation'}),
    url(r'^analytics/chart_data/remote/(?P<remote_server_id>[\S]+)/installation$', rest_dispatch,
        {'GET': 'analytics.views.get_chart_data_for_remote_installation'}),
    url(r'^analytics/chart_data/remote/(?P<remote_server_id>[\S]+)/realm/(?P<remote_realm_id>[\S]+)$',
        rest_dispatch,
        {'GET': 'analytics.views.get_chart_data_for_remote_realm'}),
]

i18n_urlpatterns += [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

urlpatterns = i18n_urlpatterns

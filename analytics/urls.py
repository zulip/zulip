from django.conf.urls import include
from django.urls import path

import analytics.views
from zerver.lib.rest import rest_dispatch

i18n_urlpatterns = [
    # Server admin (user_profile.is_staff) visible stats pages
    path('activity', analytics.views.get_activity,
         name='analytics.views.get_activity'),
    path('activity/support', analytics.views.support,
         name='analytics.views.support'),
    path('realm_activity/<str:realm_str>/', analytics.views.get_realm_activity,
         name='analytics.views.get_realm_activity'),
    path('user_activity/<str:email>/', analytics.views.get_user_activity,
         name='analytics.views.get_user_activity'),

    path('stats/realm/<str:realm_str>/', analytics.views.stats_for_realm,
         name='analytics.views.stats_for_realm'),
    path('stats/installation', analytics.views.stats_for_installation,
         name='analytics.views.stats_for_installation'),
    path('stats/remote/<int:remote_server_id>/installation',
         analytics.views.stats_for_remote_installation,
         name='analytics.views.stats_for_remote_installation'),
    path('stats/remote/<int:remote_server_id>/realm/<int:remote_realm_id>/',
         analytics.views.stats_for_remote_realm,
         name='analytics.views.stats_for_remote_realm'),

    # User-visible stats page
    path('stats', analytics.views.stats,
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
    path('analytics/chart_data', rest_dispatch,
         {'GET': 'analytics.views.get_chart_data'}),
    path('analytics/chart_data/realm/<str:realm_str>', rest_dispatch,
         {'GET': 'analytics.views.get_chart_data_for_realm'}),
    path('analytics/chart_data/installation', rest_dispatch,
         {'GET': 'analytics.views.get_chart_data_for_installation'}),
    path('analytics/chart_data/remote/<int:remote_server_id>/installation', rest_dispatch,
         {'GET': 'analytics.views.get_chart_data_for_remote_installation'}),
    path('analytics/chart_data/remote/<int:remote_server_id>/realm/<int:remote_realm_id>',
         rest_dispatch,
         {'GET': 'analytics.views.get_chart_data_for_remote_realm'}),
]

i18n_urlpatterns += [
    path('api/v1/', include(v1_api_and_json_patterns)),
    path('json/', include(v1_api_and_json_patterns)),
]

urlpatterns = i18n_urlpatterns

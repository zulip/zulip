from django.conf import settings
from django.conf.urls import include
from django.urls import path
from django.urls.resolvers import URLPattern, URLResolver

from analytics.views.stats import (
    get_chart_data,
    get_chart_data_for_installation,
    get_chart_data_for_realm,
    get_chart_data_for_stream,
    stats,
    stats_for_installation,
    stats_for_realm,
)
from zerver.lib.rest import rest_path

i18n_urlpatterns: list[URLPattern | URLResolver] = [
    # Server admin (user_profile.is_staff) visible stats pages
    path("stats/realm/<realm_str>/", stats_for_realm),
    path("stats/installation", stats_for_installation),
    # User-visible stats page
    path("stats", stats, name="stats"),
]

if settings.ZILENCER_ENABLED:
    from analytics.views.stats import stats_for_remote_installation, stats_for_remote_realm

    i18n_urlpatterns += [
        path("stats/remote/<int:remote_server_id>/installation", stats_for_remote_installation),
        path(
            "stats/remote/<int:remote_server_id>/realm/<int:remote_realm_id>/",
            stats_for_remote_realm,
        ),
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
    rest_path("analytics/chart_data", GET=get_chart_data),
    rest_path("analytics/chart_data/stream/<stream_id>", GET=get_chart_data_for_stream),
    rest_path("analytics/chart_data/realm/<realm_str>", GET=get_chart_data_for_realm),
    rest_path("analytics/chart_data/installation", GET=get_chart_data_for_installation),
]

if settings.ZILENCER_ENABLED:
    from analytics.views.stats import (
        get_chart_data_for_remote_installation,
        get_chart_data_for_remote_realm,
    )

    v1_api_and_json_patterns += [
        rest_path(
            "analytics/chart_data/remote/<int:remote_server_id>/installation",
            GET=get_chart_data_for_remote_installation,
        ),
        rest_path(
            "analytics/chart_data/remote/<int:remote_server_id>/realm/<int:remote_realm_id>",
            GET=get_chart_data_for_remote_realm,
        ),
    ]

i18n_urlpatterns += [
    path("api/v1/", include(v1_api_and_json_patterns)),
    path("json/", include(v1_api_and_json_patterns)),
]

urlpatterns = i18n_urlpatterns

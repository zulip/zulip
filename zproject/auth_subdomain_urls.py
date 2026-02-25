from .urls import (
    healthcheck_urls,
    i18n_auth_urls,
    i18n_landing_urls,
    i18n_login_urls,
    mobile_compatibility_urls,
    social_auth_urls,
    v1_api_mobile_urls,
)

urlpatterns = (
    i18n_landing_urls
    + i18n_login_urls
    + i18n_auth_urls
    + mobile_compatibility_urls
    + social_auth_urls
    + v1_api_mobile_urls
    + healthcheck_urls
)

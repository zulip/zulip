from .urls import (
    extra_installed_app_urls,
    healthcheck_urls,
    i18n_landing_urls,
    i18n_login_urls,
    self_hosting_management_urls,
    self_hosting_registration_urls,
)

urlpatterns = (
    i18n_landing_urls
    + i18n_login_urls
    + self_hosting_management_urls
    + self_hosting_registration_urls
    + extra_installed_app_urls
    + healthcheck_urls
)

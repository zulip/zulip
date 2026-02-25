from django.conf.urls.i18n import i18n_patterns

from .urls import realm_host_i18n_urls, realm_host_urls

urlpatterns = i18n_patterns(*realm_host_i18n_urls) + realm_host_urls

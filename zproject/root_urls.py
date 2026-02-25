from django.conf.urls.i18n import i18n_patterns

from .urls import i18n_urls, root_host_urls

urlpatterns = i18n_patterns(*i18n_urls) + root_host_urls

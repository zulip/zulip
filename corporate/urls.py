from django.conf.urls import patterns, url
from django.views.generic import TemplateView, RedirectView

i18n_urlpatterns = [
    # Zephyr/MIT
    url(r'^zephyr/$', TemplateView.as_view(template_name='corporate/zephyr.html')),
    url(r'^mit/$', TemplateView.as_view(template_name='corporate/mit.html')),
    url(r'^zephyr-mirror/$', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),

    # Terms of service and privacy policy
    url(r'^terms-enterprise/$',  TemplateView.as_view(template_name='corporate/terms-enterprise.html')),
    url(r'^privacy/$', TemplateView.as_view(template_name='corporate/privacy.html')),
]

urlpatterns = patterns('', *i18n_urlpatterns)

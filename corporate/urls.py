from django.conf.urls import patterns, url
from django.views.generic import TemplateView, RedirectView

urlpatterns = patterns('',
    # Zephyr/MIT
    url(r'^zephyr/$', TemplateView.as_view(template_name='corporate/zephyr.html')),
    url(r'^mit/$', TemplateView.as_view(template_name='corporate/mit.html')),
    url(r'^zephyr-mirror/$', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),

    # Terms of service and privacy policy
    url(r'^terms/$',   TemplateView.as_view(template_name='corporate/terms.html')),
    url(r'^terms-enterprise/$',  TemplateView.as_view(template_name='corporate/terms-enterprise.html')),
    url(r'^privacy/$', TemplateView.as_view(template_name='corporate/privacy.html')),

)

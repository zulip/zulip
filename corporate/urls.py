from django.conf.urls import patterns, url
from django.views.generic import TemplateView, RedirectView

urlpatterns = patterns('',
    # Zephyr/MIT
    url(r'^zephyr/$', TemplateView.as_view(template_name='corporate/zephyr.html')),
    url(r'^mit/$', TemplateView.as_view(template_name='corporate/mit.html')),
    url(r'^zephyr-mirror/$', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),
)

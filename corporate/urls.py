from django.conf.urls import url
from django.views.generic import TemplateView

i18n_urlpatterns = [
    # Zephyr/MIT
    url(r'^zephyr/$', TemplateView.as_view(template_name='corporate/zephyr.html')),
    url(r'^zephyr-mirror/$', TemplateView.as_view(template_name='corporate/zephyr-mirror.html')),
]

urlpatterns = i18n_urlpatterns

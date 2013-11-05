from django.conf.urls import patterns, url
from django.views.generic import TemplateView

urlpatterns = patterns('',
    # Job postings
    url(r'^jobs/$', TemplateView.as_view(template_name='corporate/jobs/index.html')),
    url(r'^jobs/lead-designer/$', TemplateView.as_view(template_name='corporate/jobs/lead-designer.html')),
)

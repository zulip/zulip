from django.conf.urls import patterns, url, include

urlpatterns = patterns('zilencer.views',
    url('^feedback$', 'rest_dispatch',
          {'POST': 'submit_feedback'}),
)

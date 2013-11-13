from django.conf.urls import patterns, url, include

urlpatterns = patterns('zilencer.views',
    url('^feedback$', 'rest_dispatch',
          {'POST': 'submit_feedback'}),
    url('^report_error$', 'rest_dispatch',
          {'POST': 'report_error'}),
    url('^endpoints$', 'lookup_endpoints_for_user'),
)

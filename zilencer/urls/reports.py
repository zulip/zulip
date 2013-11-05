from django.conf.urls import patterns, url

urlpatterns = patterns('zilencer.views',
    url(r'^activity$', 'get_activity'),
    url(r'^realm_activity/(?P<realm>[\S]+)/$', 'get_realm_activity'),
    url(r'^user_activity/(?P<email>[\S]+)/$', 'get_user_activity'),
)


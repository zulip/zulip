from django.conf.urls import patterns, url

i18n_urlpatterns = [
    url(r'^activity$', 'analytics.views.get_activity'),
    url(r'^realm_activity/(?P<realm>[\S]+)/$', 'analytics.views.get_realm_activity'),
    url(r'^user_activity/(?P<email>[\S]+)/$', 'analytics.views.get_user_activity'),
]

urlpatterns = patterns('', *i18n_urlpatterns)

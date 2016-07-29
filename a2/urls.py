from django.conf.urls import patterns, url

i18n_urlpatterns = [
    url(r'^a2$', 'a2.views.get_activity'),
    url(r'^a2realm/(?P<realm>[\S]+)/$', 'a2.views.get_realm_activity'),
    url(r'^a2user/(?P<email>[\S]+)/$', 'a2.views.get_user_activity'),
]

urlpatterns = patterns('', *i18n_urlpatterns)

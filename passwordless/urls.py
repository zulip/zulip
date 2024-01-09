from django.conf.urls import patterns, url


urlpatterns = patterns('',
    url(r'^$', 'passwordless.views.home', name='home'),
    url(r'^done/$', 'passwordless.views.done', name='done'),
    url(r'^login-form/$', 'passwordless.views.login_form', name='login_form'),
    url(r'^validation-sent/$', 'passwordless.views.validation_sent',
        name='validation_sent'),
    url(r'^token-login/(?P<token>[^/]+)/$', 'passwordless.views.token_login',
        name='token_login'),
    url(r'^logout/$', 'passwordless.views.logout', name='logout')
)

from django.conf.urls import url
from . import views

i18n_urlpatterns = [
    url(r'^activity$', views.get_activity),
    url(r'^realm_activity/(?P<realm>[\S]+)/$', views.get_realm_activity),
    url(r'^user_activity/(?P<email>[\S]+)/$', views.get_user_activity),
]

urlpatterns = i18n_urlpatterns

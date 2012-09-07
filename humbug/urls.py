from django.conf import settings
from django.conf.urls import patterns, url
import os.path

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'zephyr.views.home', name='home'),
    url(r'^update$', 'zephyr.views.update', name='update'),
    url(r'^get_updates_longpoll$', 'zephyr.views.get_updates_longpoll', name='get_updates_longpoll'),
    url(r'^zephyr/', 'zephyr.views.zephyr', name='zephyr'),
    url(r'^forge_zephyr/', 'zephyr.views.forge_zephyr', name='forge_zephyr'),
    url(r'^accounts/home/', 'zephyr.views.accounts_home', name='accounts_home'),
    url(r'^accounts/login/', 'django.contrib.auth.views.login', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/logout/', 'django.contrib.auth.views.logout', {'template_name': 'zephyr/index.html'}),
    url(r'^accounts/register/', 'zephyr.views.register', name='register'),
    url(r'^subscriptions/$', 'zephyr.views.subscriptions', name='subscriptions'),
    url(r'^subscriptions/manage/$', 'zephyr.views.manage_subscriptions', name='manage_subscriptions'),
    url(r'^subscriptions/add/$', 'zephyr.views.add_subscriptions', name='add_subscriptions'),
    url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': os.path.join(settings.SITE_ROOT, '..', 'zephyr', 'static/')}),
    url(r'^subscriptions/exists/(?P<zephyr_class>.*)$', 'zephyr.views.class_exists', name='class_exists'),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)

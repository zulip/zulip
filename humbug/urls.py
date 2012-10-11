from django.conf import settings
from django.conf.urls import patterns, url
import os.path

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'zephyr.views.home', name='home'),
    url(r'^update$', 'zephyr.views.update', name='update'),
    url(r'^get_updates$', 'zephyr.views.get_updates', name='get_updates'),
    url(r'^api/v1/get_messages$', 'zephyr.views.api_get_messages', name='api_get_messages'),
    url(r'^api/v1/send_message$', 'zephyr.views.api_send_message', name='api_send_message'),
    url(r'^send_message/', 'zephyr.views.send_message', name='send_message'),
    url(r'^accounts/home/', 'zephyr.views.accounts_home', name='accounts_home'),
    # We have two entries for accounts/login to allow reverses on the Django
    # view we're wrapping to continue to function.
    url(r'^accounts/login/', 'zephyr.views.login_page', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/login/', 'django.contrib.auth.views.login', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/logout/', 'django.contrib.auth.views.logout', {'template_name': 'zephyr/index.html'}),
    url(r'^accounts/register/', 'zephyr.views.register', name='register'),
    url(r'^accounts/send_confirm/(?P<email>[\S]+)?', 'django.views.generic.simple.direct_to_template', {'template': 'zephyr/accounts_send_confirm.html'}, name='send_confirm'),
    url(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)', 'confirmation.views.confirm', name='confirm'),
    url(r'^settings/change/$', 'zephyr.views.change_settings', name='change_settings'),
    url(r'^json/subscriptions/list$', 'zephyr.views.json_list_subscriptions', name='list_subscriptions'),
    url(r'^json/subscriptions/remove$', 'zephyr.views.json_remove_subscription', name='remove_subscription'),
    url(r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/favicon.ico'}),
    url(r'^json/subscriptions/add$', 'zephyr.views.json_add_subscription', name='add_subscription'),
    url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': os.path.join(settings.SITE_ROOT, '..', 'zephyr', 'static/')}),
    url(r'^subscriptions/exists/(?P<stream>.*)$', 'zephyr.views.stream_exists', name='stream_exists'),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)

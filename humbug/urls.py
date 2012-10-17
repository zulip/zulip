from django.conf import settings
from django.conf.urls import patterns, url
import os.path

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'zephyr.views.home', name='home'),
    # We have two entries for accounts/login to allow reverses on the Django
    # view we're wrapping to continue to function.
    url(r'^accounts/login/', 'zephyr.views.login_page', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/login/', 'django.contrib.auth.views.login', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/logout/', 'django.contrib.auth.views.logout', {'template_name': 'zephyr/index.html'}),

    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/update_pointer$', 'zephyr.views.json_update_pointer', name='json_update_pointer'),
    url(r'^json/get_updates$', 'zephyr.views.json_get_updates', name='json_get_updates'),
    url(r'^json/send_message/', 'zephyr.views.json_send_message', name='json_send_message'),
    url(r'^json/settings/change/$', 'zephyr.views.json_change_settings', name='json_change_settings'),
    url(r'^json/subscriptions/list$', 'zephyr.views.json_list_subscriptions', name='json_list_subscriptions'),
    url(r'^json/subscriptions/remove$', 'zephyr.views.json_remove_subscription', name='json_remove_subscription'),
    url(r'^json/subscriptions/add$', 'zephyr.views.json_add_subscription', name='json_add_subscription'),
    url(r'^json/subscriptions/exists$', 'zephyr.views.json_stream_exists', name='json_stream_exists'),

    # These are json format views used by the API.  They require an API key.
    url(r'^api/v1/get_messages$', 'zephyr.views.api_get_messages', name='api_get_messages'),
    url(r'^api/v1/get_public_streams$', 'zephyr.views.api_get_public_streams', name='api_get_public_streams'),
    url(r'^api/v1/get_subscriptions$', 'zephyr.views.api_get_subscriptions', name='api_get_subscriptions'),
    url(r'^api/v1/subscribe$', 'zephyr.views.api_subscribe', name='api_subscribe'),
    url(r'^api/v1/send_message$', 'zephyr.views.api_send_message', name='api_send_message'),

    url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': os.path.join(settings.SITE_ROOT, '..', 'zephyr', 'static/')}),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)

if settings.ALLOW_REGISTER:
    urlpatterns += patterns('',
        url(r'^accounts/home/', 'zephyr.views.accounts_home', name='accounts_home'),
        url(r'^accounts/register/', 'zephyr.views.accounts_register', name='accounts_register'),
        url(r'^accounts/send_confirm/(?P<email>[\S]+)?', 'django.views.generic.simple.direct_to_template', {'template': 'zephyr/accounts_send_confirm.html'}, name='send_confirm'),
        url(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)', 'confirmation.views.confirm', name='confirm'),
    )

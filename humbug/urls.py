from django.conf import settings
from django.conf.urls import patterns, url
import os.path

urlpatterns = patterns('',
    url(r'^$', 'zephyr.views.home'),
    # We have two entries for accounts/login to allow reverses on the Django
    # view we're wrapping to continue to function.
    url(r'^accounts/login/', 'zephyr.views.login_page', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/login/', 'django.contrib.auth.views.login', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/logout/', 'django.contrib.auth.views.logout_then_login'),

    url(r'^accounts/password/reset/$', 'django.contrib.auth.views.password_reset',
        {'post_reset_redirect' : '/accounts/password/reset/done/',
            'template_name': 'zephyr/reset.html',
            'email_template_name': 'registration/password_reset_email.txt',
            }),
    url(r'^accounts/password/reset/done/$', 'django.contrib.auth.views.password_reset_done',
        {'template_name': 'zephyr/reset_emailed.html'}),
    url(r'^accounts/password/reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 'django.contrib.auth.views.password_reset_confirm',
        {'post_reset_redirect' : '/accounts/password/done/', 'template_name': 'zephyr/reset_confirm.html'}),
    url(r'^accounts/password/done/$', 'django.contrib.auth.views.password_reset_complete',
        {'template_name': 'zephyr/reset_done.html'}),


    # Registration views, require a confirmation ID.
    url(r'^accounts/register/', 'zephyr.views.accounts_register'),
    url(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)', 'confirmation.views.confirm'),

    # Terms of service and privacy policy
    url(r'^terms$',   'django.views.generic.simple.direct_to_template', {'template': 'zephyr/terms.html'}),
    url(r'^privacy$', 'django.views.generic.simple.direct_to_template', {'template': 'zephyr/privacy.html'}),

    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/update_pointer$', 'zephyr.views.json_update_pointer'),
    url(r'^json/get_updates$', 'zephyr.views.json_get_updates'),
    url(r'^json/get_old_messages$', 'zephyr.views.json_get_old_messages'),
    url(r'^json/send_message/', 'zephyr.views.json_send_message'),
    url(r'^json/settings/change/$', 'zephyr.views.json_change_settings'),
    url(r'^json/subscriptions/list$', 'zephyr.views.json_list_subscriptions'),
    url(r'^json/subscriptions/remove$', 'zephyr.views.json_remove_subscription'),
    url(r'^json/subscriptions/add$', 'zephyr.views.json_add_subscriptions'),
    url(r'^json/subscriptions/exists$', 'zephyr.views.json_stream_exists'),
    url(r'^json/fetch_api_key$', 'zephyr.views.json_fetch_api_key'),

    # These are json format views used by the API.  They require an API key.
    url(r'^api/v1/get_profile$', 'zephyr.views.api_get_profile'),
    url(r'^api/v1/get_messages$', 'zephyr.views.api_get_messages'),
    url(r'^api/v1/get_old_messages$', 'zephyr.views.api_get_old_messages'),
    url(r'^api/v1/get_public_streams$', 'zephyr.views.api_get_public_streams'),
    url(r'^api/v1/get_subscriptions$', 'zephyr.views.api_get_subscriptions'),
    url(r'^api/v1/subscribe$', 'zephyr.views.api_subscribe'),
    url(r'^api/v1/send_message$', 'zephyr.views.api_send_message'),
    url(r'^api/v1/update_pointer$', 'zephyr.views.api_update_pointer'),
    # This json format view used by the API accepts a username password/pair and returns an API key.
    url(r'^api/v1/fetch_api_key$', 'zephyr.views.api_fetch_api_key'),

    url(r'^robots\.txt$', 'django.views.generic.simple.redirect_to', {'url': '/static/public/robots.txt'}),

    # Used internally for communication between Django and Tornado processes
    url(r'^notify_new_message$', 'zephyr.views.notify_new_message'),
    url(r'^notify_pointer_update$', 'zephyr.views.notify_pointer_update'),
)

if settings.ALLOW_REGISTER:
    urlpatterns += patterns('',
        url(r'^accounts/home/', 'zephyr.views.accounts_home'),
        url(r'^accounts/send_confirm/(?P<email>[\S]+)?', 'django.views.generic.simple.direct_to_template',
            {'template': 'zephyr/accounts_send_confirm.html'}, name='send_confirm'),
    )

if settings.DEBUG:
    urlpatterns += patterns('',
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(settings.SITE_ROOT, '../zephyr/static-access-control')}))

from django.conf import settings
from django.conf.urls import patterns, url
from django.views.generic import TemplateView, RedirectView
import os.path
import zephyr.forms

urlpatterns = patterns('',
    url(r'^$', 'zephyr.views.home'),
    url(r'^accounts/login/openid/$', 'django_openid_auth.views.login_begin', name='openid-login'),
    url(r'^accounts/login/openid/done/$', 'django_openid_auth.views.login_complete', name='openid-complete'),
    # We have two entries for accounts/login to allow reverses on the Django
    # view we're wrapping to continue to function.
    url(r'^accounts/login/',  'zephyr.views.login_page',         {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/login/',  'django.contrib.auth.views.login', {'template_name': 'zephyr/login.html'}),
    url(r'^accounts/logout/', 'zephyr.views.logout_then_login'),

    url(r'^accounts/password/reset/$', 'django.contrib.auth.views.password_reset',
        {'post_reset_redirect' : '/accounts/password/reset/done/',
            'template_name': 'zephyr/reset.html',
            'email_template_name': 'registration/password_reset_email.txt',
            }),
    url(r'^accounts/password/reset/done/$', 'django.contrib.auth.views.password_reset_done',
        {'template_name': 'zephyr/reset_emailed.html'}),
    url(r'^accounts/password/reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 'django.contrib.auth.views.password_reset_confirm',
        {'post_reset_redirect' : '/accounts/password/done/', 'template_name': 'zephyr/reset_confirm.html',
         'set_password_form' : zephyr.forms.LoggingSetPasswordForm}),
    url(r'^accounts/password/done/$', 'django.contrib.auth.views.password_reset_complete',
        {'template_name': 'zephyr/reset_done.html'}),


    url(r'^activity$', 'zephyr.views.get_activity'),

    # Registration views, require a confirmation ID.
    url(r'^accounts/home/', 'zephyr.views.accounts_home'),
    url(r'^accounts/send_confirm/(?P<email>[\S]+)?',
        TemplateView.as_view(template_name='zephyr/accounts_send_confirm.html'), name='send_confirm'),
    url(r'^accounts/register/', 'zephyr.views.accounts_register'),
    url(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)', 'confirmation.views.confirm'),

    # Portico-styled page used to provide email confirmation of terms acceptance.
    url(r'^accounts/accept_terms', 'zephyr.views.accounts_accept_terms'),

    # Terms of service and privacy policy
    url(r'^terms$',   TemplateView.as_view(template_name='zephyr/terms.html')),
    url(r'^privacy$', TemplateView.as_view(template_name='zephyr/privacy.html')),

    # "About Humbug" information
    url(r'^what-is-humbug$', TemplateView.as_view(template_name='zephyr/what-is-humbug.html')),
    url(r'^new-user$', TemplateView.as_view(template_name='zephyr/new-user.html')),

    # API and integrations documentation
    url(r'^api$', TemplateView.as_view(template_name='zephyr/api.html')),
    url(r'^integrations$', TemplateView.as_view(template_name='zephyr/integrations.html')),
    url(r'^zephyr$', TemplateView.as_view(template_name='zephyr/zephyr.html')),
    url(r'^apps$', TemplateView.as_view(template_name='zephyr/apps.html')),

    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/get_updates$',              'zephyr.tornadoviews.json_get_updates'),
    url(r'^json/update_pointer$',           'zephyr.views.json_update_pointer'),
    url(r'^json/get_old_messages$',         'zephyr.views.json_get_old_messages'),
    url(r'^json/get_public_streams$',       'zephyr.views.json_get_public_streams'),
    url(r'^json/send_message$',             'zephyr.views.json_send_message'),
    url(r'^json/invite_users$',             'zephyr.views.json_invite_users'),
    url(r'^json/settings/change$',          'zephyr.views.json_change_settings'),
    url(r'^json/subscriptions/list$',       'zephyr.views.json_list_subscriptions'),
    url(r'^json/subscriptions/remove$',     'zephyr.views.json_remove_subscriptions'),
    url(r'^json/subscriptions/add$',        'zephyr.views.json_add_subscriptions'),
    url(r'^json/subscriptions/exists$',     'zephyr.views.json_stream_exists'),
    url(r'^json/subscriptions/property$',   'zephyr.views.json_subscription_property'),
    url(r'^json/get_subscribers$',          'zephyr.views.json_get_subscribers'),
    url(r'^json/fetch_api_key$',            'zephyr.views.json_fetch_api_key'),
    url(r'^json/get_members$',              'zephyr.views.json_get_members'),
    url(r'^json/update_active_status$',     'zephyr.views.json_update_active_status'),
    url(r'^json/get_active_statuses$',      'zephyr.views.json_get_active_statuses'),
    url(r'^json/tutorial_send_message$',    'zephyr.views.json_tutorial_send_message'),
    url(r'^json/change_enter_sends$',       'zephyr.views.json_change_enter_sends'),
    url(r'^json/get_profile$',              'zephyr.views.json_get_profile'),
    url(r'^json/report_error$',             'zephyr.views.json_report_error'),
    url(r'^json/update_message_flags$',     'zephyr.views.json_update_flags'),

    # These are json format views used by the API.  They require an API key.
    url(r'^api/v1/get_messages$',           'zephyr.tornadoviews.api_get_messages'),
    url(r'^api/v1/get_profile$',            'zephyr.views.api_get_profile'),
    url(r'^api/v1/get_old_messages$',       'zephyr.views.api_get_old_messages'),
    url(r'^api/v1/get_public_streams$',     'zephyr.views.api_get_public_streams'),
    url(r'^api/v1/subscriptions/list$',     'zephyr.views.api_list_subscriptions'),
    url(r'^api/v1/subscriptions/add$',      'zephyr.views.api_add_subscriptions'),
    url(r'^api/v1/subscriptions/remove$',   'zephyr.views.api_remove_subscriptions'),
    url(r'^api/v1/get_subscribers$',        'zephyr.views.api_get_subscribers'),
    url(r'^api/v1/send_message$',           'zephyr.views.api_send_message'),
    url(r'^api/v1/update_pointer$',         'zephyr.views.api_update_pointer'),
    url(r'^api/v1/external/github$',        'zephyr.views.api_github_landing'),
    url(r'^api/v1/get_members$',            'zephyr.views.api_get_members'),

    # This json format view used by the API accepts a username password/pair and returns an API key.
    url(r'^api/v1/fetch_api_key$',          'zephyr.views.api_fetch_api_key'),

    url(r'^robots\.txt$', RedirectView.as_view(url='/static/robots.txt')),

    # Used internally for communication between Django and Tornado processes
    url(r'^notify_new_message$',            'zephyr.tornadoviews.notify_new_message'),
    url(r'^notify_pointer_update$',         'zephyr.tornadoviews.notify_pointer_update'),
)

if not settings.DEPLOYED:
    use_prod_static = getattr(settings, 'PIPELINE', False)
    static_root = os.path.join(settings.SITE_ROOT,
        '../prod-static/serve' if use_prod_static else '../zephyr/static')

    urlpatterns += patterns('',
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': static_root}))

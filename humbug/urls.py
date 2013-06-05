from django.conf import settings
from django.conf.urls import patterns, url
from django.views.generic import TemplateView, RedirectView
import os.path
import zephyr.forms

# NB: There are several other pieces of code which route requests by URL:
#
#   - runtornado.py has its own URL list for Tornado views.  See the
#     invocation of web.Application in that file.
#
#   - The Nginx config knows which URLs to route to Django or Tornado.
#
#   - Likewise for the local dev server in tools/run-dev.py.

urlpatterns = patterns('',
    url(r'^$', 'zephyr.views.home'),
    url(r'^accounts/login/openid/$', 'django_openid_auth.views.login_begin', name='openid-login'),
    url(r'^accounts/login/openid/done/$', 'zephyr.views.process_openid_login', name='openid-complete'),
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
    url(r'^accounts/accept_terms/$', 'zephyr.views.accounts_accept_terms'),

    # Terms of service and privacy policy
    url(r'^terms/$',   TemplateView.as_view(template_name='zephyr/terms.html')),
    url(r'^privacy/$', TemplateView.as_view(template_name='zephyr/privacy.html')),

    # "About Humbug" information
    url(r'^what-is-humbug/$', TemplateView.as_view(template_name='zephyr/what-is-humbug.html')),
    url(r'^new-user/$', TemplateView.as_view(template_name='zephyr/new-user.html')),
    url(r'^features/$', TemplateView.as_view(template_name='zephyr/features.html')),

    # Landing page, signup form, and nice register URL
    url(r'^hello/$', TemplateView.as_view(template_name='zephyr/hello.html'),
                                         name='landing-page'),
    url(r'^signup/$', TemplateView.as_view(template_name='zephyr/signup.html'),
                                         name='signup'),
    url(r'^signup/sign-me-up$', 'zephyr.views.beta_signup_submission', name='beta-signup-submission'),
    url(r'^register/$', 'zephyr.views.accounts_home', name='register'),
    url(r'^login/$',  'zephyr.views.login_page', {'template_name': 'zephyr/login.html'}),

    # API and integrations documentation
    url(r'^api/$', TemplateView.as_view(template_name='zephyr/api.html')),
    url(r'^api/endpoints/$', 'zephyr.views.api_endpoint_docs'),
    url(r'^integrations/$', TemplateView.as_view(template_name='zephyr/integrations.html')),
    url(r'^zephyr/$', TemplateView.as_view(template_name='zephyr/zephyr.html')),
    url(r'^apps$', TemplateView.as_view(template_name='zephyr/apps.html')),

    # Job postings
    url(r'^jobs/$', TemplateView.as_view(template_name='zephyr/jobs/index.html')),
    url(r'^jobs/lead-designer/$', TemplateView.as_view(template_name='zephyr/jobs/lead-designer.html')),

    url(r'^robots\.txt$', RedirectView.as_view(url='/static/robots.txt')),
)

urlpatterns += patterns('zephyr.views',
    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/update_pointer$',           'json_update_pointer'),
    url(r'^json/get_old_messages$',         'json_get_old_messages'),
    url(r'^json/get_public_streams$',       'json_get_public_streams'),
    url(r'^json/send_message$',             'json_send_message'),
    url(r'^json/invite_users$',             'json_invite_users'),
    url(r'^json/settings/change$',          'json_change_settings'),
    url(r'^json/subscriptions/list$',       'json_list_subscriptions'),
    url(r'^json/subscriptions/remove$',     'json_remove_subscriptions'),
    url(r'^json/subscriptions/add$',        'json_add_subscriptions'),
    url(r'^json/subscriptions/exists$',     'json_stream_exists'),
    url(r'^json/subscriptions/property$',   'json_subscription_property'),
    url(r'^json/get_subscribers$',          'json_get_subscribers'),
    url(r'^json/fetch_api_key$',            'json_fetch_api_key'),
    url(r'^json/get_members$',              'json_get_members'),
    url(r'^json/update_active_status$',     'json_update_active_status'),
    url(r'^json/get_active_statuses$',      'json_get_active_statuses'),
    url(r'^json/tutorial_send_message$',    'json_tutorial_send_message'),
    url(r'^json/tutorial_status$',          'json_tutorial_status'),
    url(r'^json/change_enter_sends$',       'json_change_enter_sends'),
    url(r'^json/get_profile$',              'json_get_profile'),
    url(r'^json/report_error$',             'json_report_error'),
    url(r'^json/update_message_flags$',     'json_update_flags'),
    url(r'^json/register$',                 'json_events_register'),
    url(r'^json/upload_file$',              'json_upload_file'),
    url(r'^json/messages_in_narrow$',       'json_messages_in_narrow'),
    url(r'^json/create_bot$',               'json_create_bot'),
    url(r'^json/get_bots$',                 'json_get_bots'),
    url(r'^json/update_onboarding_steps$',  'json_update_onboarding_steps'),
    url(r'^json/update_message$',           'json_update_message'),
    url(r'^json/fetch_raw_message$',        'json_fetch_raw_message'),

    # These are json format views used by the API.  They require an API key.
    url(r'^api/v1/get_profile$',            'api_get_profile'),
    url(r'^api/v1/get_old_messages$',       'api_get_old_messages'),
    url(r'^api/v1/get_public_streams$',     'api_get_public_streams'),
    url(r'^api/v1/subscriptions/list$',     'api_list_subscriptions'),
    url(r'^api/v1/subscriptions/add$',      'api_add_subscriptions'),
    url(r'^api/v1/subscriptions/remove$',   'api_remove_subscriptions'),
    url(r'^api/v1/get_subscribers$',        'api_get_subscribers'),
    url(r'^api/v1/send_message$',           'api_send_message'),
    url(r'^api/v1/update_pointer$',         'api_update_pointer'),
    url(r'^api/v1/get_members$',            'api_get_members'),

    # This json format view used by the API accepts a username password/pair and returns an API key.
    url(r'^api/v1/fetch_api_key$',          'api_fetch_api_key'),

    # JSON format views used by the redesigned API, accept basic auth username:password.
    # GET returns messages, possibly filtered, POST sends a message
    url(r'^api/v1/messages$', 'rest_dispatch',
            {'GET':  'get_old_messages_backend',
             'PATCH': 'update_message_backend',
             'POST': 'send_message_backend'}),
    url(r'^api/v1/streams$', 'rest_dispatch',
            {'GET':  'get_public_streams_backend'}),
    # GET returns "stream info" (undefined currently?), HEAD returns whether stream exists (200 or 404)
    url(r'^api/v1/streams/(?P<stream_name>.*)/members$', 'rest_dispatch',
            {'GET': 'get_subscribers_backend'}),
    url(r'^api/v1/streams/(?P<stream_name>.*)$', 'rest_dispatch',
            {'HEAD': 'stream_exists_backend',
             'GET': 'stream_exists_backend'}),
    url(r'^api/v1/users$', 'rest_dispatch',
            {'GET': 'get_members_backend'}),
    url(r'^api/v1/users/me$', 'rest_dispatch',
            {'GET': 'get_profile_backend'}),
    url(r'^api/v1/users/me/enter-sends$', 'rest_dispatch',
            {'POST': 'json_change_enter_sends'}),
    url(r'^api/v1/users/me/pointer$', 'rest_dispatch',
            {'GET': 'get_pointer_backend',
             'PUT': 'update_pointer_backend'}),
    # GET lists your streams, POST bulk adds, PATCH bulk modifies/removes
    url(r'^api/v1/users/me/subscriptions$', 'rest_dispatch',
            {'GET': 'list_subscriptions_backend',
             'POST': 'add_subscriptions_backend',
             'PATCH': 'update_subscriptions_backend'}),
    url(r'^api/v1/register$',               'rest_dispatch',
            {'POST': 'api_events_register'}),

    # These are integration-specific web hook callbacks
    url(r'^api/v1/external/beanstalk$',    'api_beanstalk_webhook'),
    url(r'^api/v1/external/github$',        'api_github_landing'),
    url(r'^api/v1/external/jira$',          'api_jira_webhook'),
    url(r'^api/v1/external/pivotal$',       'api_pivotal_webhook'),
)

urlpatterns += patterns('zephyr.tornadoviews',
    # Tornado views
    url(r'^api/v1/get_messages$',           'api_get_messages'),
    url(r'^api/v1/messages/latest$',        'rest_get_messages'),
    url(r'^json/get_updates$',              'json_get_updates'),
    url(r'^api/v1/events$',                 'rest_get_events'),
    url(r'^json/get_events$',               'json_get_events'),
    # Used internally for communication between Django and Tornado processes
    url(r'^notify_tornado$',                'notify'),
)

if not settings.DEPLOYED:
    use_prod_static = getattr(settings, 'PIPELINE', False)
    static_root = os.path.join(settings.SITE_ROOT,
        '../prod-static/serve' if use_prod_static else '../zephyr/static')

    urlpatterns += patterns('',
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': static_root}))

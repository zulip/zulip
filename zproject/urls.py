from django.conf import settings
from django.conf.urls import patterns, url, include
from django.views.generic import TemplateView, RedirectView
import os.path
import zerver.forms

# NB: There are several other pieces of code which route requests by URL:
#
#   - runtornado.py has its own URL list for Tornado views.  See the
#     invocation of web.Application in that file.
#
#   - The Nginx config knows which URLs to route to Django or Tornado.
#
#   - Likewise for the local dev server in tools/run-dev.py.

urlpatterns = patterns('',
    url(r'^$', 'zerver.views.home'),
    url(r'^accounts/login/openid/$', 'django_openid_auth.views.login_begin', name='openid-login'),
    url(r'^accounts/login/openid/done/$', 'zerver.views.process_openid_login', name='openid-complete'),
    url(r'^accounts/login/openid/done/$', 'django_openid_auth.views.login_complete', name='openid-complete'),
    url(r'^accounts/login/sso/$', 'zerver.views.remote_user_sso'),
    # We have two entries for accounts/login to allow reverses on the Django
    # view we're wrapping to continue to function.
    url(r'^accounts/login/',  'zerver.views.login_page',         {'template_name': 'zerver/login.html'}),
    url(r'^accounts/login/',  'django.contrib.auth.views.login', {'template_name': 'zerver/login.html'}),
    url(r'^accounts/logout/', 'zerver.views.logout_then_login'),
    url(r'^accounts/webathena_kerberos_login/', 'zerver.views.webathena_kerberos_login'),

    url(r'^accounts/password/reset/$', 'django.contrib.auth.views.password_reset',
        {'post_reset_redirect' : '/accounts/password/reset/done/',
            'template_name': 'zerver/reset.html',
            'email_template_name': 'registration/password_reset_email.txt',
            }),
    url(r'^accounts/password/reset/done/$', 'django.contrib.auth.views.password_reset_done',
        {'template_name': 'zerver/reset_emailed.html'}),
    url(r'^accounts/password/reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 'django.contrib.auth.views.password_reset_confirm',
        {'post_reset_redirect' : '/accounts/password/done/', 'template_name': 'zerver/reset_confirm.html',
         'set_password_form' : zerver.forms.LoggingSetPasswordForm}),
    url(r'^accounts/password/done/$', 'django.contrib.auth.views.password_reset_complete',
        {'template_name': 'zerver/reset_done.html'}),

    # Registration views, require a confirmation ID.
    url(r'^accounts/home/', 'zerver.views.accounts_home'),
    url(r'^accounts/send_confirm/(?P<email>[\S]+)?',
        TemplateView.as_view(template_name='zerver/accounts_send_confirm.html'), name='send_confirm'),
    url(r'^accounts/register/', 'zerver.views.accounts_register'),
    url(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)', 'confirmation.views.confirm'),
    url(r'^invite/$', 'zerver.views.initial_invite_page', name='initial-invite-users'),

    # Portico-styled page used to provide email confirmation of terms acceptance.
    url(r'^accounts/accept_terms/$', 'zerver.views.accounts_accept_terms'),

    # Terms of service and privacy policy
    url(r'^terms/$',   TemplateView.as_view(template_name='zerver/terms.html')),
    url(r'^privacy/$', TemplateView.as_view(template_name='zerver/privacy.html')),

    # Login/registration
    url(r'^register/$', 'zerver.views.accounts_home', name='register'),
    url(r'^login/$',  'zerver.views.login_page', {'template_name': 'zerver/login.html'}),

    # A registration page that passes through the domain, for totally open realms.
    url(r'^register/(?P<domain>\S+)/$', 'zerver.views.accounts_home_with_domain'),

    # API and integrations documentation
    url(r'^api/$', TemplateView.as_view(template_name='zerver/api.html')),
    url(r'^api/endpoints/$', 'zerver.views.api_endpoint_docs'),
    url(r'^integrations/$', TemplateView.as_view(template_name='zerver/integrations.html')),
    url(r'^apps/$', TemplateView.as_view(template_name='zerver/apps.html')),

    url(r'^robots\.txt$', RedirectView.as_view(url='/static/robots.txt')),
)

# These are used for localserver development. On a real localserver instance,
# these files would be served by nginx.
if not settings.DEPLOYED and settings.LOCAL_UPLOADS_DIR is not None:
    urlpatterns += patterns('',
        url(r'^user_avatars/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")}),
        url(r'^user_uploads/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "files")}),
    )

urlpatterns += patterns('zerver.views',
    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/update_pointer$',           'json_update_pointer'),
    url(r'^json/get_old_messages$',         'json_get_old_messages'),
    url(r'^json/get_public_streams$',       'json_get_public_streams'),
    url(r'^json/rename_stream$',            'json_rename_stream'),
    url(r'^json/send_message$',             'json_send_message'),
    url(r'^json/invite_users$',             'json_invite_users'),
    url(r'^json/bulk_invite_users$',        'json_bulk_invite_users'),
    url(r'^json/settings/change$',          'json_change_settings'),
    url(r'^json/notify_settings/change$',   'json_change_notify_settings'),
    url(r'^json/subscriptions/remove$',     'json_remove_subscriptions'),
    url(r'^json/subscriptions/add$',        'json_add_subscriptions'),
    url(r'^json/subscriptions/exists$',     'json_stream_exists'),
    url(r'^json/subscriptions/property$',   'json_subscription_property'),
    url(r'^json/get_subscribers$',          'json_get_subscribers'),
    url(r'^json/fetch_api_key$',            'json_fetch_api_key'),
    url(r'^json/get_members$',              'json_get_members'),
    url(r'^json/update_active_status$',     'json_update_active_status'),
    url(r'^json/get_active_statuses$',      'json_get_active_statuses'),
    url(r'^json/tutorial_status$',          'json_tutorial_status'),
    url(r'^json/change_enter_sends$',       'json_change_enter_sends'),
    url(r'^json/get_profile$',              'json_get_profile'),
    url(r'^json/report_error$',             'json_report_error'),
    url(r'^json/report_send_time$',         'json_report_send_time'),
    url(r'^json/update_message_flags$',     'json_update_flags'),
    url(r'^json/register$',                 'json_events_register'),
    url(r'^json/upload_file$',              'json_upload_file'),
    url(r'^json/messages_in_narrow$',       'json_messages_in_narrow'),
    url(r'^json/create_bot$',               'json_create_bot'),
    url(r'^json/get_bots$',                 'json_get_bots'),
    url(r'^json/update_message$',           'json_update_message'),
    url(r'^json/fetch_raw_message$',        'json_fetch_raw_message'),
    url(r'^json/refer_friend$',             'json_refer_friend'),
    url(r'^json/set_alert_words$',          'json_set_alert_words'),
    url(r'^json/set_muted_topics$',         'json_set_muted_topics'),
    url(r'^json/set_avatar$',               'json_set_avatar'),

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

    # These are integration-specific web hook callbacks
    url(r'^api/v1/external/beanstalk$' ,    'webhooks.api_beanstalk_webhook'),
    url(r'^api/v1/external/github$',        'webhooks.api_github_landing'),
    url(r'^api/v1/external/jira$',          'webhooks.api_jira_webhook'),
    url(r'^api/v1/external/pivotal$',       'webhooks.api_pivotal_webhook'),
    url(r'^api/v1/external/newrelic$',      'webhooks.api_newrelic_webhook'),
    url(r'^api/v1/external/bitbucket$',     'webhooks.api_bitbucket_webhook'),
    url(r'^api/v1/external/desk$',          'webhooks.api_deskdotcom_webhook'),
    url(r'^api/v1/external/stash$',         'webhooks.api_stash_webhook'),

    url(r'^user_uploads/(?P<realm_id>\d*)/(?P<filename>.*)', 'rest_dispatch',
        {'GET': 'get_uploaded_file'}),
)

v1_api_and_json_patterns = patterns('zerver.views',
    # JSON format views used by the redesigned API, accept basic auth username:password.
    # GET returns messages, possibly filtered, POST sends a message
    url(r'^messages$', 'rest_dispatch',
            {'GET':  'get_old_messages_backend',
             'PATCH': 'update_message_backend',
             'POST': 'send_message_backend'}),
    url(r'^messages/render$', 'rest_dispatch',
            {'GET':  'render_message_backend'}),
    url(r'^messages/flags$', 'rest_dispatch',
            {'POST':  'update_message_flags'}),
    url(r'^streams$', 'rest_dispatch',
            {'GET':  'get_streams_backend'}),
    # GET returns "stream info" (undefined currently?), HEAD returns whether stream exists (200 or 404)
    url(r'^streams/(?P<stream_name>.*)/members$', 'rest_dispatch',
            {'GET': 'get_subscribers_backend'}),
    url(r'^streams/(?P<stream_name>.*)$', 'rest_dispatch',
            {'HEAD': 'stream_exists_backend',
             'GET': 'stream_exists_backend'}),
    url(r'^users$', 'rest_dispatch',
            {'GET': 'get_members_backend'}),
    url(r'^users/me$', 'rest_dispatch',
            {'GET': 'get_profile_backend'}),
    url(r'^users/me/enter-sends$', 'rest_dispatch',
            {'POST': 'json_change_enter_sends'}),
    url(r'^users/me/pointer$', 'rest_dispatch',
            {'GET': 'get_pointer_backend',
             'PUT': 'update_pointer_backend'}),
    # GET lists your streams, POST bulk adds, PATCH bulk modifies/removes
    url(r'^users/me/subscriptions$', 'rest_dispatch',
            {'GET': 'list_subscriptions_backend',
             'POST': 'add_subscriptions_backend',
             'PATCH': 'update_subscriptions_backend'}),
    url(r'^users/me/alert_words$', 'rest_dispatch',
            {'GET': 'list_alert_words',
             'PUT': 'set_alert_words',
             'PATCH': 'add_alert_words',
             'DELETE': 'remove_alert_words'}),
    url(r'^users/me/api_key/regenerate$', 'rest_dispatch',
            {'POST': 'regenerate_api_key'}),
    # Endpoint used by iOS devices to register their
    # unique APNS device token
    url(r'^users/me/apns_device_token$', 'rest_dispatch',
        {'POST'  : 'add_apns_device_token',
         'DELETE': 'remove_apns_device_token'}),
    url(r'^users/(?P<email>.*)$', 'rest_dispatch',
            {'DELETE': 'deactivate_user_backend'}),
    url(r'^bots/(?P<email>.*)/api_key/regenerate$', 'rest_dispatch',
            {'POST': 'regenerate_bot_api_key'}),
    url(r'^bots/(?P<email>.*)$', 'rest_dispatch',
            {'PATCH': 'patch_bot_backend'}),
    url(r'^register$', 'rest_dispatch',
            {'POST': 'api_events_register'}),

) + patterns('zerver.tornadoviews',
    url(r'^events$', 'rest_dispatch',
        {'GET': 'get_events_backend'}),
)
if not settings.LOCAL_SERVER:
    v1_api_and_json_patterns += patterns('',
        # Still scoped to api/v1/, but under a different project
        url(r'^deployments/', include('zilencer.urls.api')),
    )

    urlpatterns += patterns('',
        url(r'^', include('analytics.urls')),
    )

    urlpatterns += patterns('',
        url(r'^', include('corporate.urls')),
    )


urlpatterns += patterns('zerver.tornadoviews',
    # Tornado views
    url(r'^json/get_events$',               'json_get_events'),
    # Used internally for communication between Django and Tornado processes
    url(r'^notify_tornado$',                'notify'),
)

# Include the dual-use patterns twice
urlpatterns += patterns('',
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
)


if not settings.DEPLOYED:
    use_prod_static = getattr(settings, 'PIPELINE', False)
    static_root = os.path.join(settings.DEPLOY_ROOT,
        'prod-static/serve' if use_prod_static else 'static')

    urlpatterns += patterns('',
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': static_root}))

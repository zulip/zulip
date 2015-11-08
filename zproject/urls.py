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
    # We have a desktop-specific landing page in case we change our / to not log in in the future. We don't
    # want to require a new desktop app build for everyone in that case
    url(r'^desktop_home/$', 'zerver.views.desktop_home'),

    url(r'^accounts/login/sso/$', 'zerver.views.remote_user_sso', name='login-sso'),
    url(r'^accounts/login/jwt/$', 'zerver.views.remote_user_jwt', name='login-jwt'),
    url(r'^accounts/login/google/$', 'zerver.views.start_google_oauth2'),
    url(r'^accounts/login/google/done/$', 'zerver.views.finish_google_oauth2'),
    url(r'^accounts/login/local/$', 'zerver.views.dev_direct_login'),
    # We have two entries for accounts/login to allow reverses on the Django
    # view we're wrapping to continue to function.
    url(r'^accounts/login/',  'zerver.views.login_page',         {'template_name': 'zerver/login.html'}),
    url(r'^accounts/login/',  'django.contrib.auth.views.login', {'template_name': 'zerver/login.html'}),
    url(r'^accounts/logout/', 'zerver.views.logout_then_login'),
    url(r'^accounts/webathena_kerberos_login/', 'zerver.views.webathena_kerberos_login'),

    url(r'^accounts/password/reset/$', 'django.contrib.auth.views.password_reset',
        {'post_reset_redirect': '/accounts/password/reset/done/',
            'template_name': 'zerver/reset.html',
            'email_template_name': 'registration/password_reset_email.txt',
            }),
    url(r'^accounts/password/reset/done/$', 'django.contrib.auth.views.password_reset_done',
        {'template_name': 'zerver/reset_emailed.html'}),
    url(r'^accounts/password/reset/(?P<uidb64>[0-9A-Za-z]+)/(?P<token>.+)/$',
        'django.contrib.auth.views.password_reset_confirm',
        {'post_reset_redirect' : '/accounts/password/done/',
         'template_name': 'zerver/reset_confirm.html',
         'set_password_form' : zerver.forms.LoggingSetPasswordForm}),
    url(r'^accounts/password/done/$', 'django.contrib.auth.views.password_reset_complete',
        {'template_name': 'zerver/reset_done.html'}),

    # Avatar
    url(r'^avatar/(?P<email>[\S]+)?', 'zerver.views.avatar'),

    # Registration views, require a confirmation ID.
    url(r'^accounts/home/', 'zerver.views.accounts_home'),
    url(r'^accounts/send_confirm/(?P<email>[\S]+)?',
        TemplateView.as_view(template_name='zerver/accounts_send_confirm.html'), name='send_confirm'),
    url(r'^accounts/register/', 'zerver.views.accounts_register'),
    url(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)', 'confirmation.views.confirm'),
    url(r'^invite/$', 'zerver.views.initial_invite_page', name='initial-invite-users'),

    # Unsubscription endpoint. Used for various types of e-mails (day 1 & 2,
    # missed PMs, etc.)
    url(r'^accounts/unsubscribe/(?P<type>[\w]+)/(?P<token>[\w]+)',
        'zerver.views.email_unsubscribe'),

    # Portico-styled page used to provide email confirmation of terms acceptance.
    url(r'^accounts/accept_terms/$', 'zerver.views.accounts_accept_terms'),

    # Terms of service and privacy policy
    url(r'^terms/$',   TemplateView.as_view(template_name='zerver/terms.html')),
    url(r'^terms-enterprise/$',  TemplateView.as_view(template_name='zerver/terms-enterprise.html')),
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

    # Landing page, features pages, signup form, etc.
    url(r'^hello/$', TemplateView.as_view(template_name='zerver/hello.html'),
                                         name='landing-page'),
    url(r'^new-user/$', RedirectView.as_view(url='/hello')),
    url(r'^features/$', TemplateView.as_view(template_name='zerver/features.html')),
)

# These are used for voyager development. On a real voyager instance,
# these files would be served by nginx.
if settings.DEVELOPMENT and settings.LOCAL_UPLOADS_DIR is not None:
    urlpatterns += patterns('',
        url(r'^user_avatars/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")}),
        url(r'^user_uploads/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "files")}),
    )

urlpatterns += patterns('zerver.views',
    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/update_pointer$',           'json_update_pointer'),
    url(r'^json/get_old_messages$',         'messages.json_get_old_messages'),
    url(r'^json/get_public_streams$',       'json_get_public_streams'),
    url(r'^json/rename_stream$',            'json_rename_stream'),
    url(r'^json/make_stream_public$',       'json_make_stream_public'),
    url(r'^json/make_stream_private$',      'json_make_stream_private'),
    url(r'^json/send_message$',             'messages.json_send_message'),
    url(r'^json/invite_users$',             'json_invite_users'),
    url(r'^json/bulk_invite_users$',        'json_bulk_invite_users'),
    url(r'^json/settings/change$',          'json_change_settings'),
    url(r'^json/notify_settings/change$',   'json_change_notify_settings'),
    url(r'^json/ui_settings/change$',       'json_change_ui_settings'),
    url(r'^json/subscriptions/remove$',     'json_remove_subscriptions'),
    url(r'^json/subscriptions/add$',        'json_add_subscriptions'),
    url(r'^json/subscriptions/exists$',     'json_stream_exists'),
    url(r'^json/subscriptions/property$',   'json_subscription_property'),
    url(r'^json/get_subscribers$',          'json_get_subscribers'),
    url(r'^json/fetch_api_key$',            'json_fetch_api_key'),
    url(r'^json/update_active_status$',     'json_update_active_status'),
    url(r'^json/get_active_statuses$',      'json_get_active_statuses'),
    url(r'^json/tutorial_send_message$',    'json_tutorial_send_message'),
    url(r'^json/tutorial_status$',          'json_tutorial_status'),
    url(r'^json/change_enter_sends$',       'json_change_enter_sends'),
    url(r'^json/get_profile$',              'json_get_profile'),
    url(r'^json/report_error$',             'json_report_error'),
    url(r'^json/report_send_time$',         'json_report_send_time'),
    url(r'^json/report_narrow_time$',       'json_report_narrow_time'),
    url(r'^json/report_unnarrow_time$',     'json_report_unnarrow_time'),
    url(r'^json/update_message_flags$',     'messages.json_update_flags'),
    url(r'^json/register$',                 'json_events_register'),
    url(r'^json/upload_file$',              'json_upload_file'),
    url(r'^json/messages_in_narrow$',       'messages.json_messages_in_narrow'),
    url(r'^json/update_message$',           'messages.json_update_message'),
    url(r'^json/fetch_raw_message$',        'messages.json_fetch_raw_message'),
    url(r'^json/refer_friend$',             'json_refer_friend'),
    url(r'^json/set_alert_words$',          'json_set_alert_words'),
    url(r'^json/set_muted_topics$',         'json_set_muted_topics'),
    url(r'^json/set_avatar$',               'json_set_avatar'),
    url(r'^json/time_setting$',             'json_time_setting'),
    url(r'^json/left_side_userlist$',       'json_left_side_userlist'),

    # This json format view is used by the LEGACY pre-REST API.  It
    # requires an API key.
    url(r'^api/v1/send_message$',           'messages.api_send_message'),

    # This json format view used by the mobile apps accepts a username
    # password/pair and returns an API key.
    url(r'^api/v1/fetch_api_key$',          'api_fetch_api_key'),

    # Used to present the GOOGLE_CLIENT_ID to mobile apps
    url(r'^api/v1/fetch_google_client_id$', 'api_fetch_google_client_id'),

    # These are integration-specific web hook callbacks
    url(r'^api/v1/external/beanstalk$',     'webhooks.api_beanstalk_webhook'),
    url(r'^api/v1/external/github$',        'webhooks.api_github_landing'),
    url(r'^api/v1/external/jira$',          'webhooks.api_jira_webhook'),
    url(r'^api/v1/external/pivotal$',       'webhooks.api_pivotal_webhook'),
    url(r'^api/v1/external/newrelic$',      'webhooks.api_newrelic_webhook'),
    url(r'^api/v1/external/bitbucket$',     'webhooks.api_bitbucket_webhook'),
    url(r'^api/v1/external/desk$',          'webhooks.api_deskdotcom_webhook'),
    url(r'^api/v1/external/stash$',         'webhooks.api_stash_webhook'),
    url(r'^api/v1/external/freshdesk$',     'webhooks.api_freshdesk_webhook'),
    url(r'^api/v1/external/zendesk$',       'webhooks.api_zendesk_webhook'),
    url(r'^api/v1/external/pagerduty$',     'webhooks.api_pagerduty_webhook'),

    url(r'^user_uploads/(?P<realm_id>(\d*|unk))/(?P<filename>.*)', 'get_uploaded_file'),
)

# JSON format views used by the redesigned API, accept basic auth username:password.
v1_api_and_json_patterns = patterns('zerver.views',
    url(r'^export$', 'rest_dispatch',
            {'GET':  'export'}),
    url(r'^streams$', 'rest_dispatch',
            {'GET':  'get_streams_backend'}),
    # GET returns "stream info" (undefined currently?), HEAD returns whether stream exists (200 or 404)
    url(r'^streams/(?P<stream_name>.*)/members$', 'rest_dispatch',
            {'GET': 'get_subscribers_backend'}),
    url(r'^streams/(?P<stream_name>.*)$', 'rest_dispatch',
            {'HEAD': 'stream_exists_backend',
             'GET': 'stream_exists_backend',
             'PATCH': 'update_stream_backend',
             'DELETE': 'deactivate_stream_backend'}),
    url(r'^users$', 'rest_dispatch',
            {'GET': 'get_members_backend',
             'POST': 'create_user_backend'}),
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
    url(r'^default_streams$', 'rest_dispatch',
            {'PATCH': 'add_default_stream',
             'DELETE': 'remove_default_stream'}),
    url(r'^realm$', 'rest_dispatch',
            {'PATCH': 'update_realm'}),
    url(r'^users/me/api_key/regenerate$', 'rest_dispatch',
            {'POST': 'regenerate_api_key'}),
    url(r'^users/me/presence$', 'rest_dispatch',
            {'POST': 'update_active_status_backend'}),
    # Endpoint used by iOS devices to register their
    # unique APNS device token
    url(r'^users/me/apns_device_token$', 'rest_dispatch',
        {'POST'  : 'add_apns_device_token',
         'DELETE': 'remove_apns_device_token'}),
    url(r'^users/me/android_gcm_reg_id$', 'rest_dispatch',
        {'POST': 'add_android_reg_id',
         'DELETE': 'remove_android_reg_id'}),
    url(r'^users/(?P<email>.*)/reactivate$', 'rest_dispatch',
            {'POST': 'reactivate_user_backend'}),
    url(r'^users/(?P<email>.*)$', 'rest_dispatch',
            {'PATCH': 'update_user_backend',
             'DELETE': 'deactivate_user_backend'}),
    url(r'^bots$', 'rest_dispatch',
            {'GET': 'get_bots_backend',
             'POST': 'add_bot_backend'}),
    url(r'^bots/(?P<email>.*)/api_key/regenerate$', 'rest_dispatch',
            {'POST': 'regenerate_bot_api_key'}),
    url(r'^bots/(?P<email>.*)$', 'rest_dispatch',
            {'PATCH': 'patch_bot_backend',
             'DELETE': 'deactivate_bot_backend'}),
    url(r'^register$', 'rest_dispatch',
            {'POST': 'api_events_register'}),

    # Returns a 204, used by desktop app to verify connectivity status
    url(r'generate_204$', 'generate_204'),

) + patterns('zerver.views.messages',
    # GET returns messages, possibly filtered, POST sends a message
    url(r'^messages$', 'rest_dispatch',
            {'GET':  'get_old_messages_backend',
             'PATCH': 'update_message_backend',
             'POST': 'send_message_backend'}),
    url(r'^messages/render$', 'rest_dispatch',
            {'GET':  'render_message_backend'}),
    url(r'^messages/flags$', 'rest_dispatch',
            {'POST':  'update_message_flags'}),

) + patterns('zerver.tornadoviews',
    url(r'^events$', 'rest_dispatch',
        {'GET': 'get_events_backend',
         'DELETE': 'cleanup_event_queue'}),
)
if not settings.VOYAGER:
    v1_api_and_json_patterns += patterns('',
        # Still scoped to api/v1/, but under a different project
        url(r'^deployments/', include('zilencer.urls.api')),
    )

    urlpatterns += patterns('',
        url(r'^', include('zilencer.urls.pages')),
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


if settings.DEVELOPMENT:
    use_prod_static = getattr(settings, 'PIPELINE', False)
    static_root = os.path.join(settings.DEPLOY_ROOT,
        'prod-static/serve' if use_prod_static else 'static')

    urlpatterns += patterns('',
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': static_root}))

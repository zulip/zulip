from django.conf import settings
from django.conf.urls import patterns, url, include
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import TemplateView, RedirectView
from django.utils.module_loading import import_string
import os.path
import zerver.forms
from zproject import dev_urls
from zproject.legacy_urls import legacy_urls

# NB: There are several other pieces of code which route requests by URL:
#
#   - legacy_urls.py contains API endpoint written before the redesign
#     and should not be added to.
#
#   - runtornado.py has its own URL list for Tornado views.  See the
#     invocation of web.Application in that file.
#
#   - The Nginx config knows which URLs to route to Django or Tornado.
#
#   - Likewise for the local dev server in tools/run-dev.py.

# These views serve pages (HTML). As such, their internationalization
# must depend on the url.
#
# If you're adding a new page to the website (as opposed to a new
# endpoint for use by code), you should add it here.
i18n_urls = [
    url(r'^$', 'zerver.views.home'),
    # We have a desktop-specific landing page in case we change our /
    # to not log in in the future. We don't want to require a new
    # desktop app build for everyone in that case
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
         'password_reset_form': zerver.forms.ZulipPasswordResetForm,
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
    url(r'^avatar/(?P<email>[\S]+)?', 'zerver.views.users.avatar'),

    # Registration views, require a confirmation ID.
    url(r'^accounts/home/', 'zerver.views.accounts_home'),
    url(r'^accounts/send_confirm/(?P<email>[\S]+)?',
        TemplateView.as_view(template_name='zerver/accounts_send_confirm.html'), name='send_confirm'),
    url(r'^accounts/register/', 'zerver.views.accounts_register'),
    url(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)', 'confirmation.views.confirm'),
    url(r'^invite/$', 'zerver.views.initial_invite_page', name='initial-invite-users'),

    # Email unsubscription endpoint. Allows for unsubscribing from various types of emails,
    # including the welcome emails (day 1 & 2), missed PMs, etc.
    url(r'^accounts/unsubscribe/(?P<type>[\w]+)/(?P<token>[\w]+)',
        'zerver.views.email_unsubscribe'),

    # Portico-styled page used to provide email confirmation of terms acceptance.
    url(r'^accounts/accept_terms/$', 'zerver.views.accounts_accept_terms'),

    # Realm Creation
    url(r'^create_realm/$', 'zerver.views.create_realm'),
    url(r'^create_realm/(?P<creation_key>[\w]+)$', 'zerver.views.create_realm'),

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
]

# Make a copy of i18n_urls so that they appear without prefix for english
urls = list(i18n_urls)

# These endpoints constitute the redesigned API (V1), which uses:
# * REST verbs
# * Basic auth (username:password is email:apiKey)
# * Take and return json-formatted data
#
# If you're adding a new endpoint to the code that requires authentication,
# please add it here.
# See rest_dispatch in zerver.lib.rest for an explanation of auth methods used
#
# All of these paths are accessed by either a /json or /api prefix
v1_api_and_json_patterns = [
    # realm-level calls
    url(r'^realm$', 'zerver.lib.rest.rest_dispatch',
        {'PATCH': 'zerver.views.update_realm'}),

    # Returns a 204, used by desktop app to verify connectivity status
    url(r'generate_204$', 'zerver.views.generate_204'),

    # realm/emoji -> zerver.views.realm_emoji
    url(r'^realm/emoji$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.realm_emoji.list_emoji',
         'PUT': 'zerver.views.realm_emoji.upload_emoji'}),
    url(r'^realm/emoji/(?P<emoji_name>[0-9a-zA-Z.\-_]+(?<![.\-_]))$', 'zerver.lib.rest.rest_dispatch',
        {'DELETE': 'zerver.views.realm_emoji.delete_emoji'}),

    # users -> zerver.views.users
    url(r'^users$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.users.get_members_backend',
         'POST': 'zerver.views.users.create_user_backend'}),
    url(r'^users/(?P<email>(?!me)[^/]*)/reactivate$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.users.reactivate_user_backend'}),
    url(r'^users/(?P<email>(?!me)[^/]*)$', 'zerver.lib.rest.rest_dispatch',
        {'PATCH': 'zerver.views.users.update_user_backend',
         'DELETE': 'zerver.views.users.deactivate_user_backend'}),
    url(r'^bots$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.users.get_bots_backend',
         'POST': 'zerver.views.users.add_bot_backend'}),
    url(r'^bots/(?P<email>(?!me)[^/]*)/api_key/regenerate$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.users.regenerate_bot_api_key'}),
    url(r'^bots/(?P<email>(?!me)[^/]*)$', 'zerver.lib.rest.rest_dispatch',
        {'PATCH': 'zerver.views.users.patch_bot_backend',
         'DELETE': 'zerver.views.users.deactivate_bot_backend'}),

    # messages -> zerver.views.messages
    # GET returns messages, possibly filtered, POST sends a message
    url(r'^messages$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.messages.get_old_messages_backend',
         'PATCH': 'zerver.views.messages.update_message_backend',
         'POST': 'zerver.views.messages.send_message_backend'}),
    url(r'^messages/render$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.messages.render_message_backend'}),
    url(r'^messages/flags$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.messages.update_message_flags'}),

    # user_uploads -> zerver.views.upload
    url(r'^user_uploads$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.upload.upload_file_backend'}),

    # users/me -> zerver.views
    url(r'^users/me$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.get_profile_backend'}),
    url(r'^users/me/pointer$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.get_pointer_backend',
         'PUT': 'zerver.views.update_pointer_backend'}),
    url(r'^users/me/presence$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.update_active_status_backend'}),
    # Endpoint used by mobile devices to register their push
    # notification credentials
    url(r'^users/me/apns_device_token$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.add_apns_device_token',
         'DELETE': 'zerver.views.remove_apns_device_token'}),
    url(r'^users/me/android_gcm_reg_id$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.add_android_reg_id',
         'DELETE': 'zerver.views.remove_android_reg_id'}),

    # users/me -> zerver.views.user_settings
    url(r'^users/me/api_key/regenerate$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.user_settings.regenerate_api_key'}),
    url(r'^users/me/enter-sends$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.user_settings.change_enter_sends'}),

    # users/me/alert_words -> zerver.views.alert_words
    url(r'^users/me/alert_words$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.alert_words.list_alert_words',
         'POST': 'zerver.views.alert_words.set_alert_words',
         'PUT': 'zerver.views.alert_words.add_alert_words',
         'DELETE': 'zerver.views.alert_words.remove_alert_words'}),

    # streams -> zerver.views.streams
    url(r'^streams$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.streams.get_streams_backend'}),
    # GET returns "stream info" (undefined currently?), HEAD returns whether stream exists (200 or 404)
    url(r'^streams/(?P<stream_name>.*)/members$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.streams.get_subscribers_backend'}),
    url(r'^streams/(?P<stream_name>.*)$', 'zerver.lib.rest.rest_dispatch',
        {'HEAD': 'zerver.views.streams.stream_exists_backend',
         'GET': 'zerver.views.streams.stream_exists_backend',
         'PATCH': 'zerver.views.streams.update_stream_backend',
         'DELETE': 'zerver.views.streams.deactivate_stream_backend'}),
    url(r'^default_streams$', 'zerver.lib.rest.rest_dispatch',
        {'PUT': 'zerver.views.streams.add_default_stream',
         'DELETE': 'zerver.views.streams.remove_default_stream'}),
    # GET lists your streams, POST bulk adds, PATCH bulk modifies/removes
    url(r'^users/me/subscriptions$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.views.streams.list_subscriptions_backend',
         'POST': 'zerver.views.streams.add_subscriptions_backend',
         'PATCH': 'zerver.views.streams.update_subscriptions_backend'}),

    # used to register for an event queue in tornado
    url(r'^register$', 'zerver.lib.rest.rest_dispatch',
        {'POST': 'zerver.views.api_events_register'}),

    # events -> zerver.tornadoviews
    url(r'^events$', 'zerver.lib.rest.rest_dispatch',
        {'GET': 'zerver.tornadoviews.get_events_backend',
         'DELETE': 'zerver.tornadoviews.cleanup_event_queue'}),
]

# Include the dual-use patterns twice
urls += [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
]

# user_uploads -> zerver.views.upload.serve_file_backend
#
# This url is an exception to the url naming schemes for endpoints. It
# supports both API and session cookie authentication, using a single
# URL for both (not 'api/v1/' or 'json/' prefix). This is required to
# easily support the mobile apps fetching uploaded files without
# having to rewrite URLs, and is implemented using the
# 'override_api_url_scheme' flag passed to rest_dispatch
urls += url(r'^user_uploads/(?P<realm_id_str>(\d*|unk))/(?P<filename>.*)',
            'zerver.lib.rest.rest_dispatch',
            {'GET': ('zerver.views.upload.serve_file_backend',
                     {'override_api_url_scheme'})}),

# Incoming webhook URLs
urls += [
    # Sorted integration-specific webhook callbacks.
    url(r'^api/v1/external/airbrake$',      'zerver.views.webhooks.airbrake.api_airbrake_webhook'),
    url(r'^api/v1/external/beanstalk$',     'zerver.views.webhooks.beanstalk.api_beanstalk_webhook'),
    url(r'^api/v1/external/bitbucket$',     'zerver.views.webhooks.bitbucket.api_bitbucket_webhook'),
    url(r'^api/v1/external/circleci$',      'zerver.views.webhooks.circleci.api_circleci_webhook'),
    url(r'^api/v1/external/codeship$',      'zerver.views.webhooks.codeship.api_codeship_webhook'),
    url(r'^api/v1/external/crashlytics$',   'zerver.views.webhooks.crashlytics.api_crashlytics_webhook'),
    url(r'^api/v1/external/desk$',          'zerver.views.webhooks.deskdotcom.api_deskdotcom_webhook'),
    url(r'^api/v1/external/freshdesk$',     'zerver.views.webhooks.freshdesk.api_freshdesk_webhook'),
    url(r'^api/v1/external/github$',        'zerver.views.webhooks.github.api_github_landing'),
    url(r'^api/v1/external/ifttt$',         'zerver.views.webhooks.ifttt.api_iftt_app_webhook'),
    url(r'^api/v1/external/jira$',          'zerver.views.webhooks.jira.api_jira_webhook'),
    url(r'^api/v1/external/newrelic$',      'zerver.views.webhooks.newrelic.api_newrelic_webhook'),
    url(r'^api/v1/external/pagerduty$',     'zerver.views.webhooks.pagerduty.api_pagerduty_webhook'),
    url(r'^api/v1/external/pingdom$',       'zerver.views.webhooks.pingdom.api_pingdom_webhook'),
    url(r'^api/v1/external/pivotal$',       'zerver.views.webhooks.pivotal.api_pivotal_webhook'),
    url(r'^api/v1/external/semaphore$',     'zerver.views.webhooks.semaphore.api_semaphore_webhook'),
    url(r'^api/v1/external/stash$',         'zerver.views.webhooks.stash.api_stash_webhook'),
    url(r'^api/v1/external/taiga$',         'zerver.views.webhooks.taiga.api_taiga_webhook'),
    url(r'^api/v1/external/teamcity$',      'zerver.views.webhooks.teamcity.api_teamcity_webhook'),
    url(r'^api/v1/external/transifex$',     'zerver.views.webhooks.transifex.api_transifex_webhook'),
    url(r'^api/v1/external/travis$',        'zerver.views.webhooks.travis.api_travis_webhook'),
    url(r'^api/v1/external/updown$',        'zerver.views.webhooks.updown.api_updown_webhook'),
    url(r'^api/v1/external/yo$',            'zerver.views.webhooks.yo.api_yo_app_webhook'),
    url(r'^api/v1/external/zendesk$',       'zerver.views.webhooks.zendesk.api_zendesk_webhook'),
]

# Mobile-specific authentication URLs
urls += [
    # This json format view used by the mobile apps lists which authentication
    # backends the server allows, to display the proper UI and check for server existence
    url(r'^api/v1/get_auth_backends',       'zerver.views.api_get_auth_backends'),

    # This json format view used by the mobile apps accepts a username
    # password/pair and returns an API key.
    url(r'^api/v1/fetch_api_key$',          'zerver.views.api_fetch_api_key'),

    # This is for the signing in through the devAuthBackEnd on mobile apps.
    url(r'^api/v1/dev_fetch_api_key$',      'zerver.views.api_dev_fetch_api_key'),
    # This is for fetching the emails of the admins and the users.
    url(r'^api/v1/dev_get_emails$',         'zerver.views.api_dev_get_emails'),

    # Used to present the GOOGLE_CLIENT_ID to mobile apps
    url(r'^api/v1/fetch_google_client_id$', 'zerver.views.api_fetch_google_client_id'),
]

# Include URL configuration files for site-specified extra installed
# Django apps
for app_name in settings.EXTRA_INSTALLED_APPS:
    app_dir = os.path.join(settings.DEPLOY_ROOT, app_name)
    if os.path.exists(os.path.join(app_dir, 'urls.py')):
        urls += [url(r'^', include('%s.urls' % (app_name,)))]
        i18n_urls += import_string("{}.urls.i18n_urlpatterns".format(app_name))

# Tornado views
urls += [
    url(r'^json/get_events$',               'zerver.tornadoviews.json_get_events'),
    # Used internally for communication between Django and Tornado processes
    url(r'^notify_tornado$',                'zerver.tornadoviews.notify'),
]

if settings.DEVELOPMENT:
    urls += dev_urls.urls
    i18n_urls += dev_urls.i18n_urls

# The sequence is important; if i18n urls don't come first then
# reverse url mapping points to i18n urls which causes the frontend
# tests to fail
urlpatterns = i18n_patterns(*i18n_urls) + urls + legacy_urls

import os

from django.conf import settings
from django.conf.urls import include
from django.conf.urls.i18n import i18n_patterns
from django.contrib.auth.views import (
    LoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
)
from django.urls import path, re_path
from django.utils.module_loading import import_string
from django.views.generic import RedirectView, TemplateView

import zerver.forms
import zerver.tornado.views
import zerver.views
import zerver.views.archive
import zerver.views.auth
import zerver.views.camo
import zerver.views.compatibility
import zerver.views.digest
import zerver.views.documentation
import zerver.views.email_mirror
import zerver.views.home
import zerver.views.message_edit
import zerver.views.message_fetch
import zerver.views.message_flags
import zerver.views.message_send
import zerver.views.muting
import zerver.views.portico
import zerver.views.realm
import zerver.views.realm_export
import zerver.views.registration
import zerver.views.streams
import zerver.views.unsubscribe
import zerver.views.upload
import zerver.views.user_groups
import zerver.views.user_settings
import zerver.views.users
import zerver.views.video_calls
import zerver.views.zephyr
from zerver.lib.integrations import WEBHOOK_INTEGRATIONS
from zerver.lib.rest import rest_dispatch
from zerver.views.documentation import IntegrationView, MarkdownDirectoryView
from zproject import dev_urls
from zproject.legacy_urls import legacy_urls

if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
    from two_factor.gateways.twilio.urls import urlpatterns as tf_twilio_urls
    from two_factor.urls import urlpatterns as tf_urls

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

# These endpoints constitute the currently designed API (V1), which uses:
# * REST verbs
# * Basic auth (username:password is email:apiKey)
# * Take and return json-formatted data
#
# If you're adding a new endpoint to the code that requires authentication,
# please add it here.
# See rest_dispatch in zerver.lib.rest for an explanation of auth methods used
#
# All of these paths are accessed by either a /json or /api/v1 prefix;
# e.g. `PATCH /json/realm` or `PATCH /api/v1/realm`.
v1_api_and_json_patterns = [
    # realm-level calls
    path('realm', rest_dispatch,
         {'PATCH': 'zerver.views.realm.update_realm'}),

    # Returns a 204, used by desktop app to verify connectivity status
    path('generate_204', zerver.views.registration.generate_204,
         name='zerver.views.registration.generate_204'),

    re_path(r'^realm/subdomain/(?P<subdomain>\S+)$', zerver.views.realm.check_subdomain_available,
            name='zerver.views.realm.check_subdomain_available'),

    # realm/domains -> zerver.views.realm_domains
    path('realm/domains', rest_dispatch,
         {'GET': 'zerver.views.realm_domains.list_realm_domains',
          'POST': 'zerver.views.realm_domains.create_realm_domain'}),
    re_path(r'^realm/domains/(?P<domain>\S+)$', rest_dispatch,
            {'PATCH': 'zerver.views.realm_domains.patch_realm_domain',
             'DELETE': 'zerver.views.realm_domains.delete_realm_domain'}),

    # realm/emoji -> zerver.views.realm_emoji
    path('realm/emoji', rest_dispatch,
         {'GET': 'zerver.views.realm_emoji.list_emoji'}),
    re_path(r'^realm/emoji/(?P<emoji_name>.*)$', rest_dispatch,
            {'POST': 'zerver.views.realm_emoji.upload_emoji',
             'DELETE': ('zerver.views.realm_emoji.delete_emoji', {"intentionally_undocumented"})}),
    # this endpoint throws a status code 400 JsonableError when it should be a 404.

    # realm/icon -> zerver.views.realm_icon
    path('realm/icon', rest_dispatch,
         {'POST': 'zerver.views.realm_icon.upload_icon',
          'DELETE': 'zerver.views.realm_icon.delete_icon_backend',
          'GET': 'zerver.views.realm_icon.get_icon_backend'}),

    # realm/logo -> zerver.views.realm_logo
    path('realm/logo', rest_dispatch,
         {'POST': 'zerver.views.realm_logo.upload_logo',
          'DELETE': 'zerver.views.realm_logo.delete_logo_backend',
          'GET': 'zerver.views.realm_logo.get_logo_backend'}),

    # realm/filters -> zerver.views.realm_filters
    path('realm/filters', rest_dispatch,
         {'GET': 'zerver.views.realm_filters.list_filters',
          'POST': 'zerver.views.realm_filters.create_filter'}),
    path('realm/filters/<int:filter_id>', rest_dispatch,
         {'DELETE': 'zerver.views.realm_filters.delete_filter'}),

    # realm/profile_fields -> zerver.views.custom_profile_fields
    path('realm/profile_fields', rest_dispatch,
         {'GET': 'zerver.views.custom_profile_fields.list_realm_custom_profile_fields',
          'PATCH': 'zerver.views.custom_profile_fields.reorder_realm_custom_profile_fields',
          'POST': 'zerver.views.custom_profile_fields.create_realm_custom_profile_field'}),
    path('realm/profile_fields/<int:field_id>', rest_dispatch,
         {'PATCH': 'zerver.views.custom_profile_fields.update_realm_custom_profile_field',
          'DELETE': 'zerver.views.custom_profile_fields.delete_realm_custom_profile_field'}),

    # realm/deactivate -> zerver.views.deactivate_realm
    path('realm/deactivate', rest_dispatch,
         {'POST': 'zerver.views.realm.deactivate_realm'}),

    # users -> zerver.views.users
    path('users', rest_dispatch,
         {'GET': 'zerver.views.users.get_members_backend',
          'POST': 'zerver.views.users.create_user_backend'}),
    path('users/me', rest_dispatch,
         {'GET': 'zerver.views.users.get_profile_backend',
          'DELETE': 'zerver.views.users.deactivate_user_own_backend'}),
    path('users/<int:user_id>/reactivate', rest_dispatch,
         {'POST': 'zerver.views.users.reactivate_user_backend'}),
    path('users/<int:user_id>', rest_dispatch,
         {'GET': 'zerver.views.users.get_members_backend',
          'PATCH': 'zerver.views.users.update_user_backend',
          'DELETE': 'zerver.views.users.deactivate_user_backend'}),
    path('users/<int:user_id>/subscriptions/<int:stream_id>', rest_dispatch,
         {'GET': 'zerver.views.users.get_subscription_backend'}),
    path('bots', rest_dispatch,
         {'GET': 'zerver.views.users.get_bots_backend',
          'POST': 'zerver.views.users.add_bot_backend'}),
    path('bots/<int:bot_id>/api_key/regenerate', rest_dispatch,
         {'POST': 'zerver.views.users.regenerate_bot_api_key'}),
    path('bots/<int:bot_id>', rest_dispatch,
         {'PATCH': 'zerver.views.users.patch_bot_backend',
          'DELETE': 'zerver.views.users.deactivate_bot_backend'}),

    # invites -> zerver.views.invite
    path('invites', rest_dispatch,
         {'GET': 'zerver.views.invite.get_user_invites',
          'POST': 'zerver.views.invite.invite_users_backend'}),
    path('invites/<int:prereg_id>', rest_dispatch,
         {'DELETE': 'zerver.views.invite.revoke_user_invite'}),
    path('invites/<int:prereg_id>/resend', rest_dispatch,
         {'POST': 'zerver.views.invite.resend_user_invite_email'}),

    # invites/multiuse -> zerver.views.invite
    path('invites/multiuse', rest_dispatch,
         {'POST': 'zerver.views.invite.generate_multiuse_invite_backend'}),
    # invites/multiuse -> zerver.views.invite
    path('invites/multiuse/<int:invite_id>', rest_dispatch,
         {'DELETE': 'zerver.views.invite.revoke_multiuse_invite'}),

    # mark messages as read (in bulk)
    path('mark_all_as_read', rest_dispatch,
         {'POST': 'zerver.views.message_flags.mark_all_as_read'}),
    path('mark_stream_as_read', rest_dispatch,
         {'POST': 'zerver.views.message_flags.mark_stream_as_read'}),
    path('mark_topic_as_read', rest_dispatch,
         {'POST': 'zerver.views.message_flags.mark_topic_as_read'}),

    path('zcommand', rest_dispatch,
         {'POST': 'zerver.views.message_send.zcommand_backend'}),

    # Endpoints for syncing drafts.
    path('drafts', rest_dispatch,
         {'GET': ('zerver.views.drafts.fetch_drafts',
                  {'intentionally_undocumented'}),
          'POST': ('zerver.views.drafts.create_drafts',
                   {'intentionally_undocumented'})}),
    path('drafts/<int:draft_id>', rest_dispatch,
         {'PATCH': ('zerver.views.drafts.edit_draft',
                    {'intentionally_undocumented'}),
          'DELETE': ('zerver.views.drafts.delete_draft',
                     {'intentionally_undocumented'})}),

    # messages -> zerver.views.message*
    # GET returns messages, possibly filtered, POST sends a message
    path('messages', rest_dispatch,
         {'GET': ('zerver.views.message_fetch.get_messages_backend',
                  {'allow_anonymous_user_web'}),
          'POST': ('zerver.views.message_send.send_message_backend',
                   {'allow_incoming_webhooks'})}),
    path('messages/<int:message_id>', rest_dispatch,
         {'GET': 'zerver.views.message_edit.json_fetch_raw_message',
          'PATCH': 'zerver.views.message_edit.update_message_backend',
          'DELETE': 'zerver.views.message_edit.delete_message_backend'}),
    path('messages/render', rest_dispatch,
         {'POST': 'zerver.views.message_send.render_message_backend'}),
    path('messages/flags', rest_dispatch,
         {'POST': 'zerver.views.message_flags.update_message_flags'}),
    path('messages/<int:message_id>/history', rest_dispatch,
         {'GET': 'zerver.views.message_edit.get_message_edit_history'}),
    path('messages/matches_narrow', rest_dispatch,
         {'GET': 'zerver.views.message_fetch.messages_in_narrow_backend'}),

    path('users/me/subscriptions/properties', rest_dispatch,
         {'POST': 'zerver.views.streams.update_subscription_properties_backend'}),

    path('users/me/subscriptions/<int:stream_id>', rest_dispatch,
         {'PATCH': 'zerver.views.streams.update_subscriptions_property'}),

    path('submessage',
         rest_dispatch,
         {'POST': 'zerver.views.submessage.process_submessage'}),

    # New endpoint for handling reactions.
    # reactions -> zerver.view.reactions
    # POST adds a reaction to a message
    # DELETE removes a reaction from a message
    path('messages/<int:message_id>/reactions',
         rest_dispatch,
         {'POST': 'zerver.views.reactions.add_reaction',
          'DELETE': 'zerver.views.reactions.remove_reaction'}),

    # attachments -> zerver.views.attachments
    path('attachments', rest_dispatch,
         {'GET': 'zerver.views.attachments.list_by_user'}),
    path('attachments/<int:attachment_id>', rest_dispatch,
         {'DELETE': 'zerver.views.attachments.remove'}),

    # typing -> zerver.views.typing
    # POST sends a typing notification event to recipients
    path('typing', rest_dispatch,
         {'POST': 'zerver.views.typing.send_notification_backend'}),

    # user_uploads -> zerver.views.upload
    path('user_uploads', rest_dispatch,
         {'POST': 'zerver.views.upload.upload_file_backend'}),
    re_path(r'^user_uploads/(?P<realm_id_str>(\d*|unk))/(?P<filename>.*)$',
            rest_dispatch,
            {'GET': ('zerver.views.upload.serve_file_url_backend',
                     {'override_api_url_scheme'})}),

    # bot_storage -> zerver.views.storage
    path('bot_storage', rest_dispatch,
         {'PUT': 'zerver.views.storage.update_storage',
          'GET': 'zerver.views.storage.get_storage',
          'DELETE': 'zerver.views.storage.remove_storage'}),

    # Endpoint used by mobile devices to register their push
    # notification credentials
    path('users/me/apns_device_token', rest_dispatch,
         {'POST': 'zerver.views.push_notifications.add_apns_device_token',
          'DELETE': 'zerver.views.push_notifications.remove_apns_device_token'}),
    path('users/me/android_gcm_reg_id', rest_dispatch,
         {'POST': 'zerver.views.push_notifications.add_android_reg_id',
          'DELETE': 'zerver.views.push_notifications.remove_android_reg_id'}),

    # users/*/presnece => zerver.views.presence.
    path('users/me/presence', rest_dispatch,
         {'POST': 'zerver.views.presence.update_active_status_backend'}),
    # It's important that this sit after users/me/presence so that
    # Django's URL resolution order doesn't break the
    # /users/me/presence endpoint.
    path(r'users/<str:email>/presence', rest_dispatch,
         {'GET': 'zerver.views.presence.get_presence_backend'}),
    path('realm/presence', rest_dispatch,
         {'GET': 'zerver.views.presence.get_statuses_for_realm'}),
    path('users/me/status', rest_dispatch,
         {'POST': 'zerver.views.presence.update_user_status_backend'}),

    # user_groups -> zerver.views.user_groups
    path('user_groups', rest_dispatch,
         {'GET': 'zerver.views.user_groups.get_user_group'}),
    path('user_groups/create', rest_dispatch,
         {'POST': 'zerver.views.user_groups.add_user_group'}),
    path('user_groups/<int:user_group_id>', rest_dispatch,
         {'PATCH': 'zerver.views.user_groups.edit_user_group',
          'DELETE': 'zerver.views.user_groups.delete_user_group'}),
    path('user_groups/<int:user_group_id>/members', rest_dispatch,
         {'POST': 'zerver.views.user_groups.update_user_group_backend'}),

    # users/me -> zerver.views.user_settings
    path('users/me/api_key/regenerate', rest_dispatch,
         {'POST': 'zerver.views.user_settings.regenerate_api_key'}),
    path('users/me/enter-sends', rest_dispatch,
         {'POST': ('zerver.views.user_settings.change_enter_sends',
                   # This endpoint should be folded into user settings
                   {'intentionally_undocumented'})}),
    path('users/me/avatar', rest_dispatch,
         {'POST': 'zerver.views.user_settings.set_avatar_backend',
          'DELETE': 'zerver.views.user_settings.delete_avatar_backend'}),

    # users/me/hotspots -> zerver.views.hotspots
    path('users/me/hotspots', rest_dispatch,
         {'POST': ('zerver.views.hotspots.mark_hotspot_as_read',
                   # This endpoint is low priority for documentation as
                   # it is part of the webapp-specific tutorial.
                   {'intentionally_undocumented'})}),

    # users/me/tutorial_status -> zerver.views.tutorial
    path('users/me/tutorial_status', rest_dispatch,
         {'POST': ('zerver.views.tutorial.set_tutorial_status',
                   # This is a relic of an old Zulip tutorial model and
                   # should be deleted.
                   {'intentionally_undocumented'})}),

    # settings -> zerver.views.user_settings
    path('settings', rest_dispatch,
         {'PATCH': 'zerver.views.user_settings.json_change_settings'}),
    path('settings/display', rest_dispatch,
         {'PATCH': 'zerver.views.user_settings.update_display_settings_backend'}),
    path('settings/notifications', rest_dispatch,
         {'PATCH': 'zerver.views.user_settings.json_change_notify_settings'}),

    # users/me/alert_words -> zerver.views.alert_words
    path('users/me/alert_words', rest_dispatch,
         {'GET': 'zerver.views.alert_words.list_alert_words',
          'POST': 'zerver.views.alert_words.add_alert_words',
          'DELETE': 'zerver.views.alert_words.remove_alert_words'}),

    # users/me/custom_profile_data -> zerver.views.custom_profile_data
    path('users/me/profile_data', rest_dispatch,
         {'PATCH': 'zerver.views.custom_profile_fields.update_user_custom_profile_data',
          'DELETE': 'zerver.views.custom_profile_fields.remove_user_custom_profile_data'}),

    path('users/me/<int:stream_id>/topics', rest_dispatch,
         {'GET': ('zerver.views.streams.get_topics_backend',
                  {'allow_anonymous_user_web'})}),


    # streams -> zerver.views.streams
    # (this API is only used externally)
    path('streams', rest_dispatch,
         {'GET': 'zerver.views.streams.get_streams_backend'}),

    # GET returns `stream_id`, stream name should be encoded in the url query (in `stream` param)
    path('get_stream_id', rest_dispatch,
         {'GET': 'zerver.views.streams.json_get_stream_id'}),

    # GET returns "stream info" (undefined currently?), HEAD returns whether stream exists (200 or 404)
    path('streams/<int:stream_id>/members', rest_dispatch,
         {'GET': 'zerver.views.streams.get_subscribers_backend'}),
    path('streams/<int:stream_id>', rest_dispatch,
         {'PATCH': 'zerver.views.streams.update_stream_backend',
          'DELETE': 'zerver.views.streams.deactivate_stream_backend'}),

    # Delete topic in stream
    path('streams/<int:stream_id>/delete_topic', rest_dispatch,
         {'POST': 'zerver.views.streams.delete_in_topic'}),

    path('default_streams', rest_dispatch,
         {'POST': 'zerver.views.streams.add_default_stream',
          'DELETE': 'zerver.views.streams.remove_default_stream'}),
    path('default_stream_groups/create', rest_dispatch,
         {'POST': 'zerver.views.streams.create_default_stream_group'}),
    path('default_stream_groups/<int:group_id>', rest_dispatch,
         {'PATCH': 'zerver.views.streams.update_default_stream_group_info',
          'DELETE': 'zerver.views.streams.remove_default_stream_group'}),
    path('default_stream_groups/<int:group_id>/streams', rest_dispatch,
         {'PATCH': 'zerver.views.streams.update_default_stream_group_streams'}),
    # GET lists your streams, POST bulk adds, PATCH bulk modifies/removes
    path('users/me/subscriptions', rest_dispatch,
         {'GET': 'zerver.views.streams.list_subscriptions_backend',
          'POST': 'zerver.views.streams.add_subscriptions_backend',
          'PATCH': 'zerver.views.streams.update_subscriptions_backend',
          'DELETE': 'zerver.views.streams.remove_subscriptions_backend'}),
    # muting -> zerver.views.muting
    path('users/me/subscriptions/muted_topics', rest_dispatch,
         {'PATCH': 'zerver.views.muting.update_muted_topic'}),

    # used to register for an event queue in tornado
    path('register', rest_dispatch,
         {'POST': 'zerver.views.events_register.events_register_backend'}),

    # events -> zerver.tornado.views
    path('events', rest_dispatch,
         {'GET': 'zerver.tornado.views.get_events',
          'DELETE': 'zerver.tornado.views.cleanup_event_queue'}),

    # report -> zerver.views.report
    #
    # These endpoints are for internal error/performance reporting
    # from the browser to the webapp, and we don't expect to ever
    # include in our API documentation.
    path('report/error', rest_dispatch,
         # Logged-out browsers can hit this endpoint, for portico page JS exceptions.
         {'POST': ('zerver.views.report.report_error', {'allow_anonymous_user_web',
                                                        'intentionally_undocumented'})}),
    path('report/send_times', rest_dispatch,
         {'POST': ('zerver.views.report.report_send_times', {'intentionally_undocumented'})}),
    path('report/narrow_times', rest_dispatch,
         {'POST': ('zerver.views.report.report_narrow_times', {'intentionally_undocumented'})}),
    path('report/unnarrow_times', rest_dispatch,
         {'POST': ('zerver.views.report.report_unnarrow_times', {'intentionally_undocumented'})}),

    # Used to generate a Zoom video call URL
    path('calls/zoom/create', rest_dispatch,
         {'POST': 'zerver.views.video_calls.make_zoom_video_call'}),
    # Used to generate a Big Blue Button video call URL
    path('calls/bigbluebutton/create', rest_dispatch,
         {'GET': 'zerver.views.video_calls.get_bigbluebutton_url'}),

    # export/realm -> zerver.views.realm_export
    path('export/realm', rest_dispatch,
         {'POST': 'zerver.views.realm_export.export_realm',
          'GET': 'zerver.views.realm_export.get_realm_exports'}),
    re_path(r'^export/realm/(?P<export_id>.*)$', rest_dispatch,
            {'DELETE': 'zerver.views.realm_export.delete_realm_export'}),
]

# These views serve pages (HTML). As such, their internationalization
# must depend on the url.
#
# If you're adding a new page to the website (as opposed to a new
# endpoint for use by code), you should add it here.
i18n_urls = [
    path('', zerver.views.home.home, name='zerver.views.home.home'),
    # We have a desktop-specific landing page in case we change our /
    # to not log in in the future. We don't want to require a new
    # desktop app build for everyone in that case
    path('desktop_home/', zerver.views.home.desktop_home,
         name='zerver.views.home.desktop_home'),

    # Backwards-compatibility (legacy) Google auth URL for the mobile
    # apps; see https://github.com/zulip/zulip/issues/13081 for
    # background.  We can remove this once older versions of the
    # mobile app are no longer present in the wild.
    re_path(r'accounts/login/(google)/$', zerver.views.auth.start_social_login,
            name='login-social'),

    path('accounts/login/start/sso/', zerver.views.auth.start_remote_user_sso, name='start-login-sso'),
    path('accounts/login/sso/', zerver.views.auth.remote_user_sso, name='login-sso'),
    path('accounts/login/jwt/', zerver.views.auth.remote_user_jwt, name='login-jwt'),
    re_path(r'^accounts/login/social/([\w,-]+)$', zerver.views.auth.start_social_login,
            name='login-social'),
    re_path(r'^accounts/login/social/([\w,-]+)/([\w,-]+)$', zerver.views.auth.start_social_login,
            name='login-social-extra-arg'),
    re_path(r'^accounts/register/social/([\w,-]+)$',
            zerver.views.auth.start_social_signup,
            name='signup-social'),
    re_path(r'^accounts/register/social/([\w,-]+)/([\w,-]+)$',
            zerver.views.auth.start_social_signup,
            name='signup-social-extra-arg'),
    re_path(r'^accounts/login/subdomain/([^/]+)$', zerver.views.auth.log_into_subdomain,
            name='zerver.views.auth.log_into_subdomain'),
    path('accounts/login/local/', zerver.views.auth.dev_direct_login,
         name='zerver.views.auth.dev_direct_login'),
    # We have two entries for accounts/login; only the first one is
    # used for URL resolution.  The second here is to allow
    # reverse("django.contrib.auth.views.login") in templates to
    # return `/accounts/login/`.
    path('accounts/login/', zerver.views.auth.login_page,
         {'template_name': 'zerver/login.html'}, name='zerver.views.auth.login_page'),
    path('accounts/login/', LoginView.as_view(template_name='zerver/login.html'),
         name='django.contrib.auth.views.login'),
    path('accounts/logout/', zerver.views.auth.logout_then_login,
         name='zerver.views.auth.logout_then_login'),

    path('accounts/webathena_kerberos_login/',
         zerver.views.zephyr.webathena_kerberos_login,
         name='zerver.views.zephyr.webathena_kerberos_login'),

    path('accounts/password/reset/', zerver.views.auth.password_reset,
         name='zerver.views.auth.password_reset'),
    path('accounts/password/reset/done/',
         PasswordResetDoneView.as_view(template_name='zerver/reset_emailed.html')),
    re_path(r'^accounts/password/reset/(?P<uidb64>[0-9A-Za-z]+)/(?P<token>.+)/$',
            PasswordResetConfirmView.as_view(success_url='/accounts/password/done/',
                                             template_name='zerver/reset_confirm.html',
                                             form_class=zerver.forms.LoggingSetPasswordForm),
            name='django.contrib.auth.views.password_reset_confirm'),
    path('accounts/password/done/',
         PasswordResetCompleteView.as_view(template_name='zerver/reset_done.html')),
    path('accounts/deactivated/',
         zerver.views.auth.show_deactivation_notice,
         name='zerver.views.auth.show_deactivation_notice'),

    # Displays digest email content in browser.
    path('digest/', zerver.views.digest.digest_page),

    # Registration views, require a confirmation ID.
    path('accounts/home/', zerver.views.registration.accounts_home,
         name='zerver.views.registration.accounts_home'),
    re_path(r'^accounts/send_confirm/(?P<email>[\S]+)?$',
            TemplateView.as_view(
                template_name='zerver/accounts_send_confirm.html'),
            name='signup_send_confirm'),
    re_path(r'^accounts/new/send_confirm/(?P<email>[\S]+)?$',
            TemplateView.as_view(
                template_name='zerver/accounts_send_confirm.html'),
            {'realm_creation': True}, name='new_realm_send_confirm'),
    path('accounts/register/', zerver.views.registration.accounts_register,
         name='zerver.views.registration.accounts_register'),
    re_path(r'^accounts/do_confirm/(?P<confirmation_key>[\w]+)$',
            zerver.views.registration.check_prereg_key_and_redirect,
            name='check_prereg_key_and_redirect'),

    re_path(r'^accounts/confirm_new_email/(?P<confirmation_key>[\w]+)$',
            zerver.views.user_settings.confirm_email_change,
            name='zerver.views.user_settings.confirm_email_change'),

    # Email unsubscription endpoint. Allows for unsubscribing from various types of emails,
    # including the welcome emails (day 1 & 2), missed PMs, etc.
    re_path(r'^accounts/unsubscribe/(?P<email_type>[\w]+)/(?P<confirmation_key>[\w]+)$',
            zerver.views.unsubscribe.email_unsubscribe,
            name='zerver.views.unsubscribe.email_unsubscribe'),

    # Portico-styled page used to provide email confirmation of terms acceptance.
    path('accounts/accept_terms/', zerver.views.home.accounts_accept_terms,
         name='zerver.views.home.accounts_accept_terms'),

    # Find your account
    path('accounts/find/', zerver.views.registration.find_account,
         name='zerver.views.registration.find_account'),

    # Go to organization subdomain
    path('accounts/go/', zerver.views.registration.realm_redirect,
         name='zerver.views.registration.realm_redirect'),

    # Realm Creation
    path('new/', zerver.views.registration.create_realm,
         name='zerver.views.create_realm'),
    re_path(r'^new/(?P<creation_key>[\w]+)$',
            zerver.views.registration.create_realm, name='zerver.views.create_realm'),

    # Realm Reactivation
    re_path(r'^reactivate/(?P<confirmation_key>[\w]+)$', zerver.views.realm.realm_reactivation,
            name='zerver.views.realm.realm_reactivation'),

    # Global public streams (Zulip's way of doing archives)
    path('archive/streams/<int:stream_id>/topics/<str:topic_name>',
         zerver.views.archive.archive,
         name='zerver.views.archive.archive'),
    path('archive/streams/<int:stream_id>/topics',
         zerver.views.archive.get_web_public_topics_backend,
         name='zerver.views.archive.get_web_public_topics_backend'),

    # Login/registration
    path('register/', zerver.views.registration.accounts_home, name='register'),
    path('login/', zerver.views.auth.login_page, {'template_name': 'zerver/login.html'},
         name='zerver.views.auth.login_page'),

    re_path(r'^join/(?P<confirmation_key>\S+)/$',
            zerver.views.registration.accounts_home_from_multiuse_invite,
            name='zerver.views.registration.accounts_home_from_multiuse_invite'),

    # Used to generate a Zoom video call URL
    path('calls/zoom/register', zerver.views.video_calls.register_zoom_user),
    path('calls/zoom/complete', zerver.views.video_calls.complete_zoom_user),
    path('calls/zoom/deauthorize', zerver.views.video_calls.deauthorize_zoom_user),

    # Used to join a Big Blue Button video call
    path('calls/bigbluebutton/join', zerver.views.video_calls.join_bigbluebutton),

    # API and integrations documentation
    path('integrations/doc-html/<str:integration_name>',
         zerver.views.documentation.integration_doc,
         name="zerver.views.documentation.integration_doc"),
    re_path(r'^integrations/(.*)$', IntegrationView.as_view()),

    # Landing page, features pages, signup form, etc.
    path('hello/', zerver.views.portico.hello_view, name='landing-page'),
    path('new-user/', RedirectView.as_view(url='/hello', permanent=True)),
    path('features/', zerver.views.portico.landing_view, {'template_name': 'zerver/features.html'}),
    path('plans/', zerver.views.portico.plans_view, name='plans'),
    re_path(r'apps/(.*)$', zerver.views.portico.apps_view, name='zerver.views.home.apps_view'),
    path('team/', zerver.views.portico.team_view),
    path('history/', zerver.views.portico.landing_view, {'template_name': 'zerver/history.html'}),
    path('why-zulip/', zerver.views.portico.landing_view, {'template_name': 'zerver/why-zulip.html'}),
    path('for/open-source/', zerver.views.portico.landing_view,
         {'template_name': 'zerver/for-open-source.html'}),
    path('for/research/', zerver.views.portico.landing_view,
         {'template_name': 'zerver/for-research.html'}),
    path('for/companies/', zerver.views.portico.landing_view,
         {'template_name': 'zerver/for-companies.html'}),
    path('for/working-groups-and-communities/', zerver.views.portico.landing_view,
         {'template_name': 'zerver/for-working-groups-and-communities.html'}),
    path('security/', zerver.views.portico.landing_view, {'template_name': 'zerver/security.html'}),
    path('atlassian/', zerver.views.portico.landing_view, {'template_name': 'zerver/atlassian.html'}),

    # Terms of Service and privacy pages.
    path('terms/', zerver.views.portico.terms_view, name='terms'),
    path('privacy/', zerver.views.portico.privacy_view, name='privacy'),
    re_path(r'^config-error/(?P<error_category_name>[\w,-]+)$', zerver.views.auth.config_error_view,
            name='config_error'),
    re_path(r'^config-error/remoteuser/(?P<error_category_name>[\w,-]+)$',
            zerver.views.auth.config_error_view),
]

# Make a copy of i18n_urls so that they appear without prefix for english
urls = list(i18n_urls)

# Include the dual-use patterns twice
urls += [
    path('api/v1/', include(v1_api_and_json_patterns)),
    path('json/', include(v1_api_and_json_patterns)),
]

# user_uploads -> zerver.views.upload.serve_file_backend
#
# This url is an exception to the url naming schemes for endpoints. It
# supports both API and session cookie authentication, using a single
# URL for both (not 'api/v1/' or 'json/' prefix). This is required to
# easily support the mobile apps fetching uploaded files without
# having to rewrite URLs, and is implemented using the
# 'override_api_url_scheme' flag passed to rest_dispatch
urls += [
    re_path(r'^user_uploads/temporary/([0-9A-Za-z]+)/([^/]+)$',
            zerver.views.upload.serve_local_file_unauthed,
            name='zerver.views.upload.serve_local_file_unauthed'),
    re_path(r'^user_uploads/(?P<realm_id_str>(\d*|unk))/(?P<filename>.*)$',
            rest_dispatch,
            {'GET': ('zerver.views.upload.serve_file_backend',
                     {'override_api_url_scheme'})}),
    # This endpoint serves thumbnailed versions of images using thumbor;
    # it requires an exception for the same reason.
    path('thumbnail', rest_dispatch,
         {'GET': ('zerver.views.thumbnail.backend_serve_thumbnail',
                  {'override_api_url_scheme'})}),
    # Avatars have the same constraint because their URLs are included
    # in API data structures used by both the mobile and web clients.
    re_path(r'^avatar/(?P<email_or_id>[\S]+)/(?P<medium>[\S]+)?$',
            rest_dispatch,
            {'GET': ('zerver.views.users.avatar',
                     {'override_api_url_scheme'})}),
    re_path(r'^avatar/(?P<email_or_id>[\S]+)$',
            rest_dispatch,
            {'GET': ('zerver.views.users.avatar',
                     {'override_api_url_scheme'})}),
]

# This url serves as a way to receive CSP violation reports from the users.
# We use this endpoint to just log these reports.
urls += [
    path('report/csp_violations', zerver.views.report.report_csp_violations,
         name='zerver.views.report.report_csp_violations'),
]

# This url serves as a way to provide backward compatibility to messages
# rendered at the time Zulip used camo for doing http -> https conversion for
# such links with images previews. Now thumbor can be used for serving such
# images.
urls += [
    re_path(r'^external_content/(?P<digest>[\S]+)/(?P<received_url>[\S]+)$',
            zerver.views.camo.handle_camo_url,
            name='zerver.views.camo.handle_camo_url'),
]

# Incoming webhook URLs
# We don't create urls for particular git integrations here
# because of generic one below
for incoming_webhook in WEBHOOK_INTEGRATIONS:
    if incoming_webhook.url_object:
        urls.append(incoming_webhook.url_object)

# Desktop-specific authentication URLs
urls += [
    path('json/fetch_api_key', rest_dispatch,
         {'POST': 'zerver.views.auth.json_fetch_api_key'}),
]

# Mobile-specific authentication URLs
urls += [
    # Used as a global check by all mobile clients, which currently send
    # requests to https://zulip.com/compatibility almost immediately after
    # starting up.
    path('compatibility', zerver.views.compatibility.check_global_compatibility),
]

v1_api_mobile_patterns = [
    # This json format view used by the mobile apps lists which
    # authentication backends the server allows as well as details
    # like the requested subdomains'd realm icon (if known) and
    # server-specific compatibility.
    path('server_settings', zerver.views.auth.api_get_server_settings),

    # This json format view used by the mobile apps accepts a username
    # password/pair and returns an API key.
    path('fetch_api_key', zerver.views.auth.api_fetch_api_key,
         name='zerver.views.auth.api_fetch_api_key'),

    # This is for the signing in through the devAuthBackEnd on mobile apps.
    path('dev_fetch_api_key', zerver.views.auth.api_dev_fetch_api_key,
         name='zerver.views.auth.api_dev_fetch_api_key'),
    # This is for fetching the emails of the admins and the users.
    path('dev_list_users', zerver.views.auth.api_dev_list_users,
         name='zerver.views.auth.api_dev_list_users'),

    # Used to present the GOOGLE_CLIENT_ID to mobile apps
    path('fetch_google_client_id',
         zerver.views.auth.api_fetch_google_client_id,
         name='zerver.views.auth.api_fetch_google_client_id'),
]
urls += [
    path('api/v1/', include(v1_api_mobile_patterns)),
]

# View for uploading messages from email mirror
urls += [
    path('email_mirror_message', zerver.views.email_mirror.email_mirror_message,
         name='zerver.views.email_mirror.email_mirror_message'),
]

# Include URL configuration files for site-specified extra installed
# Django apps
for app_name in settings.EXTRA_INSTALLED_APPS:
    app_dir = os.path.join(settings.DEPLOY_ROOT, app_name)
    if os.path.exists(os.path.join(app_dir, 'urls.py')):
        urls += [path('', include(f'{app_name}.urls'))]
        i18n_urls += import_string(f"{app_name}.urls.i18n_urlpatterns")

# Tornado views
urls += [
    # Used internally for communication between Django and Tornado processes
    #
    # Since these views don't use rest_dispatch, they cannot have
    # asynchronous Tornado behavior.
    path('notify_tornado', zerver.tornado.views.notify,
         name='zerver.tornado.views.notify'),
    path('api/v1/events/internal', zerver.tornado.views.get_events_internal),
]

# Python Social Auth

urls += [path('', include('social_django.urls', namespace='social'))]
urls += [path('saml/metadata.xml', zerver.views.auth.saml_sp_metadata)]

# User documentation site
urls += [re_path(r'^help/(?P<article>.*)$',
                 MarkdownDirectoryView.as_view(template_name='zerver/documentation_main.html',
                                               path_template='/zerver/help/%s.md'))]
urls += [re_path(r'^api/(?P<article>[-\w]*\/?)$',
                 MarkdownDirectoryView.as_view(template_name='zerver/documentation_main.html',
                                               path_template='/zerver/api/%s.md'))]

# Two Factor urls
if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
    urls += [path('', include(tf_urls)),
             path('', include(tf_twilio_urls))]

if settings.DEVELOPMENT:
    urls += dev_urls.urls
    i18n_urls += dev_urls.i18n_urls

# The sequence is important; if i18n urls don't come first then
# reverse url mapping points to i18n urls which causes the frontend
# tests to fail
urlpatterns = i18n_patterns(*i18n_urls) + urls + legacy_urls

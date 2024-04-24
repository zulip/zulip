import os
from typing import List, Union

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
from django.urls.resolvers import URLPattern, URLResolver
from django.utils.module_loading import import_string
from django.views.generic import RedirectView

from zerver.forms import LoggingSetPasswordForm
from zerver.lib.integrations import WEBHOOK_INTEGRATIONS
from zerver.lib.rest import rest_path
from zerver.lib.url_redirects import DOCUMENTATION_REDIRECTS
from zerver.tornado.views import (
    cleanup_event_queue,
    get_events,
    get_events_internal,
    notify,
    web_reload_clients,
)
from zerver.views.alert_words import add_alert_words, list_alert_words, remove_alert_words
from zerver.views.attachments import list_by_user, remove
from zerver.views.auth import (
    api_fetch_api_key,
    api_get_server_settings,
    json_fetch_api_key,
    jwt_fetch_api_key,
    log_into_subdomain,
    login_page,
    logout_view,
    password_reset,
    remote_user_jwt,
    remote_user_sso,
    saml_sp_metadata,
    show_deactivation_notice,
    start_remote_user_sso,
    start_social_login,
    start_social_signup,
)
from zerver.views.compatibility import check_global_compatibility
from zerver.views.custom_profile_fields import (
    create_realm_custom_profile_field,
    delete_realm_custom_profile_field,
    list_realm_custom_profile_fields,
    remove_user_custom_profile_data,
    reorder_realm_custom_profile_fields,
    update_realm_custom_profile_field,
    update_user_custom_profile_data,
)
from zerver.views.digest import digest_page
from zerver.views.documentation import IntegrationView, MarkdownDirectoryView, integration_doc
from zerver.views.drafts import create_drafts, delete_draft, edit_draft, fetch_drafts
from zerver.views.email_mirror import email_mirror_message
from zerver.views.events_register import events_register_backend
from zerver.views.health import health
from zerver.views.home import accounts_accept_terms, desktop_home, home
from zerver.views.hotspots import mark_onboarding_step_as_read
from zerver.views.invite import (
    generate_multiuse_invite_backend,
    get_user_invites,
    invite_users_backend,
    resend_user_invite_email,
    revoke_multiuse_invite,
    revoke_user_invite,
)
from zerver.views.message_edit import (
    delete_message_backend,
    get_message_edit_history,
    json_fetch_raw_message,
    update_message_backend,
)
from zerver.views.message_fetch import get_messages_backend, messages_in_narrow_backend
from zerver.views.message_flags import (
    mark_all_as_read,
    mark_stream_as_read,
    mark_topic_as_read,
    update_message_flags,
    update_message_flags_for_narrow,
)
from zerver.views.message_send import render_message_backend, send_message_backend, zcommand_backend
from zerver.views.muted_users import mute_user, unmute_user
from zerver.views.presence import (
    get_presence_backend,
    get_statuses_for_realm,
    update_active_status_backend,
    update_user_status_backend,
)
from zerver.views.push_notifications import (
    add_android_reg_id,
    add_apns_device_token,
    remove_android_reg_id,
    remove_apns_device_token,
    self_hosting_auth_json_endpoint,
    self_hosting_auth_not_configured,
    self_hosting_auth_redirect_endpoint,
    send_test_push_notification_api,
)
from zerver.views.reactions import add_reaction, remove_reaction
from zerver.views.read_receipts import read_receipts
from zerver.views.realm import (
    check_subdomain_available,
    deactivate_realm,
    realm_reactivation,
    update_realm,
    update_realm_user_settings_defaults,
)
from zerver.views.realm_domains import (
    create_realm_domain,
    delete_realm_domain,
    list_realm_domains,
    patch_realm_domain,
)
from zerver.views.realm_emoji import delete_emoji, list_emoji, upload_emoji
from zerver.views.realm_export import delete_realm_export, export_realm, get_realm_exports
from zerver.views.realm_icon import delete_icon_backend, get_icon_backend, upload_icon
from zerver.views.realm_linkifiers import (
    create_linkifier,
    delete_linkifier,
    list_linkifiers,
    reorder_linkifiers,
    update_linkifier,
)
from zerver.views.realm_logo import delete_logo_backend, get_logo_backend, upload_logo
from zerver.views.realm_playgrounds import add_realm_playground, delete_realm_playground
from zerver.views.registration import (
    accounts_home,
    accounts_home_from_multiuse_invite,
    accounts_register,
    create_realm,
    find_account,
    get_prereg_key_and_redirect,
    new_realm_send_confirm,
    realm_redirect,
    realm_register,
    signup_send_confirm,
)
from zerver.views.report import report_csp_violations
from zerver.views.scheduled_messages import (
    create_scheduled_message_backend,
    delete_scheduled_messages,
    fetch_scheduled_messages,
    update_scheduled_message_backend,
)
from zerver.views.sentry import sentry_tunnel
from zerver.views.storage import get_storage, remove_storage, update_storage
from zerver.views.streams import (
    add_default_stream,
    add_subscriptions_backend,
    create_default_stream_group,
    deactivate_stream_backend,
    delete_in_topic,
    get_stream_backend,
    get_stream_email_address,
    get_streams_backend,
    get_subscribers_backend,
    get_topics_backend,
    json_get_stream_id,
    list_subscriptions_backend,
    remove_default_stream,
    remove_default_stream_group,
    remove_subscriptions_backend,
    update_default_stream_group_info,
    update_default_stream_group_streams,
    update_stream_backend,
    update_subscription_properties_backend,
    update_subscriptions_backend,
    update_subscriptions_property,
)
from zerver.views.submessage import process_submessage
from zerver.views.thumbnail import backend_serve_thumbnail
from zerver.views.tutorial import set_tutorial_status
from zerver.views.typing import send_notification_backend
from zerver.views.unsubscribe import email_unsubscribe
from zerver.views.upload import (
    serve_file_backend,
    serve_file_download_backend,
    serve_file_unauthed_from_token,
    serve_file_url_backend,
    serve_local_avatar_unauthed,
    upload_file_backend,
)
from zerver.views.user_groups import (
    add_user_group,
    delete_user_group,
    edit_user_group,
    get_is_user_group_member,
    get_subgroups_of_user_group,
    get_user_group,
    get_user_group_members,
    update_subgroups_of_user_group,
    update_user_group_backend,
)
from zerver.views.user_settings import (
    confirm_email_change,
    delete_avatar_backend,
    json_change_settings,
    regenerate_api_key,
    set_avatar_backend,
)
from zerver.views.user_topics import update_muted_topic, update_user_topic
from zerver.views.users import (
    add_bot_backend,
    avatar,
    avatar_medium,
    create_user_backend,
    deactivate_bot_backend,
    deactivate_user_backend,
    deactivate_user_own_backend,
    get_bots_backend,
    get_members_backend,
    get_profile_backend,
    get_subscription_backend,
    get_user_by_email,
    patch_bot_backend,
    reactivate_user_backend,
    regenerate_bot_api_key,
    update_user_backend,
)
from zerver.views.video_calls import (
    complete_zoom_user,
    deauthorize_zoom_user,
    get_bigbluebutton_url,
    join_bigbluebutton,
    make_zoom_video_call,
    register_zoom_user,
)
from zerver.views.zephyr import webathena_kerberos_login
from zproject import dev_urls

if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:  # nocoverage
    from two_factor.gateways.twilio.urls import urlpatterns as tf_twilio_urls
    from two_factor.urls import urlpatterns as tf_urls

# NB: There are several other pieces of code which route requests by URL:
#
#   - runtornado.py has its own URL list for Tornado views.  See the
#     invocation of web.Application in that file.
#
#   - The nginx config knows which URLs to route to Django or Tornado.
#
#   - Likewise for the local dev server in tools/run-dev.

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
    rest_path("realm", PATCH=update_realm),
    rest_path("realm/user_settings_defaults", PATCH=update_realm_user_settings_defaults),
    path("realm/subdomain/<subdomain>", check_subdomain_available),
    # realm/domains -> zerver.views.realm_domains
    rest_path("realm/domains", GET=list_realm_domains, POST=create_realm_domain),
    rest_path("realm/domains/<domain>", PATCH=patch_realm_domain, DELETE=delete_realm_domain),
    # realm/emoji -> zerver.views.realm_emoji
    rest_path("realm/emoji", GET=list_emoji),
    rest_path(
        "realm/emoji/<path:emoji_name>",
        POST=upload_emoji,
        DELETE=delete_emoji,
    ),
    # realm/icon -> zerver.views.realm_icon
    rest_path("realm/icon", POST=upload_icon, DELETE=delete_icon_backend, GET=get_icon_backend),
    # realm/logo -> zerver.views.realm_logo
    rest_path("realm/logo", POST=upload_logo, DELETE=delete_logo_backend, GET=get_logo_backend),
    # realm/filters and realm/linkifiers -> zerver.views.realm_linkifiers
    rest_path("realm/linkifiers", GET=list_linkifiers, PATCH=reorder_linkifiers),
    rest_path("realm/filters", POST=create_linkifier),
    rest_path("realm/filters/<int:filter_id>", DELETE=delete_linkifier, PATCH=update_linkifier),
    # realm/playgrounds -> zerver.views.realm_playgrounds
    rest_path("realm/playgrounds", POST=add_realm_playground),
    rest_path("realm/playgrounds/<int:playground_id>", DELETE=delete_realm_playground),
    # realm/profile_fields -> zerver.views.custom_profile_fields
    rest_path(
        "realm/profile_fields",
        GET=list_realm_custom_profile_fields,
        PATCH=reorder_realm_custom_profile_fields,
        POST=create_realm_custom_profile_field,
    ),
    rest_path(
        "realm/profile_fields/<int:field_id>",
        PATCH=update_realm_custom_profile_field,
        DELETE=delete_realm_custom_profile_field,
    ),
    # realm/deactivate -> zerver.views.deactivate_realm
    rest_path("realm/deactivate", POST=deactivate_realm),
    # users -> zerver.views.users
    rest_path("users", GET=get_members_backend, POST=create_user_backend),
    rest_path("users/me", GET=get_profile_backend, DELETE=deactivate_user_own_backend),
    rest_path("users/<int:user_id>/reactivate", POST=reactivate_user_backend),
    rest_path(
        "users/<int:user_id>",
        GET=get_members_backend,
        PATCH=update_user_backend,
        DELETE=deactivate_user_backend,
    ),
    rest_path("users/<int:user_id>/subscriptions/<int:stream_id>", GET=get_subscription_backend),
    rest_path("users/<email>", GET=get_user_by_email),
    rest_path("bots", GET=get_bots_backend, POST=add_bot_backend),
    rest_path("bots/<int:bot_id>/api_key/regenerate", POST=regenerate_bot_api_key),
    rest_path("bots/<int:bot_id>", PATCH=patch_bot_backend, DELETE=deactivate_bot_backend),
    # invites -> zerver.views.invite
    rest_path("invites", GET=get_user_invites, POST=invite_users_backend),
    rest_path("invites/<int:invite_id>", DELETE=revoke_user_invite),
    rest_path("invites/<int:prereg_id>/resend", POST=resend_user_invite_email),
    # invites/multiuse -> zerver.views.invite
    rest_path("invites/multiuse", POST=generate_multiuse_invite_backend),
    # invites/multiuse -> zerver.views.invite
    rest_path("invites/multiuse/<int:invite_id>", DELETE=revoke_multiuse_invite),
    # mark messages as read (in bulk)
    rest_path("mark_all_as_read", POST=mark_all_as_read),
    rest_path("mark_stream_as_read", POST=mark_stream_as_read),
    rest_path("mark_topic_as_read", POST=mark_topic_as_read),
    rest_path("zcommand", POST=zcommand_backend),
    # Endpoints for syncing drafts.
    rest_path("drafts", GET=fetch_drafts, POST=create_drafts),
    rest_path("drafts/<int:draft_id>", PATCH=edit_draft, DELETE=delete_draft),
    # New scheduled messages are created via send_message_backend.
    rest_path(
        "scheduled_messages", GET=fetch_scheduled_messages, POST=create_scheduled_message_backend
    ),
    rest_path(
        "scheduled_messages/<int:scheduled_message_id>",
        DELETE=delete_scheduled_messages,
        PATCH=update_scheduled_message_backend,
    ),
    # messages -> zerver.views.message*
    # GET returns messages, possibly filtered, POST sends a message
    rest_path(
        "messages",
        GET=(get_messages_backend, {"allow_anonymous_user_web"}),
        POST=(send_message_backend, {"allow_incoming_webhooks"}),
    ),
    rest_path(
        "messages/<int:message_id>",
        GET=(json_fetch_raw_message, {"allow_anonymous_user_web"}),
        PATCH=update_message_backend,
        DELETE=delete_message_backend,
    ),
    rest_path("messages/render", POST=render_message_backend),
    rest_path("messages/flags", POST=update_message_flags),
    rest_path("messages/flags/narrow", POST=update_message_flags_for_narrow),
    rest_path("messages/<int:message_id>/history", GET=get_message_edit_history),
    rest_path("messages/matches_narrow", GET=messages_in_narrow_backend),
    rest_path("users/me/subscriptions/properties", POST=update_subscription_properties_backend),
    rest_path("users/me/subscriptions/<int:stream_id>", PATCH=update_subscriptions_property),
    rest_path("submessage", POST=process_submessage),
    # New endpoint for handling reactions.
    # reactions -> zerver.view.reactions
    # POST adds a reaction to a message
    # DELETE removes a reaction from a message
    rest_path("messages/<int:message_id>/reactions", POST=add_reaction, DELETE=remove_reaction),
    # read_receipts -> zerver.views.read_receipts
    rest_path("messages/<int:message_id>/read_receipts", GET=read_receipts),
    # attachments -> zerver.views.attachments
    rest_path("attachments", GET=list_by_user),
    rest_path("attachments/<int:attachment_id>", DELETE=remove),
    # typing -> zerver.views.typing
    # POST sends a typing notification event to recipients
    rest_path("typing", POST=send_notification_backend),
    # user_uploads -> zerver.views.upload
    rest_path("user_uploads", POST=upload_file_backend),
    rest_path(
        "user_uploads/<realm_id_str>/<path:filename>",
        GET=(serve_file_url_backend, {"override_api_url_scheme"}),
    ),
    # bot_storage -> zerver.views.storage
    rest_path("bot_storage", PUT=update_storage, GET=get_storage, DELETE=remove_storage),
    # Endpoint used by mobile devices to register their push
    # notification credentials
    rest_path(
        "users/me/apns_device_token", POST=add_apns_device_token, DELETE=remove_apns_device_token
    ),
    rest_path("users/me/android_gcm_reg_id", POST=add_android_reg_id, DELETE=remove_android_reg_id),
    rest_path("mobile_push/test_notification", POST=send_test_push_notification_api),
    # users/*/presence => zerver.views.presence.
    rest_path("users/me/presence", POST=update_active_status_backend),
    # It's important that this sit after users/me/presence so that
    # Django's URL resolution order doesn't break the
    # /users/me/presence endpoint.
    rest_path("users/<user_id_or_email>/presence", GET=get_presence_backend),
    rest_path("realm/presence", GET=get_statuses_for_realm),
    rest_path("users/me/status", POST=update_user_status_backend),
    # user_groups -> zerver.views.user_groups
    rest_path("user_groups", GET=get_user_group),
    rest_path("user_groups/create", POST=add_user_group),
    rest_path("user_groups/<int:user_group_id>", PATCH=edit_user_group, DELETE=delete_user_group),
    rest_path(
        "user_groups/<int:user_group_id>/members",
        GET=get_user_group_members,
        POST=update_user_group_backend,
    ),
    rest_path(
        "user_groups/<int:user_group_id>/subgroups",
        POST=update_subgroups_of_user_group,
        GET=get_subgroups_of_user_group,
    ),
    rest_path(
        "user_groups/<int:user_group_id>/members/<int:user_id>", GET=get_is_user_group_member
    ),
    # users/me -> zerver.views.user_settings
    rest_path("users/me/avatar", POST=set_avatar_backend, DELETE=delete_avatar_backend),
    # users/me/onboarding_steps -> zerver.views.hotspots
    rest_path(
        "users/me/onboarding_steps",
        POST=(
            mark_onboarding_step_as_read,
            # This endpoint is low priority for documentation as
            # it is part of the web app-specific tutorial.
            {"intentionally_undocumented"},
        ),
    ),
    # users/me/tutorial_status -> zerver.views.tutorial
    rest_path(
        "users/me/tutorial_status",
        POST=(
            set_tutorial_status,
            # This is a relic of an old Zulip tutorial model and
            # should be deleted.
            {"intentionally_undocumented"},
        ),
    ),
    # settings -> zerver.views.user_settings
    rest_path("settings", PATCH=json_change_settings),
    # These next two are legacy aliases for /settings, from before
    # we merged the endpoints. They are documented in the `/json/settings`
    # documentation, rather than having dedicated pages.
    rest_path("settings/display", PATCH=(json_change_settings, {"intentionally_undocumented"})),
    rest_path(
        "settings/notifications", PATCH=(json_change_settings, {"intentionally_undocumented"})
    ),
    # users/me/alert_words -> zerver.views.alert_words
    rest_path(
        "users/me/alert_words",
        GET=list_alert_words,
        POST=add_alert_words,
        DELETE=remove_alert_words,
    ),
    # users/me/custom_profile_data -> zerver.views.custom_profile_data
    rest_path(
        "users/me/profile_data",
        PATCH=update_user_custom_profile_data,
        DELETE=remove_user_custom_profile_data,
    ),
    rest_path(
        "users/me/<int:stream_id>/topics", GET=(get_topics_backend, {"allow_anonymous_user_web"})
    ),
    # streams -> zerver.views.streams
    # (this API is only used externally)
    rest_path("streams", GET=get_streams_backend),
    # GET returns `stream_id`, stream name should be encoded in the URL query (in `stream` param)
    rest_path("get_stream_id", GET=json_get_stream_id),
    # GET returns "stream info" (undefined currently?), HEAD returns whether stream exists (200 or 404)
    rest_path("streams/<int:stream_id>/members", GET=get_subscribers_backend),
    rest_path(
        "streams/<int:stream_id>",
        GET=get_stream_backend,
        PATCH=update_stream_backend,
        DELETE=deactivate_stream_backend,
    ),
    rest_path("streams/<int:stream_id>/email_address", GET=get_stream_email_address),
    # Delete topic in stream
    rest_path("streams/<int:stream_id>/delete_topic", POST=delete_in_topic),
    rest_path("default_streams", POST=add_default_stream, DELETE=remove_default_stream),
    rest_path("default_stream_groups/create", POST=create_default_stream_group),
    rest_path(
        "default_stream_groups/<int:group_id>",
        PATCH=update_default_stream_group_info,
        DELETE=remove_default_stream_group,
    ),
    rest_path(
        "default_stream_groups/<int:group_id>/streams", PATCH=update_default_stream_group_streams
    ),
    # GET lists your streams, POST bulk adds, PATCH bulk modifies/removes
    rest_path(
        "users/me/subscriptions",
        GET=list_subscriptions_backend,
        POST=add_subscriptions_backend,
        PATCH=update_subscriptions_backend,
        DELETE=remove_subscriptions_backend,
    ),
    # topic-muting -> zerver.views.user_topics
    # (deprecated and will be removed once clients are migrated to use '/user_topics')
    rest_path("users/me/subscriptions/muted_topics", PATCH=update_muted_topic),
    # used to update the personal preferences for a topic -> zerver.views.user_topics
    rest_path("user_topics", POST=update_user_topic),
    # user-muting -> zerver.views.user_mutes
    rest_path("users/me/muted_users/<int:muted_user_id>", POST=mute_user, DELETE=unmute_user),
    # used to register for an event queue in tornado
    rest_path("register", POST=(events_register_backend, {"allow_anonymous_user_web"})),
    # events -> zerver.tornado.views
    rest_path("events", GET=get_events, DELETE=cleanup_event_queue),
    # Used to generate a Zoom video call URL
    rest_path("calls/zoom/create", POST=make_zoom_video_call),
    # Used to generate a BigBlueButton video call URL
    rest_path("calls/bigbluebutton/create", GET=get_bigbluebutton_url),
    # export/realm -> zerver.views.realm_export
    rest_path("export/realm", POST=export_realm, GET=get_realm_exports),
    rest_path("export/realm/<int:export_id>", DELETE=delete_realm_export),
]

integrations_view = IntegrationView.as_view()

# These views serve pages (HTML). As such, their internationalization
# must depend on the URL.
#
# If you're adding a new page to the website (as opposed to a new
# endpoint for use by code), you should add it here.
i18n_urls = [
    path("", home, name="home"),
    # We have a desktop-specific landing page in case we change our /
    # to not log in in the future. We don't want to require a new
    # desktop app build for everyone in that case
    path("desktop_home/", desktop_home),
    # Backwards-compatibility (legacy) Google auth URL for the mobile
    # apps; see https://github.com/zulip/zulip/issues/13081 for
    # background.  We can remove this once older versions of the
    # mobile app are no longer present in the wild.
    path("accounts/login/google/", start_social_login, {"backend": "google"}),
    path("accounts/login/start/sso/", start_remote_user_sso, name="start-login-sso"),
    path("accounts/login/sso/", remote_user_sso, name="login-sso"),
    path("accounts/login/jwt/", remote_user_jwt),
    path("accounts/login/social/<backend>", start_social_login, name="login-social"),
    path("accounts/login/social/<backend>/<extra_arg>", start_social_login, name="login-social"),
    path("accounts/register/social/<backend>", start_social_signup, name="signup-social"),
    path(
        "accounts/register/social/<backend>/<extra_arg>", start_social_signup, name="signup-social"
    ),
    path("accounts/login/subdomain/<token>", log_into_subdomain),
    # We have two entries for accounts/login; only the first one is
    # used for URL resolution.  The second here is to allow
    # reverse("login") in templates to
    # return `/accounts/login/`.
    path("accounts/login/", login_page, {"template_name": "zerver/login.html"}, name="login_page"),
    path("accounts/login/", LoginView.as_view(template_name="zerver/login.html"), name="login"),
    path("accounts/logout/", logout_view),
    path("accounts/webathena_kerberos_login/", webathena_kerberos_login),
    path("accounts/password/reset/", password_reset, name="password_reset"),
    path(
        "accounts/password/reset/done/",
        PasswordResetDoneView.as_view(template_name="zerver/reset_emailed.html"),
    ),
    path(
        "accounts/password/reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            success_url="/accounts/password/done/",
            template_name="zerver/reset_confirm.html",
            form_class=LoggingSetPasswordForm,
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/password/done/",
        PasswordResetCompleteView.as_view(template_name="zerver/reset_done.html"),
    ),
    path("accounts/deactivated/", show_deactivation_notice),
    # Displays digest email content in browser.
    path("digest/", digest_page),
    # Registration views, require a confirmation ID.
    path("accounts/home/", accounts_home),
    path(
        "accounts/send_confirm/",
        signup_send_confirm,
        name="signup_send_confirm",
    ),
    path(
        "accounts/new/send_confirm/",
        new_realm_send_confirm,
        name="new_realm_send_confirm",
    ),
    path("accounts/register/", accounts_register, name="accounts_register"),
    path("realm/register/", realm_register, name="realm_register"),
    path(
        "accounts/do_confirm/<confirmation_key>",
        get_prereg_key_and_redirect,
        name="get_prereg_key_and_redirect",
    ),
    path(
        "accounts/confirm_new_email/<confirmation_key>",
        confirm_email_change,
        name="confirm_email_change",
    ),
    # Email unsubscription endpoint. Allows for unsubscribing from various types of emails,
    # including welcome emails, missed direct messages, etc.
    path(
        "accounts/unsubscribe/<email_type>/<confirmation_key>",
        email_unsubscribe,
        name="unsubscribe",
    ),
    # Portico-styled page used to provide email confirmation of terms acceptance.
    path("accounts/accept_terms/", accounts_accept_terms, name="accept_terms"),
    # Find your account
    path("accounts/find/", find_account, name="find_account"),
    # Go to organization subdomain
    path("accounts/go/", realm_redirect, name="realm_redirect"),
    # Realm creation
    path("new/", create_realm),
    path("new/<creation_key>", create_realm, name="create_realm"),
    # Realm reactivation
    path("reactivate/<confirmation_key>", realm_reactivation, name="realm_reactivation"),
    # Login/registration
    path("register/", accounts_home, name="register"),
    path("login/", login_page, {"template_name": "zerver/login.html"}, name="login_page"),
    path("join/<confirmation_key>/", accounts_home_from_multiuse_invite, name="join"),
    # Used to generate a Zoom video call URL
    path("calls/zoom/register", register_zoom_user),
    path("calls/zoom/complete", complete_zoom_user),
    path("calls/zoom/deauthorize", deauthorize_zoom_user),
    # Used to join a BigBlueButton video call
    path("calls/bigbluebutton/join", join_bigbluebutton),
    # API and integrations documentation
    path("integrations/doc-html/<integration_name>", integration_doc),
    path("integrations/", integrations_view),
    path("integrations/<path:path>", integrations_view),
]

# Make a copy of i18n_urls so that they appear without prefix for english
urls: List[Union[URLPattern, URLResolver]] = list(i18n_urls)

# Include the dual-use patterns twice
urls += [
    path("api/v1/", include(v1_api_and_json_patterns)),
    path("json/", include(v1_api_and_json_patterns)),
]

# user_uploads -> zerver.views.upload.serve_file_backend
#
# This URL is an exception to the URL naming schemes for endpoints. It
# supports both API and session cookie authentication, using a single
# URL for both (not 'api/v1/' or 'json/' prefix). This is required to
# easily support the mobile apps fetching uploaded files without
# having to rewrite URLs, and is implemented using the
# 'override_api_url_scheme' flag passed to rest_dispatch
urls += [
    path(
        "user_uploads/temporary/<token>/<filename>",
        serve_file_unauthed_from_token,
        name="file_unauthed_from_token",
    ),
    rest_path(
        "user_uploads/download/<realm_id_str>/<path:filename>",
        GET=(serve_file_download_backend, {"override_api_url_scheme", "allow_anonymous_user_web"}),
    ),
    rest_path(
        "user_uploads/<realm_id_str>/<path:filename>",
        GET=(serve_file_backend, {"override_api_url_scheme", "allow_anonymous_user_web"}),
    ),
    # This endpoint redirects to camo; it requires an exception for the
    # same reason.
    rest_path(
        "thumbnail",
        GET=(backend_serve_thumbnail, {"override_api_url_scheme", "allow_anonymous_user_web"}),
    ),
    # Avatars have the same constraint because their URLs are included
    # in API data structures used by both the mobile and web clients.
    rest_path(
        "avatar/<email_or_id>",
        GET=(avatar, {"override_api_url_scheme", "allow_anonymous_user_web"}),
    ),
    rest_path(
        "avatar/<email_or_id>/medium",
        GET=(
            avatar_medium,
            {"override_api_url_scheme", "allow_anonymous_user_web"},
        ),
    ),
    path(
        "user_avatars/<path:path>",
        serve_local_avatar_unauthed,
        name="local_avatar_unauthed",
    ),
]

# This URL serves as a way to receive CSP violation reports from the users.
# We use this endpoint to just log these reports.
urls += [
    path("report/csp_violations", report_csp_violations),
]

# Incoming webhook URLs
# We don't create URLs for particular Git integrations here
# because of generic one below
urls.extend(incoming_webhook.url_object for incoming_webhook in WEBHOOK_INTEGRATIONS)

# Desktop-specific authentication URLs
urls += [
    rest_path("json/fetch_api_key", POST=json_fetch_api_key),
]

# Mobile-specific authentication URLs
urls += [
    # Used as a global check by all mobile clients, which currently send
    # requests to https://zulip.com/compatibility almost immediately after
    # starting up.
    path("compatibility", check_global_compatibility),
]

v1_api_mobile_patterns = [
    # This json format view used by the mobile apps lists which
    # authentication backends the server allows as well as details
    # like the requested subdomains'd realm icon (if known) and
    # server-specific compatibility.
    path("server_settings", api_get_server_settings),
    # This json format view used by the mobile apps accepts a username
    # password/pair and returns an API key.
    path("fetch_api_key", api_fetch_api_key),
    # The endpoint for regenerating and obtaining a new API key
    # should only be available by authenticating with the current
    # API key - as we consider access to the API key sensitive
    # and just having a logged-in session should be insufficient.
    rest_path("users/me/api_key/regenerate", POST=regenerate_api_key),
    #  This view accepts a JWT containing an email and returns an API key
    #  and the details for a single user.
    path("jwt/fetch_api_key", jwt_fetch_api_key),
]

# Include URL configuration files for site-specified extra installed
# Django apps
for app_name in settings.EXTRA_INSTALLED_APPS:
    app_dir = os.path.join(settings.DEPLOY_ROOT, app_name)
    if os.path.exists(os.path.join(app_dir, "urls.py")):
        urls += [path("", include(f"{app_name}.urls"))]
        i18n_urls += import_string(f"{app_name}.urls.i18n_urlpatterns")

# Used internally for communication between command-line, Django,
# and Tornado processes
urls += [
    path("api/internal/email_mirror_message", email_mirror_message),
    path("api/internal/notify_tornado", notify),
    path("api/internal/web_reload_clients", web_reload_clients),
    path("api/v1/events/internal", get_events_internal),
]

# Python Social Auth

urls += [path("", include("social_django.urls", namespace="social"))]
urls += [path("saml/metadata.xml", saml_sp_metadata)]


# SCIM2

from django_scim import views as scim_views

urls += [
    # Everything below here are features that we don't yet support and we want
    # to explicitly mark them to return "Not Implemented" rather than running
    # the django-scim2 code for them.
    re_path(
        r"^scim/v2/Groups/.search$",
        scim_views.SCIMView.as_view(implemented=False),
    ),
    re_path(
        r"^scim/v2/Groups(?:/(?P<uuid>[^/]+))?$",
        scim_views.SCIMView.as_view(implemented=False),
    ),
    re_path(r"^scim/v2/Me$", scim_views.SCIMView.as_view(implemented=False)),
    re_path(
        r"^scim/v2/ServiceProviderConfig$",
        scim_views.SCIMView.as_view(implemented=False),
    ),
    re_path(
        r"^scim/v2/ResourceTypes(?:/(?P<uuid>[^/]+))?$",
        scim_views.SCIMView.as_view(implemented=False),
    ),
    re_path(
        r"^scim/v2/Schemas(?:/(?P<uuid>[^/]+))?$", scim_views.SCIMView.as_view(implemented=False)
    ),
    re_path(r"^scim/v2/Bulk$", scim_views.SCIMView.as_view(implemented=False)),
    # This registers the remaining SCIM endpoints.
    path("scim/v2/", include("django_scim.urls", namespace="scim")),
]

# Front-end Sentry requests tunnel through the server, if enabled
if settings.SENTRY_FRONTEND_DSN:  # nocoverage
    urls += [path("error_tracing", sentry_tunnel)]

# User documentation site
help_documentation_view = MarkdownDirectoryView.as_view(
    template_name="zerver/documentation_main.html",
    path_template=f"{settings.DEPLOY_ROOT}/help/%s.md",
    help_view=True,
)
api_documentation_view = MarkdownDirectoryView.as_view(
    template_name="zerver/documentation_main.html",
    path_template=f"{settings.DEPLOY_ROOT}/api_docs/%s.md",
    api_doc_view=True,
)
policy_documentation_view = MarkdownDirectoryView.as_view(
    template_name="zerver/documentation_main.html",
    policies_view=True,
)

# Redirects due to us having moved help center, API or policy documentation pages:
for redirect in DOCUMENTATION_REDIRECTS:
    old_url = redirect.old_url.lstrip("/")
    urls += [path(old_url, RedirectView.as_view(url=redirect.new_url, permanent=True))]

urls += [
    path("help/", help_documentation_view),
    path("help/<path:article>", help_documentation_view),
    path("api/", api_documentation_view),
    path("api/<slug:article>", api_documentation_view),
    path("policies/", policy_documentation_view),
    path("policies/<slug:article>", policy_documentation_view),
]

urls += [
    path(
        "self-hosted-billing/",
        self_hosting_auth_redirect_endpoint,
        name="self_hosting_auth_redirect_endpoint",
    ),
    path(
        "self-hosted-billing/not-configured/",
        self_hosting_auth_not_configured,
    ),
    rest_path(
        "json/self-hosted-billing",
        GET=self_hosting_auth_json_endpoint,
    ),
]

if not settings.CORPORATE_ENABLED:  # nocoverage
    # This conditional behavior cannot be tested directly, since
    # urls.py is not readily reloaded in Django tests. See the block
    # comment inside apps_view for details.
    urls += [
        path("apps/", RedirectView.as_view(url="https://zulip.com/apps/", permanent=True)),
    ]

# Two-factor URLs
if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:  # nocoverage
    urls += [path("", include(tf_urls)), path("", include(tf_twilio_urls))]

if settings.DEVELOPMENT:
    urls += dev_urls.urls
    i18n_urls += dev_urls.i18n_urls
    v1_api_mobile_patterns += dev_urls.v1_api_mobile_patterns

urls += [
    path("api/v1/", include(v1_api_mobile_patterns)),
]

# Healthcheck URL
urls += [path("health", health)]

# The sequence is important; if i18n URLs don't come first then
# reverse URL mapping points to i18n URLs which causes the frontend
# tests to fail
urlpatterns = i18n_patterns(*i18n_urls) + urls

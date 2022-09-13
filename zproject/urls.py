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
from django.views.generic import RedirectView, TemplateView

from zerver.forms import LoggingSetPasswordForm
from zerver.lib.integrations import WEBHOOK_INTEGRATIONS
from zerver.lib.rest import rest_path
from zerver.tornado.views import cleanup_event_queue, get_events, get_events_internal, notify
from zerver.views.alert_words import add_alert_words, list_alert_words, remove_alert_words
from zerver.views.attachments import list_by_user, remove
from zerver.views.auth import (
    api_fetch_api_key,
    api_get_server_settings,
    json_fetch_api_key,
    jwt_fetch_api_key,
    log_into_subdomain,
    login_page,
    logout_then_login,
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
from zerver.views.home import accounts_accept_terms, desktop_home, home
from zerver.views.hotspots import mark_hotspot_as_read
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
)
from zerver.views.message_send import render_message_backend, send_message_backend, zcommand_backend
from zerver.views.muting import mute_user, unmute_user, update_muted_topic
from zerver.views.portico import (
    app_download_link_redirect,
    apps_view,
    hello_view,
    landing_view,
    plans_view,
    team_view,
)
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
)
from zerver.views.reactions import add_reaction, remove_reaction
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
    realm_redirect,
)
from zerver.views.report import (
    report_csp_violations,
    report_error,
    report_narrow_times,
    report_send_times,
    report_unnarrow_times,
)
from zerver.views.storage import get_storage, remove_storage, update_storage
from zerver.views.streams import (
    add_default_stream,
    add_subscriptions_backend,
    create_default_stream_group,
    deactivate_stream_backend,
    delete_in_topic,
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
    serve_file_url_backend,
    serve_local_file_unauthed,
    upload_file_backend,
)
from zerver.views.user_groups import (
    add_user_group,
    delete_user_group,
    edit_user_group,
    get_user_group,
    update_user_group_backend,
)
from zerver.views.user_settings import (
    confirm_email_change,
    delete_avatar_backend,
    json_change_settings,
    regenerate_api_key,
    set_avatar_backend,
)
from zerver.views.users import (
    add_bot_backend,
    avatar,
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
#   - The nginx config knows which URLs to route to Django or Tornado.
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
    rest_path("realm", PATCH=update_realm),
    rest_path("realm/user_settings_defaults", PATCH=update_realm_user_settings_defaults),
    path("realm/subdomain/<subdomain>", check_subdomain_available),
    # realm/domains -> zerver.views.realm_domains
    rest_path("realm/domains", GET=list_realm_domains, POST=create_realm_domain),
    rest_path("realm/domains/<domain>", PATCH=patch_realm_domain, DELETE=delete_realm_domain),
    # realm/emoji -> zerver.views.realm_emoji
    rest_path("realm/emoji", GET=list_emoji),
    rest_path(
        "realm/emoji/<emoji_name>",
        POST=upload_emoji,
        DELETE=(delete_emoji, {"intentionally_undocumented"}),
    ),
    # this endpoint throws a status code 400 JsonableError when it should be a 404.
    # realm/icon -> zerver.views.realm_icon
    rest_path("realm/icon", POST=upload_icon, DELETE=delete_icon_backend, GET=get_icon_backend),
    # realm/logo -> zerver.views.realm_logo
    rest_path("realm/logo", POST=upload_logo, DELETE=delete_logo_backend, GET=get_logo_backend),
    # realm/filters and realm/linkifiers -> zerver.views.realm_linkifiers
    rest_path("realm/linkifiers", GET=list_linkifiers),
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
    rest_path("invites/<int:prereg_id>", DELETE=revoke_user_invite),
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
    rest_path("user_groups/<int:user_group_id>/members", POST=update_user_group_backend),
    # users/me -> zerver.views.user_settings
    rest_path("users/me/avatar", POST=set_avatar_backend, DELETE=delete_avatar_backend),
    # users/me/hotspots -> zerver.views.hotspots
    rest_path(
        "users/me/hotspots",
        POST=(
            mark_hotspot_as_read,
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
        "streams/<int:stream_id>", PATCH=update_stream_backend, DELETE=deactivate_stream_backend
    ),
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
    # muting -> zerver.views.muting
    rest_path("users/me/subscriptions/muted_topics", PATCH=update_muted_topic),
    rest_path("users/me/muted_users/<int:muted_user_id>", POST=mute_user, DELETE=unmute_user),
    # used to register for an event queue in tornado
    rest_path("register", POST=events_register_backend),
    # events -> zerver.tornado.views
    rest_path("events", GET=get_events, DELETE=cleanup_event_queue),
    # report -> zerver.views.report
    #
    # These endpoints are for internal error/performance reporting
    # from the browser to the web app, and we don't expect to ever
    # include in our API documentation.
    rest_path(
        "report/error",
        # Logged-out browsers can hit this endpoint, for portico page JS exceptions.
        POST=(report_error, {"allow_anonymous_user_web", "intentionally_undocumented"}),
    ),
    rest_path("report/send_times", POST=(report_send_times, {"intentionally_undocumented"})),
    rest_path(
        "report/narrow_times",
        POST=(report_narrow_times, {"allow_anonymous_user_web", "intentionally_undocumented"}),
    ),
    rest_path(
        "report/unnarrow_times",
        POST=(report_unnarrow_times, {"allow_anonymous_user_web", "intentionally_undocumented"}),
    ),
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
    path("accounts/logout/", logout_then_login),
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
        "accounts/send_confirm/<email>",
        TemplateView.as_view(template_name="zerver/accounts_send_confirm.html"),
        name="signup_send_confirm",
    ),
    path(
        "accounts/new/send_confirm/<email>",
        TemplateView.as_view(template_name="zerver/accounts_send_confirm.html"),
        {"realm_creation": True},
        name="new_realm_send_confirm",
    ),
    path("accounts/register/", accounts_register, name="accounts_register"),
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
    # including the welcome emails (day 1 & 2), missed PMs, etc.
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
    # Landing page, features pages, signup form, etc.
    path("hello/", hello_view),
    path("new-user/", RedirectView.as_view(url="/hello", permanent=True)),
    path("features/", landing_view, {"template_name": "zerver/features.html"}),
    path("plans/", plans_view, name="plans"),
    path("apps/", apps_view),
    path("apps/download/<platform>", app_download_link_redirect),
    path("apps/<platform>", apps_view),
    path(
        "developer-community/", RedirectView.as_view(url="/development-community/", permanent=True)
    ),
    path(
        "development-community/",
        landing_view,
        {"template_name": "zerver/development-community.html"},
    ),
    # Renamed to have a cleared URL.
    path(
        "developer-community/", RedirectView.as_view(url="/development-community/", permanent=True)
    ),
    path("attribution/", landing_view, {"template_name": "zerver/attribution.html"}),
    path("team/", team_view),
    path("history/", landing_view, {"template_name": "zerver/history.html"}),
    path("why-zulip/", landing_view, {"template_name": "zerver/why-zulip.html"}),
    path("for/education/", landing_view, {"template_name": "zerver/for-education.html"}),
    path("for/events/", landing_view, {"template_name": "zerver/for-events.html"}),
    path("for/open-source/", landing_view, {"template_name": "zerver/for-open-source.html"}),
    path("for/research/", landing_view, {"template_name": "zerver/for-research.html"}),
    path("for/business/", landing_view, {"template_name": "zerver/for-business.html"}),
    path("for/companies/", RedirectView.as_view(url="/for/business/", permanent=True)),
    path("case-studies/idrift/", landing_view, {"template_name": "zerver/idrift-case-study.html"}),
    path("case-studies/tum/", landing_view, {"template_name": "zerver/tum-case-study.html"}),
    path("case-studies/ucsd/", landing_view, {"template_name": "zerver/ucsd-case-study.html"}),
    path("case-studies/rust/", landing_view, {"template_name": "zerver/rust-case-study.html"}),
    path("case-studies/lean/", landing_view, {"template_name": "zerver/lean-case-study.html"}),
    path(
        "case-studies/asciidoctor/",
        landing_view,
        {"template_name": "zerver/asciidoctor-case-study.html"},
    ),
    path(
        "for/communities/",
        landing_view,
        {"template_name": "zerver/for-communities.html"},
    ),
    # We merged this into /for/communities.
    path(
        "for/working-groups-and-communities/",
        RedirectView.as_view(url="/for/communities/", permanent=True),
    ),
    path("use-cases/", landing_view, {"template_name": "zerver/use-cases.html"}),
    path("self-hosting/", landing_view, {"template_name": "zerver/self-hosting.html"}),
    path("security/", landing_view, {"template_name": "zerver/security.html"}),
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
        serve_local_file_unauthed,
        name="local_file_unauthed",
    ),
    rest_path(
        "user_uploads/download/<realm_id_str>/<path:filename>",
        GET=(serve_file_download_backend, {"override_api_url_scheme"}),
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
        {"medium": True},
        GET=(avatar, {"override_api_url_scheme", "allow_anonymous_user_web"}),
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
for incoming_webhook in WEBHOOK_INTEGRATIONS:
    if incoming_webhook.url_object:
        urls.append(incoming_webhook.url_object)

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
]

# View for uploading messages from email mirror
urls += [
    path("email_mirror_message", email_mirror_message),
]

#  This view accepts a JWT containing an email and returns an API key
#  and the details for a single user.
urls += [
    path("jwt/fetch_api_key", jwt_fetch_api_key),
]

# Include URL configuration files for site-specified extra installed
# Django apps
for app_name in settings.EXTRA_INSTALLED_APPS:
    app_dir = os.path.join(settings.DEPLOY_ROOT, app_name)
    if os.path.exists(os.path.join(app_dir, "urls.py")):
        urls += [path("", include(f"{app_name}.urls"))]
        i18n_urls += import_string(f"{app_name}.urls.i18n_urlpatterns")

# Tornado views
urls += [
    # Used internally for communication between Django and Tornado processes
    #
    # Since these views don't use rest_dispatch, they cannot have
    # asynchronous Tornado behavior.
    path("notify_tornado", notify),
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

# User documentation site
help_documentation_view = MarkdownDirectoryView.as_view(
    template_name="zerver/documentation_main.html", path_template="/zerver/help/%s.md"
)
api_documentation_view = MarkdownDirectoryView.as_view(
    template_name="zerver/documentation_main.html", path_template="/zerver/api/%s.md"
)
policy_documentation_view = MarkdownDirectoryView.as_view(
    template_name="zerver/documentation_main.html",
    policies_view=True,
)
urls += [
    # Redirects due to us having moved the docs:
    path(
        "help/delete-a-stream", RedirectView.as_view(url="/help/archive-a-stream", permanent=True)
    ),
    path("api/delete-stream", RedirectView.as_view(url="/api/archive-stream", permanent=True)),
    path(
        "help/change-the-topic-of-a-message",
        RedirectView.as_view(url="/help/rename-a-topic", permanent=True),
    ),
    path(
        "help/configure-missed-message-emails",
        RedirectView.as_view(url="/help/email-notifications", permanent=True),
    ),
    path(
        "help/add-an-alert-word",
        RedirectView.as_view(
            url="/help/pm-mention-alert-notifications#alert-words", permanent=True
        ),
    ),
    path(
        "help/test-mobile-notifications",
        RedirectView.as_view(url="/help/mobile-notifications", permanent=True),
    ),
    path(
        "help/troubleshooting-desktop-notifications",
        RedirectView.as_view(
            url="/help/desktop-notifications#troubleshooting-desktop-notifications", permanent=True
        ),
    ),
    path(
        "help/change-notification-sound",
        RedirectView.as_view(
            url="/help/desktop-notifications#change-notification-sound", permanent=True
        ),
    ),
    path(
        "help/configure-message-notification-emails",
        RedirectView.as_view(url="/help/email-notifications", permanent=True),
    ),
    path(
        "help/disable-new-login-emails",
        RedirectView.as_view(url="/help/email-notifications#new-login-emails", permanent=True),
    ),
    # This redirect is particularly important, because the old URL
    # appears in links from Welcome Bot messages.
    path(
        "help/about-streams-and-topics",
        RedirectView.as_view(url="/help/streams-and-topics", permanent=True),
    ),
    path(
        "help/community-topic-edits",
        RedirectView.as_view(url="/help/configure-who-can-edit-topics", permanent=True),
    ),
    path(
        "help/only-allow-admins-to-add-emoji",
        RedirectView.as_view(
            url="/help/custom-emoji#change-who-can-add-custom-emoji", permanent=True
        ),
    ),
    path(
        "help/configure-who-can-add-custom-emoji",
        RedirectView.as_view(
            url="/help/custom-emoji#change-who-can-add-custom-emoji", permanent=True
        ),
    ),
    path(
        "help/add-custom-emoji",
        RedirectView.as_view(url="/help/custom-emoji", permanent=True),
    ),
    path(
        "help/night-mode",
        RedirectView.as_view(url="/help/dark-theme", permanent=True),
    ),
    path("help/", help_documentation_view),
    path("help/<path:article>", help_documentation_view),
    path("api/", api_documentation_view),
    path("api/<slug:article>", api_documentation_view),
    path("policies/", policy_documentation_view),
    path("policies/<slug:article>", policy_documentation_view),
    path(
        "privacy/",
        RedirectView.as_view(url="/policies/privacy"),
    ),
    path(
        "terms/",
        RedirectView.as_view(url="/policies/terms"),
    ),
]

# Two-factor URLs
if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
    urls += [path("", include(tf_urls)), path("", include(tf_twilio_urls))]

if settings.DEVELOPMENT:
    urls += dev_urls.urls
    i18n_urls += dev_urls.i18n_urls
    v1_api_mobile_patterns += dev_urls.v1_api_mobile_patterns

urls += [
    path("api/v1/", include(v1_api_mobile_patterns)),
]

# The sequence is important; if i18n URLs don't come first then
# reverse URL mapping points to i18n URLs which causes the frontend
# tests to fail
urlpatterns = i18n_patterns(*i18n_urls) + urls + legacy_urls

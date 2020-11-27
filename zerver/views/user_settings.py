from typing import Any, Dict, Optional

import pytz
from django.conf import settings
from django.contrib.auth import authenticate, update_session_auth_hash
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.html import escape
from django.utils.safestring import SafeString
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from confirmation.models import (
    Confirmation,
    ConfirmationKeyException,
    get_object_from_key,
    render_confirmation_key_error,
)
from zerver.decorator import REQ, has_request_variables, human_users_only
from zerver.lib.actions import (
    check_change_full_name,
    do_change_avatar_fields,
    do_change_enter_sends,
    do_change_notification_settings,
    do_change_password,
    do_change_user_delivery_email,
    do_regenerate_api_key,
    do_set_user_display_setting,
    do_start_email_change_process,
    get_available_notification_sounds,
    validate_email_is_valid,
)
from zerver.lib.avatar import avatar_url
from zerver.lib.email_validation import (
    get_realm_email_validator,
    validate_email_not_already_in_realm,
)
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.rate_limiter import RateLimited
from zerver.lib.request import JsonableError
from zerver.lib.response import json_error, json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.upload import upload_avatar_image
from zerver.lib.validator import check_bool, check_int, check_int_in, check_string, check_string_in
from zerver.models import UserProfile, avatar_changes_disabled, name_changes_disabled
from zproject.backends import check_password_strength, email_belongs_to_ldap

AVATAR_CHANGES_DISABLED_ERROR = ugettext_lazy("Avatar changes are disabled in this organization.")

def confirm_email_change(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    try:
        email_change_object = get_object_from_key(confirmation_key, Confirmation.EMAIL_CHANGE)
    except ConfirmationKeyException as exception:
        return render_confirmation_key_error(request, exception)

    new_email = email_change_object.new_email
    old_email = email_change_object.old_email
    user_profile = email_change_object.user_profile

    if user_profile.realm.email_changes_disabled and not user_profile.is_realm_admin:
        raise JsonableError(_("Email address changes are disabled in this organization."))

    do_change_user_delivery_email(user_profile, new_email)

    context = {'realm_name': user_profile.realm.name, 'new_email': new_email}
    language = user_profile.default_language
    send_email('zerver/emails/notify_change_in_email', to_emails=[old_email],
               from_name=FromAddress.security_email_from_name(user_profile=user_profile),
               from_address=FromAddress.SUPPORT, language=language,
               context=context,
               realm=user_profile.realm)

    ctx = {
        'new_email_html_tag': SafeString(f'<a href="mailto:{escape(new_email)}">{escape(new_email)}</a>'),
        'old_email_html_tag': SafeString(f'<a href="mailto:{escape(old_email)}">{escape(old_email)}</a>'),

    }
    return render(request, 'confirmation/confirm_email_change.html', context=ctx)

@human_users_only
@has_request_variables
def json_change_settings(request: HttpRequest, user_profile: UserProfile,
                         full_name: str=REQ(default=""),
                         email: str=REQ(default=""),
                         old_password: str=REQ(default=""),
                         new_password: str=REQ(default="")) -> HttpResponse:
    if not (full_name or new_password or email):
        return json_error(_("Please fill out all fields."))

    if new_password != "":
        return_data: Dict[str, Any] = {}
        if email_belongs_to_ldap(user_profile.realm, user_profile.delivery_email):
            return json_error(_("Your Zulip password is managed in LDAP"))

        try:
            if not authenticate(request, username=user_profile.delivery_email, password=old_password,
                                realm=user_profile.realm, return_data=return_data):
                return json_error(_("Wrong password!"))
        except RateLimited as e:
            assert e.secs_to_freedom is not None
            secs_to_freedom = int(e.secs_to_freedom)
            return json_error(
                _("You're making too many attempts! Try again in {} seconds.").format(secs_to_freedom),
            )

        if not check_password_strength(new_password):
            return json_error(_("New password is too weak!"))

        do_change_password(user_profile, new_password)
        # In Django 1.10, password changes invalidates sessions, see
        # https://docs.djangoproject.com/en/1.10/topics/auth/default/#session-invalidation-on-password-change
        # for details. To avoid this logging the user out of their own
        # session (which would provide a confusing UX at best), we
        # update the session hash here.
        update_session_auth_hash(request, user_profile)
        # We also save the session to the DB immediately to mitigate
        # race conditions. In theory, there is still a race condition
        # and to completely avoid it we will have to use some kind of
        # mutex lock in `django.contrib.auth.get_user` where session
        # is verified. To make that lock work we will have to control
        # the AuthenticationMiddleware which is currently controlled
        # by Django,
        request.session.save()

    result: Dict[str, Any] = {}
    new_email = email.strip()
    if user_profile.delivery_email != new_email and new_email != '':
        if user_profile.realm.email_changes_disabled and not user_profile.is_realm_admin:
            return json_error(_("Email address changes are disabled in this organization."))

        error = validate_email_is_valid(
            new_email,
            get_realm_email_validator(user_profile.realm),
        )
        if error:
            return json_error(error)

        try:
            validate_email_not_already_in_realm(
                user_profile.realm,
                new_email,
                verbose=False,
            )
        except ValidationError as e:
            return json_error(e.message)

        do_start_email_change_process(user_profile, new_email)
        result['account_email'] = _("Check your email for a confirmation link. ")

    if user_profile.full_name != full_name and full_name.strip() != "":
        if name_changes_disabled(user_profile.realm) and not user_profile.is_realm_admin:
            # Failingly silently is fine -- they can't do it through the UI, so
            # they'd have to be trying to break the rules.
            pass
        else:
            # Note that check_change_full_name strips the passed name automatically
            result['full_name'] = check_change_full_name(user_profile, full_name, user_profile)

    return json_success(result)

emojiset_choices = {emojiset['key'] for emojiset in UserProfile.emojiset_choices()}

@human_users_only
@has_request_variables
def update_display_settings_backend(
        request: HttpRequest, user_profile: UserProfile,
        twenty_four_hour_time: Optional[bool]=REQ(validator=check_bool, default=None),
        dense_mode: Optional[bool]=REQ(validator=check_bool, default=None),
        starred_message_counts: Optional[bool]=REQ(validator=check_bool, default=None),
        fluid_layout_width: Optional[bool]=REQ(validator=check_bool, default=None),
        high_contrast_mode: Optional[bool]=REQ(validator=check_bool, default=None),
        color_scheme: Optional[int]=REQ(validator=check_int_in(
            UserProfile.COLOR_SCHEME_CHOICES), default=None),
        translate_emoticons: Optional[bool]=REQ(validator=check_bool, default=None),
        default_language: Optional[str]=REQ(validator=check_string, default=None),
        left_side_userlist: Optional[bool]=REQ(validator=check_bool, default=None),
        emojiset: Optional[str]=REQ(validator=check_string_in(
            emojiset_choices), default=None),
        demote_inactive_streams: Optional[int]=REQ(validator=check_int_in(
            UserProfile.DEMOTE_STREAMS_CHOICES), default=None),
        timezone: Optional[str]=REQ(validator=check_string_in(pytz.all_timezones_set),
                                    default=None)) -> HttpResponse:

    # We can't use REQ for this widget because
    # get_available_language_codes requires provisioning to be
    # complete.
    if (default_language is not None and
            default_language not in get_available_language_codes()):
        raise JsonableError(_("Invalid default_language"))

    request_settings = {k: v for k, v in list(locals().items()) if k in user_profile.property_types}
    result: Dict[str, Any] = {}
    for k, v in list(request_settings.items()):
        if v is not None and getattr(user_profile, k) != v:
            do_set_user_display_setting(user_profile, k, v)
            result[k] = v

    return json_success(result)

@human_users_only
@has_request_variables
def json_change_notify_settings(
        request: HttpRequest, user_profile: UserProfile,
        enable_stream_desktop_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_stream_email_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_stream_push_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_stream_audible_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        wildcard_mentions_notify: Optional[bool]=REQ(validator=check_bool, default=None),
        notification_sound: Optional[str]=REQ(validator=check_string, default=None),
        enable_desktop_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_sounds: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_offline_email_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_offline_push_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_online_push_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_digest_emails: Optional[bool]=REQ(validator=check_bool, default=None),
        enable_login_emails: Optional[bool]=REQ(validator=check_bool, default=None),
        message_content_in_email_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        pm_content_in_desktop_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        desktop_icon_count_display: Optional[int]=REQ(validator=check_int, default=None),
        realm_name_in_notifications: Optional[bool]=REQ(validator=check_bool, default=None),
        presence_enabled: Optional[bool]=REQ(validator=check_bool, default=None),
) -> HttpResponse:
    result = {}

    # Stream notification settings.

    if (notification_sound is not None and
            notification_sound not in get_available_notification_sounds()):
        raise JsonableError(_("Invalid notification sound '{}'").format(notification_sound))

    req_vars = {k: v for k, v in list(locals().items()) if k in user_profile.notification_setting_types}

    for k, v in list(req_vars.items()):
        if v is not None and getattr(user_profile, k) != v:
            do_change_notification_settings(user_profile, k, v, acting_user=user_profile)
            result[k] = v

    return json_success(result)

def set_avatar_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) != 1:
        return json_error(_("You must upload exactly one avatar."))

    if avatar_changes_disabled(user_profile.realm) and not user_profile.is_realm_admin:
        return json_error(str(AVATAR_CHANGES_DISABLED_ERROR))

    user_file = list(request.FILES.values())[0]
    if ((settings.MAX_AVATAR_FILE_SIZE * 1024 * 1024) < user_file.size):
        return json_error(_("Uploaded file is larger than the allowed limit of {} MiB").format(
            settings.MAX_AVATAR_FILE_SIZE,
        ))
    upload_avatar_image(user_file, user_profile, user_profile)
    do_change_avatar_fields(user_profile, UserProfile.AVATAR_FROM_USER, acting_user=user_profile)
    user_avatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url = user_avatar_url,
    )
    return json_success(json_result)

def delete_avatar_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if avatar_changes_disabled(user_profile.realm) and not user_profile.is_realm_admin:
        return json_error(str(AVATAR_CHANGES_DISABLED_ERROR))

    do_change_avatar_fields(user_profile, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=user_profile)
    gravatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url = gravatar_url,
    )
    return json_success(json_result)

# We don't use @human_users_only here, because there are use cases for
# a bot regenerating its own API key.
@has_request_variables
def regenerate_api_key(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    new_api_key = do_regenerate_api_key(user_profile, user_profile)
    json_result = dict(
        api_key = new_api_key,
    )
    return json_success(json_result)

@human_users_only
@has_request_variables
def change_enter_sends(request: HttpRequest, user_profile: UserProfile,
                       enter_sends: bool=REQ(validator=check_bool)) -> HttpResponse:
    do_change_enter_sends(user_profile, enter_sends)
    return json_success()

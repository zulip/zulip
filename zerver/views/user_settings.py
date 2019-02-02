from typing import Optional, Any, Dict

from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib.auth import authenticate, update_session_auth_hash
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from zerver.decorator import has_request_variables, \
    REQ, human_users_only
from zerver.lib.actions import do_change_password, do_change_notification_settings, \
    do_change_enter_sends, do_regenerate_api_key, do_change_avatar_fields, \
    do_set_user_display_setting, validate_email, do_change_user_delivery_email, \
    do_start_email_change_process, check_change_full_name, \
    get_available_notification_sounds
from zerver.lib.avatar import avatar_url
from zerver.lib.send_email import send_email, FromAddress
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.response import json_success, json_error
from zerver.lib.upload import upload_avatar_image
from zerver.lib.validator import check_bool, check_string
from zerver.lib.request import JsonableError
from zerver.lib.timezone import get_all_timezones
from zerver.models import UserProfile, name_changes_disabled
from confirmation.models import get_object_from_key, render_confirmation_key_error, \
    ConfirmationKeyException, Confirmation
from zproject.backends import email_belongs_to_ldap

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
    send_email('zerver/emails/notify_change_in_email', to_emails=[old_email],
               from_name="Zulip Account Security", from_address=FromAddress.SUPPORT,
               language=user_profile.default_language, context=context)

    ctx = {
        'new_email': new_email,
        'old_email': old_email,
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
        return_data = {}  # type: Dict[str, Any]
        if email_belongs_to_ldap(user_profile.realm, user_profile.delivery_email):
            return json_error(_("Your Zulip password is managed in LDAP"))
        if not authenticate(username=user_profile.delivery_email, password=old_password,
                            realm=user_profile.realm, return_data=return_data):
            return json_error(_("Wrong password!"))
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

    result = {}  # type: Dict[str, Any]
    new_email = email.strip()
    if user_profile.delivery_email != new_email and new_email != '':
        if user_profile.realm.email_changes_disabled and not user_profile.is_realm_admin:
            return json_error(_("Email address changes are disabled in this organization."))
        error, skipped = validate_email(user_profile, new_email)
        if error:
            return json_error(error)
        if skipped:
            return json_error(skipped)

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

@human_users_only
@has_request_variables
def update_display_settings_backend(
        request: HttpRequest, user_profile: UserProfile,
        twenty_four_hour_time: Optional[bool]=REQ(validator=check_bool, default=None),
        dense_mode: Optional[bool]=REQ(validator=check_bool, default=None),
        starred_message_counts: Optional[bool]=REQ(validator=check_bool, default=None),
        high_contrast_mode: Optional[bool]=REQ(validator=check_bool, default=None),
        night_mode: Optional[bool]=REQ(validator=check_bool, default=None),
        translate_emoticons: Optional[bool]=REQ(validator=check_bool, default=None),
        default_language: Optional[bool]=REQ(validator=check_string, default=None),
        left_side_userlist: Optional[bool]=REQ(validator=check_bool, default=None),
        emojiset: Optional[str]=REQ(validator=check_string, default=None),
        timezone: Optional[str]=REQ(validator=check_string, default=None)) -> HttpResponse:

    if (default_language is not None and
            default_language not in get_available_language_codes()):
        raise JsonableError(_("Invalid language '%s'" % (default_language,)))

    if (timezone is not None and
            timezone not in get_all_timezones()):
        raise JsonableError(_("Invalid timezone '%s'" % (timezone,)))

    if (emojiset is not None and
            emojiset not in UserProfile.emojiset_choices()):
        raise JsonableError(_("Invalid emojiset '%s'" % (emojiset,)))

    request_settings = {k: v for k, v in list(locals().items()) if k in user_profile.property_types}
    result = {}  # type: Dict[str, Any]
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
        enable_stream_sounds: Optional[bool]=REQ(validator=check_bool, default=None),
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
        realm_name_in_notifications: Optional[bool]=REQ(validator=check_bool, default=None)
) -> HttpResponse:
    result = {}

    # Stream notification settings.

    if (notification_sound is not None and
            notification_sound not in get_available_notification_sounds()):
        raise JsonableError(_("Invalid notification sound '%s'") % (notification_sound,))

    req_vars = {k: v for k, v in list(locals().items()) if k in user_profile.notification_setting_types}

    for k, v in list(req_vars.items()):
        if v is not None and getattr(user_profile, k) != v:
            do_change_notification_settings(user_profile, k, v)
            result[k] = v

    return json_success(result)

def set_avatar_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) != 1:
        return json_error(_("You must upload exactly one avatar."))

    user_file = list(request.FILES.values())[0]
    if ((settings.MAX_AVATAR_FILE_SIZE * 1024 * 1024) < user_file.size):
        return json_error(_("Uploaded file is larger than the allowed limit of %s MB") % (
            settings.MAX_AVATAR_FILE_SIZE))
    upload_avatar_image(user_file, user_profile, user_profile)
    do_change_avatar_fields(user_profile, UserProfile.AVATAR_FROM_USER)
    user_avatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url = user_avatar_url
    )
    return json_success(json_result)

def delete_avatar_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    do_change_avatar_fields(user_profile, UserProfile.AVATAR_FROM_GRAVATAR)
    gravatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url = gravatar_url
    )
    return json_success(json_result)

# We don't use @human_users_only here, because there are use cases for
# a bot regenerating its own API key.
@has_request_variables
def regenerate_api_key(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    do_regenerate_api_key(user_profile, user_profile)
    json_result = dict(
        api_key = user_profile.api_key
    )
    return json_success(json_result)

@human_users_only
@has_request_variables
def change_enter_sends(request: HttpRequest, user_profile: UserProfile,
                       enter_sends: bool=REQ(validator=check_bool)) -> HttpResponse:
    do_change_enter_sends(user_profile, enter_sends)
    return json_success()

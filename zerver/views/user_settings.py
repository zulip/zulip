from email.headerregistry import Address
from typing import Annotated, Any

from django.conf import settings
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import escape
from django.utils.safestring import SafeString
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from pydantic import Json

from confirmation.models import (
    Confirmation,
    ConfirmationKeyError,
    get_object_from_key,
    render_confirmation_key_error,
)
from zerver.actions.user_settings import (
    check_change_full_name,
    do_change_avatar_fields,
    do_change_password,
    do_change_user_delivery_email,
    do_change_user_setting,
    do_regenerate_api_key,
    do_start_email_change_process,
)
from zerver.actions.users import generate_password_reset_url
from zerver.decorator import human_users_only
from zerver.lib.avatar import avatar_url
from zerver.lib.email_validation import (
    get_realm_email_validator,
    validate_email_is_valid,
    validate_email_not_already_in_realm,
)
from zerver.lib.exceptions import JsonableError, RateLimitedError, UserDeactivatedError
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.rate_limiter import RateLimitedUser
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.sounds import get_available_notification_sounds
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.lib.typed_endpoint_validators import (
    check_int_in_validator,
    check_string_in_validator,
    timezone_validator,
)
from zerver.lib.upload import upload_avatar_image
from zerver.models import EmailChangeStatus, UserProfile
from zerver.models.realms import avatar_changes_disabled, name_changes_disabled
from zerver.views.auth import redirect_to_deactivation_notice
from zproject.backends import check_password_strength, email_belongs_to_ldap

AVATAR_CHANGES_DISABLED_ERROR = gettext_lazy("Avatar changes are disabled in this organization.")


def validate_email_change_request(user_profile: UserProfile, new_email: str) -> None:
    if not user_profile.is_active:
        raise UserDeactivatedError

    if user_profile.realm.email_changes_disabled and not user_profile.is_realm_admin:
        raise JsonableError(_("Email address changes are disabled in this organization."))

    error = validate_email_is_valid(
        new_email,
        get_realm_email_validator(user_profile.realm),
    )
    if error:
        raise JsonableError(error)

    try:
        validate_email_not_already_in_realm(
            user_profile.realm,
            new_email,
            verbose=False,
        )
    except ValidationError as e:
        raise JsonableError(e.message)


def confirm_email_change(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    try:
        email_change_object = get_object_from_key(
            confirmation_key, [Confirmation.EMAIL_CHANGE], mark_object_used=True
        )
    except ConfirmationKeyError as exception:
        return render_confirmation_key_error(request, exception)

    assert isinstance(email_change_object, EmailChangeStatus)
    new_email = email_change_object.new_email
    old_email = email_change_object.old_email
    with transaction.atomic(durable=True):
        user_profile = UserProfile.objects.select_for_update().get(
            id=email_change_object.user_profile_id
        )

        if user_profile.delivery_email != old_email:
            # This is not expected to be possible, since we deactivate
            # any previous email changes when we create a new one, but
            # double-check.
            return render_confirmation_key_error(
                request, ConfirmationKeyError(ConfirmationKeyError.EXPIRED)
            )  # nocoverage

        if user_profile.realm.deactivated:
            return redirect_to_deactivation_notice()
        try:
            validate_email_change_request(user_profile, new_email)
        except UserDeactivatedError:
            context = {"realm_url": user_profile.realm.url}
            return render(
                request,
                "zerver/portico_error_pages/user_deactivated.html",
                context=context,
                status=401,
            )
        do_change_user_delivery_email(user_profile, new_email, acting_user=user_profile)

    user_profile = UserProfile.objects.get(id=email_change_object.user_profile_id)
    context = {"realm_name": user_profile.realm.name, "new_email": new_email}
    language = user_profile.default_language

    if old_email == "":
        # The assertions here are to help document the only circumstance under which
        # this condition should be possible.
        assert (
            user_profile.realm.demo_organization_scheduled_deletion_date is not None
            and user_profile.is_realm_owner
        )
        # Because demo organizations are created without setting an email and password
        # we want to redirect to setting a password after configuring and confirming
        # an email for the owner's account.
        reset_password_url = generate_password_reset_url(user_profile, default_token_generator)
        return HttpResponseRedirect(reset_password_url)

    send_email(
        "zerver/emails/notify_change_in_email",
        to_emails=[old_email],
        from_name=FromAddress.security_email_from_name(user_profile=user_profile),
        from_address=FromAddress.SUPPORT,
        language=language,
        context=context,
        realm=user_profile.realm,
    )
    old_email_address = Address(addr_spec=old_email)
    new_email_address = Address(addr_spec=new_email)
    ctx = {
        "new_email_html_tag": SafeString(
            f'<a href="mailto:{escape(new_email)}">{escape(new_email_address.username)}@<wbr>{escape(new_email_address.domain)}</wbr></a>'
        ),
        "old_email_html_tag": SafeString(
            f'<a href="mailto:{escape(old_email)}">{escape(old_email_address.username)}@<wbr>{escape(old_email_address.domain)}</wbr></a>'
        ),
    }
    return render(request, "confirmation/confirm_email_change.html", context=ctx)


emojiset_choices = {emojiset["key"] for emojiset in UserProfile.emojiset_choices()}
web_home_view_options = ["recent_topics", "inbox", "all_messages"]
web_animate_image_previews_options = ["always", "on_hover", "never"]


def check_settings_values(
    notification_sound: str | None,
    email_notifications_batching_period_seconds: int | None,
    default_language: str | None = None,
) -> None:
    # We can't use typed_endpoint for this widget because
    # get_available_language_codes requires provisioning to be
    # complete.
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid default_language"))

    if (
        notification_sound is not None
        and notification_sound not in get_available_notification_sounds()
        and notification_sound != "none"
    ):
        raise JsonableError(
            _("Invalid notification sound '{notification_sound}'").format(
                notification_sound=notification_sound
            )
        )

    if email_notifications_batching_period_seconds is not None and (
        email_notifications_batching_period_seconds <= 0
        or email_notifications_batching_period_seconds > 7 * 24 * 60 * 60
    ):
        # We set a limit of one week for the batching period
        raise JsonableError(
            _("Invalid email batching period: {seconds} seconds").format(
                seconds=email_notifications_batching_period_seconds
            )
        )


@human_users_only
@typed_endpoint
def json_change_settings(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    full_name: str | None = None,
    email: str | None = None,
    old_password: str | None = None,
    new_password: str | None = None,
    twenty_four_hour_time: Json[bool] | None = None,
    web_mark_read_on_scroll_policy: Annotated[
        Json[int], check_int_in_validator(UserProfile.WEB_MARK_READ_ON_SCROLL_POLICY_CHOICES)
    ]
    | None = None,
    web_channel_default_view: Annotated[
        Json[int], check_int_in_validator(UserProfile.WEB_CHANNEL_DEFAULT_VIEW_CHOICES)
    ]
    | None = None,
    starred_message_counts: Json[bool] | None = None,
    receives_typing_notifications: Json[bool] | None = None,
    fluid_layout_width: Json[bool] | None = None,
    high_contrast_mode: Json[bool] | None = None,
    color_scheme: Annotated[Json[int], check_int_in_validator(UserProfile.COLOR_SCHEME_CHOICES)]
    | None = None,
    web_font_size_px: Json[int] | None = None,
    web_line_height_percent: Json[int] | None = None,
    translate_emoticons: Json[bool] | None = None,
    display_emoji_reaction_users: Json[bool] | None = None,
    default_language: str | None = None,
    web_home_view: Annotated[str, check_string_in_validator(web_home_view_options)] | None = None,
    web_escape_navigates_to_home_view: Json[bool] | None = None,
    left_side_userlist: Json[bool] | None = None,
    emojiset: Annotated[str, check_string_in_validator(emojiset_choices)] | None = None,
    demote_inactive_streams: Annotated[
        Json[int], check_int_in_validator(UserProfile.DEMOTE_STREAMS_CHOICES)
    ]
    | None = None,
    web_stream_unreads_count_display_policy: Annotated[
        Json[int],
        check_int_in_validator(UserProfile.WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_CHOICES),
    ]
    | None = None,
    timezone: Annotated[str, timezone_validator()] | None = None,
    email_notifications_batching_period_seconds: Json[int] | None = None,
    enable_drafts_synchronization: Json[bool] | None = None,
    enable_stream_desktop_notifications: Json[bool] | None = None,
    enable_stream_email_notifications: Json[bool] | None = None,
    enable_stream_push_notifications: Json[bool] | None = None,
    enable_stream_audible_notifications: Json[bool] | None = None,
    wildcard_mentions_notify: Json[bool] | None = None,
    enable_followed_topic_desktop_notifications: Json[bool] | None = None,
    enable_followed_topic_email_notifications: Json[bool] | None = None,
    enable_followed_topic_push_notifications: Json[bool] | None = None,
    enable_followed_topic_audible_notifications: Json[bool] | None = None,
    enable_followed_topic_wildcard_mentions_notify: Json[bool] | None = None,
    notification_sound: str | None = None,
    enable_desktop_notifications: Json[bool] | None = None,
    enable_sounds: Json[bool] | None = None,
    enable_offline_email_notifications: Json[bool] | None = None,
    enable_offline_push_notifications: Json[bool] | None = None,
    enable_online_push_notifications: Json[bool] | None = None,
    enable_digest_emails: Json[bool] | None = None,
    enable_login_emails: Json[bool] | None = None,
    enable_marketing_emails: Json[bool] | None = None,
    message_content_in_email_notifications: Json[bool] | None = None,
    pm_content_in_desktop_notifications: Json[bool] | None = None,
    desktop_icon_count_display: Annotated[
        Json[int], check_int_in_validator(UserProfile.DESKTOP_ICON_COUNT_DISPLAY_CHOICES)
    ]
    | None = None,
    realm_name_in_email_notifications_policy: Annotated[
        Json[int],
        check_int_in_validator(UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_CHOICES),
    ]
    | None = None,
    automatically_follow_topics_policy: Annotated[
        Json[int],
        check_int_in_validator(UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES),
    ]
    | None = None,
    automatically_unmute_topics_in_muted_streams_policy: Annotated[
        Json[int],
        check_int_in_validator(UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES),
    ]
    | None = None,
    automatically_follow_topics_where_mentioned: Json[bool] | None = None,
    presence_enabled: Json[bool] | None = None,
    enter_sends: Json[bool] | None = None,
    send_private_typing_notifications: Json[bool] | None = None,
    send_stream_typing_notifications: Json[bool] | None = None,
    send_read_receipts: Json[bool] | None = None,
    allow_private_data_export: Json[bool] | None = None,
    user_list_style: Annotated[
        Json[int], check_int_in_validator(UserProfile.USER_LIST_STYLE_CHOICES)
    ]
    | None = None,
    web_animate_image_previews: Annotated[
        str, check_string_in_validator(web_animate_image_previews_options)
    ]
    | None = None,
    email_address_visibility: Annotated[
        Json[int], check_int_in_validator(UserProfile.EMAIL_ADDRESS_VISIBILITY_TYPES)
    ]
    | None = None,
    web_navigate_to_sent_message: Json[bool] | None = None,
    web_suggest_update_timezone: Json[bool] | None = None,
    hide_ai_features: Json[bool] | None = None,
) -> HttpResponse:
    # UserProfile object is being refetched here to make sure that we
    # do not use stale object from cache which can happen when a
    # previous request tried updating multiple settings in a single
    # request.
    #
    # TODO: Change the cache flushing strategy to make sure cache
    # does not contain stale objects.
    user_profile = UserProfile.objects.get(id=user_profile.id)
    if (
        default_language is not None
        or notification_sound is not None
        or email_notifications_batching_period_seconds is not None
    ):
        check_settings_values(
            notification_sound, email_notifications_batching_period_seconds, default_language
        )

    if new_password is not None:
        return_data: dict[str, Any] = {}
        if email_belongs_to_ldap(user_profile.realm, user_profile.delivery_email):
            raise JsonableError(_("Your Zulip password is managed in LDAP"))

        try:
            if not authenticate(
                request,
                username=user_profile.delivery_email,
                password=old_password,
                realm=user_profile.realm,
                return_data=return_data,
            ):
                raise JsonableError(_("Wrong password!"))
        except RateLimitedError as e:
            assert e.secs_to_freedom is not None
            secs_to_freedom = int(e.secs_to_freedom)
            raise JsonableError(
                _("You're making too many attempts! Try again in {seconds} seconds.").format(
                    seconds=secs_to_freedom
                ),
            )

        if not check_password_strength(new_password):
            raise JsonableError(_("New password is too weak!"))

        do_change_password(user_profile, new_password)
        # Password changes invalidates sessions, see
        # https://docs.djangoproject.com/en/5.0/topics/auth/default/#session-invalidation-on-password-change
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

    result: dict[str, Any] = {}

    if email is not None:
        new_email = email.strip()
        if user_profile.delivery_email != new_email:
            validate_email_change_request(user_profile, new_email)

            ratelimited, time_until_free = RateLimitedUser(
                user_profile, domain="email_change_by_user"
            ).rate_limit()
            if ratelimited:
                raise RateLimitedError(time_until_free)

            do_start_email_change_process(user_profile, new_email)

    if full_name is not None and user_profile.full_name != full_name:
        if name_changes_disabled(user_profile.realm) and not user_profile.is_realm_admin:
            # Failingly silently is fine -- they can't do it through the UI, so
            # they'd have to be trying to break the rules.
            pass
        else:
            # Note that check_change_full_name strips the passed name automatically
            check_change_full_name(user_profile, full_name, user_profile)

    # Loop over user_profile.property_types
    request_settings = {k: v for k, v in locals().items() if k in user_profile.property_types}
    for k, v in request_settings.items():
        if v is not None and getattr(user_profile, k) != v:
            do_change_user_setting(user_profile, k, v, acting_user=user_profile)

    if timezone is not None and user_profile.timezone != timezone:
        do_change_user_setting(user_profile, "timezone", timezone, acting_user=user_profile)

    return json_success(request, data=result)


def set_avatar_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) != 1:
        raise JsonableError(_("You must upload exactly one avatar."))

    if avatar_changes_disabled(user_profile.realm) and not user_profile.is_realm_admin:
        raise JsonableError(str(AVATAR_CHANGES_DISABLED_ERROR))

    [user_file] = request.FILES.values()
    assert isinstance(user_file, UploadedFile)
    assert user_file.size is not None
    if user_file.size > settings.MAX_AVATAR_FILE_SIZE_MIB * 1024 * 1024:
        raise JsonableError(
            _("Uploaded file is larger than the allowed limit of {max_size} MiB").format(
                max_size=settings.MAX_AVATAR_FILE_SIZE_MIB,
            )
        )
    upload_avatar_image(user_file, user_profile)
    do_change_avatar_fields(user_profile, UserProfile.AVATAR_FROM_USER, acting_user=user_profile)
    user_avatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url=user_avatar_url,
    )
    return json_success(request, data=json_result)


def delete_avatar_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if avatar_changes_disabled(user_profile.realm) and not user_profile.is_realm_admin:
        raise JsonableError(str(AVATAR_CHANGES_DISABLED_ERROR))

    do_change_avatar_fields(
        user_profile, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=user_profile
    )
    gravatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url=gravatar_url,
    )
    return json_success(request, data=json_result)


# We don't use @human_users_only here, because there are use cases for
# a bot regenerating its own API key.
@typed_endpoint_without_parameters
def regenerate_api_key(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    new_api_key = do_regenerate_api_key(user_profile, user_profile)
    json_result = dict(
        api_key=new_api_key,
    )
    return json_success(request, data=json_result)

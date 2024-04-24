from email.headerregistry import Address
from typing import Any, Dict, List, Mapping, Optional, Union

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from zerver.actions.bots import (
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
)
from zerver.actions.create_user import do_create_user, do_reactivate_user, notify_created_bot
from zerver.actions.custom_profile_fields import (
    check_remove_custom_profile_field_value,
    do_update_user_custom_profile_data_if_changed,
)
from zerver.actions.user_settings import (
    check_change_bot_full_name,
    check_change_full_name,
    do_change_avatar_fields,
    do_regenerate_api_key,
)
from zerver.actions.users import (
    do_change_user_role,
    do_deactivate_user,
    do_update_bot_config_data,
    do_update_outgoing_webhook_service,
)
from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import require_member_or_admin, require_realm_admin
from zerver.forms import PASSWORD_TOO_WEAK_ERROR, CreateUserForm
from zerver.lib.avatar import avatar_url, get_avatar_for_inaccessible_user, get_gravatar_url
from zerver.lib.bot_config import set_bot_config
from zerver.lib.email_validation import email_allowed_for_realm
from zerver.lib.exceptions import (
    CannotDeactivateLastUserError,
    JsonableError,
    MissingAuthenticationError,
    OrganizationAdministratorRequiredError,
    OrganizationOwnerRequiredError,
)
from zerver.lib.integrations import EMBEDDED_BOTS
from zerver.lib.rate_limiter import rate_limit_spectator_attachment_access_by_file
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.streams import access_stream_by_id, access_stream_by_name, subscribed_to_stream
from zerver.lib.types import ProfileDataElementUpdateDict, ProfileDataElementValue, Validator
from zerver.lib.upload import upload_avatar_image
from zerver.lib.url_encoding import append_url_query_string
from zerver.lib.users import (
    APIUserDict,
    access_bot_by_id,
    access_user_by_email,
    access_user_by_id,
    add_service,
    check_bot_creation_policy,
    check_bot_name_available,
    check_can_access_user,
    check_full_name,
    check_short_name,
    check_valid_bot_config,
    check_valid_bot_type,
    check_valid_interface_type,
    get_api_key,
    get_users_for_api,
    max_message_id_for_user,
    validate_user_custom_profile_data,
)
from zerver.lib.utils import generate_api_key
from zerver.lib.validator import (
    check_bool,
    check_capped_string,
    check_dict,
    check_dict_only,
    check_int,
    check_int_in,
    check_list,
    check_none_or,
    check_string,
    check_union,
    check_url,
)
from zerver.models import Service, Stream, UserProfile
from zerver.models.realms import (
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    InvalidFakeEmailDomainError,
)
from zerver.models.users import (
    get_user_by_delivery_email,
    get_user_by_id_in_realm_including_cross_realm,
    get_user_including_cross_realm,
    get_user_profile_by_id_in_realm,
)
from zproject.backends import check_password_strength


def check_last_owner(user_profile: UserProfile) -> bool:
    owners = set(user_profile.realm.get_human_owner_users())
    return user_profile.is_realm_owner and not user_profile.is_bot and len(owners) == 1


@has_request_variables
def deactivate_user_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_id: int,
    deactivation_notification_comment: Optional[str] = REQ(
        str_validator=check_capped_string(max_length=2000), default=None
    ),
) -> HttpResponse:
    target = access_user_by_id(user_profile, user_id, for_admin=True)
    if target.is_realm_owner and not user_profile.is_realm_owner:
        raise OrganizationOwnerRequiredError
    if check_last_owner(target):
        raise JsonableError(_("Cannot deactivate the only organization owner"))
    if deactivation_notification_comment is not None:
        deactivation_notification_comment = deactivation_notification_comment.strip()
    return _deactivate_user_profile_backend(
        request,
        user_profile,
        target,
        deactivation_notification_comment=deactivation_notification_comment,
    )


def deactivate_user_own_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if UserProfile.objects.filter(realm=user_profile.realm, is_active=True).count() == 1:
        raise CannotDeactivateLastUserError(is_last_owner=False)
    if user_profile.is_realm_owner and check_last_owner(user_profile):
        raise CannotDeactivateLastUserError(is_last_owner=True)

    do_deactivate_user(user_profile, acting_user=user_profile)
    return json_success(request)


def deactivate_bot_backend(
    request: HttpRequest, user_profile: UserProfile, bot_id: int
) -> HttpResponse:
    target = access_bot_by_id(user_profile, bot_id)
    return _deactivate_user_profile_backend(
        request, user_profile, target, deactivation_notification_comment=None
    )


def _deactivate_user_profile_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    target: UserProfile,
    *,
    deactivation_notification_comment: Optional[str],
) -> HttpResponse:
    do_deactivate_user(target, acting_user=user_profile)

    # It's important that we check for None explicitly here, since ""
    # encodes sending an email without a custom administrator comment.
    if deactivation_notification_comment is not None:
        send_email(
            "zerver/emails/deactivate",
            to_user_ids=[target.id],
            from_address=FromAddress.NOREPLY,
            context={
                "deactivation_notification_comment": deactivation_notification_comment,
                "realm_uri": target.realm.uri,
                "realm_name": target.realm.name,
            },
        )
    return json_success(request)


def reactivate_user_backend(
    request: HttpRequest, user_profile: UserProfile, user_id: int
) -> HttpResponse:
    target = access_user_by_id(
        user_profile, user_id, allow_deactivated=True, allow_bots=True, for_admin=True
    )
    if target.is_bot:
        assert target.bot_type is not None
        check_bot_creation_policy(user_profile, target.bot_type)
        check_bot_name_available(user_profile.realm_id, target.full_name, is_activation=True)
    do_reactivate_user(target, acting_user=user_profile)
    return json_success(request)


check_profile_data: Validator[List[Dict[str, Optional[Union[int, ProfileDataElementValue]]]]] = (
    check_list(
        check_dict_only(
            [
                ("id", check_int),
                (
                    "value",
                    check_none_or(
                        check_union([check_string, check_list(check_int)]),
                    ),
                ),
            ]
        ),
    )
)


@has_request_variables
def update_user_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_id: int,
    full_name: Optional[str] = REQ(default=None),
    role: Optional[int] = REQ(
        default=None,
        json_validator=check_int_in(
            UserProfile.ROLE_TYPES,
        ),
    ),
    profile_data: Optional[List[Dict[str, Optional[Union[int, ProfileDataElementValue]]]]] = REQ(
        default=None,
        json_validator=check_profile_data,
    ),
) -> HttpResponse:
    target = access_user_by_id(
        user_profile, user_id, allow_deactivated=True, allow_bots=True, for_admin=True
    )

    if role is not None and target.role != role:
        # Require that the current user has permissions to
        # grant/remove the role in question.
        #
        # Logic replicated in patch_bot_backend.
        if UserProfile.ROLE_REALM_OWNER in [role, target.role] and not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError
        elif not user_profile.is_realm_admin:
            raise OrganizationAdministratorRequiredError

        if target.role == UserProfile.ROLE_REALM_OWNER and check_last_owner(target):
            raise JsonableError(
                _("The owner permission cannot be removed from the only organization owner.")
            )
        do_change_user_role(target, role, acting_user=user_profile)

    if full_name is not None and target.full_name != full_name and full_name.strip() != "":
        # We don't respect `name_changes_disabled` here because the request
        # is on behalf of the administrator.
        check_change_full_name(target, full_name, user_profile)

    if profile_data is not None:
        clean_profile_data: List[ProfileDataElementUpdateDict] = []
        for entry in profile_data:
            assert isinstance(entry["id"], int)
            assert not isinstance(entry["value"], int)
            if entry["value"] is None or not entry["value"]:
                field_id = entry["id"]
                check_remove_custom_profile_field_value(target, field_id)
            else:
                clean_profile_data.append(
                    {
                        "id": entry["id"],
                        "value": entry["value"],
                    }
                )
        validate_user_custom_profile_data(target.realm.id, clean_profile_data)
        do_update_user_custom_profile_data_if_changed(target, clean_profile_data)

    return json_success(request)


def avatar(
    request: HttpRequest,
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    email_or_id: str,
    medium: bool = False,
) -> HttpResponse:
    """Accepts an email address or user ID and returns the avatar"""
    is_email = False
    try:
        int(email_or_id)
    except ValueError:
        is_email = True

    if not maybe_user_profile.is_authenticated:
        # Allow anonymous access to avatars only if spectators are
        # enabled in the organization.
        realm = get_valid_realm_from_request(request)
        if not realm.allow_web_public_streams_access():
            raise MissingAuthenticationError

        # We only allow the ID format for accessing a user's avatar
        # for spectators. This is mainly for defense in depth, since
        # email_address_visibility should mean spectators only
        # interact with fake email addresses anyway.
        if is_email:
            raise MissingAuthenticationError

        if settings.RATE_LIMITING:
            unique_avatar_key = f"{realm.id}/{email_or_id}/{medium}"
            rate_limit_spectator_attachment_access_by_file(unique_avatar_key)
    else:
        realm = maybe_user_profile.realm

    try:
        if is_email:
            avatar_user_profile = get_user_including_cross_realm(email_or_id, realm)
        else:
            avatar_user_profile = get_user_by_id_in_realm_including_cross_realm(
                int(email_or_id), realm
            )

        url: Optional[str] = None
        if maybe_user_profile.is_authenticated and not check_can_access_user(
            avatar_user_profile, maybe_user_profile
        ):
            url = get_avatar_for_inaccessible_user()
        else:
            # If there is a valid user account passed in, use its avatar
            url = avatar_url(avatar_user_profile, medium=medium)
        assert url is not None
    except UserProfile.DoesNotExist:
        # If there is no such user, treat it as a new gravatar
        email = email_or_id
        avatar_version = 1
        url = get_gravatar_url(email, avatar_version, medium)

    # We can rely on the URL already having query parameters. Because
    # our templates depend on being able to use the ampersand to
    # add query parameters to our url, get_avatar_url does '?x=x'
    # hacks to prevent us from having to jump through decode/encode hoops.
    assert url is not None
    url = append_url_query_string(url, request.META["QUERY_STRING"])
    return redirect(url)


def avatar_medium(
    request: HttpRequest, maybe_user_profile: Union[UserProfile, AnonymousUser], email_or_id: str
) -> HttpResponse:
    return avatar(request, maybe_user_profile, email_or_id, medium=True)


def get_stream_name(stream: Optional[Stream]) -> Optional[str]:
    if stream:
        return stream.name
    return None


@require_member_or_admin
@has_request_variables
def patch_bot_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    bot_id: int,
    full_name: Optional[str] = REQ(default=None),
    role: Optional[int] = REQ(
        default=None,
        json_validator=check_int_in(
            UserProfile.ROLE_TYPES,
        ),
    ),
    bot_owner_id: Optional[int] = REQ(json_validator=check_int, default=None),
    config_data: Optional[Dict[str, str]] = REQ(
        default=None, json_validator=check_dict(value_validator=check_string)
    ),
    service_payload_url: Optional[str] = REQ(json_validator=check_url, default=None),
    service_interface: int = REQ(json_validator=check_int, default=1),
    default_sending_stream: Optional[str] = REQ(default=None),
    default_events_register_stream: Optional[str] = REQ(default=None),
    default_all_public_streams: Optional[bool] = REQ(default=None, json_validator=check_bool),
) -> HttpResponse:
    bot = access_bot_by_id(user_profile, bot_id)

    if full_name is not None:
        check_change_bot_full_name(bot, full_name, user_profile)

    if role is not None and bot.role != role:
        # Logic duplicated from update_user_backend.
        if UserProfile.ROLE_REALM_OWNER in [role, bot.role] and not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError
        elif not user_profile.is_realm_admin:
            raise OrganizationAdministratorRequiredError

        do_change_user_role(bot, role, acting_user=user_profile)

    if bot_owner_id is not None:
        try:
            owner = get_user_profile_by_id_in_realm(bot_owner_id, user_profile.realm)
        except UserProfile.DoesNotExist:
            raise JsonableError(_("Failed to change owner, no such user"))
        if not owner.is_active:
            raise JsonableError(_("Failed to change owner, user is deactivated"))
        if owner.is_bot:
            raise JsonableError(_("Failed to change owner, bots can't own other bots"))

        previous_owner = bot.bot_owner
        if previous_owner != owner:
            do_change_bot_owner(bot, owner, user_profile)

    if default_sending_stream is not None:
        if default_sending_stream == "":
            stream: Optional[Stream] = None
        else:
            (stream, sub) = access_stream_by_name(user_profile, default_sending_stream)
        do_change_default_sending_stream(bot, stream, acting_user=user_profile)
    if default_events_register_stream is not None:
        if default_events_register_stream == "":
            stream = None
        else:
            (stream, sub) = access_stream_by_name(user_profile, default_events_register_stream)
        do_change_default_events_register_stream(bot, stream, acting_user=user_profile)
    if default_all_public_streams is not None:
        do_change_default_all_public_streams(
            bot, default_all_public_streams, acting_user=user_profile
        )

    if service_payload_url is not None:
        check_valid_interface_type(service_interface)
        assert service_interface is not None
        do_update_outgoing_webhook_service(bot, service_interface, service_payload_url)

    if config_data is not None:
        do_update_bot_config_data(bot, config_data)

    if len(request.FILES) == 0:
        pass
    elif len(request.FILES) == 1:
        [user_file] = request.FILES.values()
        assert isinstance(user_file, UploadedFile)
        assert user_file.size is not None
        upload_avatar_image(user_file, user_profile, bot)
        avatar_source = UserProfile.AVATAR_FROM_USER
        do_change_avatar_fields(bot, avatar_source, acting_user=user_profile)
    else:
        raise JsonableError(_("You may only upload one file at a time"))

    json_result = dict(
        full_name=bot.full_name,
        avatar_url=avatar_url(bot),
        service_interface=service_interface,
        service_payload_url=service_payload_url,
        config_data=config_data,
        default_sending_stream=get_stream_name(bot.default_sending_stream),
        default_events_register_stream=get_stream_name(bot.default_events_register_stream),
        default_all_public_streams=bot.default_all_public_streams,
    )

    # Don't include the bot owner in case it is not set.
    # Default bots have no owner.
    if bot.bot_owner is not None:
        json_result["bot_owner"] = bot.bot_owner.email

    return json_success(request, data=json_result)


@require_member_or_admin
@has_request_variables
def regenerate_bot_api_key(
    request: HttpRequest, user_profile: UserProfile, bot_id: int
) -> HttpResponse:
    bot = access_bot_by_id(user_profile, bot_id)

    new_api_key = do_regenerate_api_key(bot, user_profile)
    json_result = dict(
        api_key=new_api_key,
    )
    return json_success(request, data=json_result)


@require_member_or_admin
@has_request_variables
def add_bot_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    full_name_raw: str = REQ("full_name"),
    short_name_raw: str = REQ("short_name"),
    bot_type: int = REQ(json_validator=check_int, default=UserProfile.DEFAULT_BOT),
    payload_url: str = REQ(json_validator=check_url, default=""),
    service_name: Optional[str] = REQ(default=None),
    config_data: Mapping[str, str] = REQ(
        default={}, json_validator=check_dict(value_validator=check_string)
    ),
    interface_type: int = REQ(json_validator=check_int, default=Service.GENERIC),
    default_sending_stream_name: Optional[str] = REQ("default_sending_stream", default=None),
    default_events_register_stream_name: Optional[str] = REQ(
        "default_events_register_stream", default=None
    ),
    default_all_public_streams: Optional[bool] = REQ(json_validator=check_bool, default=None),
) -> HttpResponse:
    short_name = check_short_name(short_name_raw)
    if bot_type != UserProfile.INCOMING_WEBHOOK_BOT:
        service_name = service_name or short_name
    short_name += "-bot"
    full_name = check_full_name(
        full_name_raw=full_name_raw, user_profile=user_profile, realm=user_profile.realm
    )
    try:
        email = Address(username=short_name, domain=user_profile.realm.get_bot_domain()).addr_spec
    except InvalidFakeEmailDomainError:
        raise JsonableError(
            _(
                "Can't create bots until FAKE_EMAIL_DOMAIN is correctly configured.\n"
                "Please contact your server administrator."
            )
        )
    except ValueError:
        raise JsonableError(_("Bad name or username"))
    form = CreateUserForm({"full_name": full_name, "email": email})

    if bot_type == UserProfile.EMBEDDED_BOT:
        if not settings.EMBEDDED_BOTS_ENABLED:
            raise JsonableError(_("Embedded bots are not enabled."))
        if service_name not in [bot.name for bot in EMBEDDED_BOTS]:
            raise JsonableError(_("Invalid embedded bot name."))

    if not form.is_valid():  # nocoverage
        # coverage note: The similar block above covers the most
        # common situation where this might fail, but this case may be
        # still possible with an overly long username.
        raise JsonableError(_("Bad name or username"))
    try:
        get_user_by_delivery_email(email, user_profile.realm)
        raise JsonableError(_("Username already in use"))
    except UserProfile.DoesNotExist:
        pass

    check_bot_name_available(
        realm_id=user_profile.realm_id,
        full_name=full_name,
        is_activation=False,
    )

    check_bot_creation_policy(user_profile, bot_type)
    check_valid_bot_type(user_profile, bot_type)
    check_valid_interface_type(interface_type)

    if len(request.FILES) == 0:
        avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
    elif len(request.FILES) != 1:
        raise JsonableError(_("You may only upload one file at a time"))
    else:
        avatar_source = UserProfile.AVATAR_FROM_USER

    default_sending_stream = None
    if default_sending_stream_name is not None:
        (default_sending_stream, ignored_sub) = access_stream_by_name(
            user_profile, default_sending_stream_name
        )

    default_events_register_stream = None
    if default_events_register_stream_name is not None:
        (default_events_register_stream, ignored_sub) = access_stream_by_name(
            user_profile, default_events_register_stream_name
        )

    if bot_type in (UserProfile.INCOMING_WEBHOOK_BOT, UserProfile.EMBEDDED_BOT) and service_name:
        check_valid_bot_config(bot_type, service_name, config_data)

    bot_profile = do_create_user(
        email=email,
        password=None,
        realm=user_profile.realm,
        full_name=full_name,
        bot_type=bot_type,
        bot_owner=user_profile,
        avatar_source=avatar_source,
        default_sending_stream=default_sending_stream,
        default_events_register_stream=default_events_register_stream,
        default_all_public_streams=default_all_public_streams,
        acting_user=user_profile,
    )
    if len(request.FILES) == 1:
        [user_file] = request.FILES.values()
        assert isinstance(user_file, UploadedFile)
        assert user_file.size is not None
        upload_avatar_image(user_file, user_profile, bot_profile)

    if bot_type in (UserProfile.OUTGOING_WEBHOOK_BOT, UserProfile.EMBEDDED_BOT):
        assert isinstance(service_name, str)
        add_service(
            name=service_name,
            user_profile=bot_profile,
            base_url=payload_url,
            interface=interface_type,
            token=generate_api_key(),
        )

    if bot_type == UserProfile.INCOMING_WEBHOOK_BOT and service_name:
        set_bot_config(bot_profile, "integration_id", service_name)

    if bot_type in (UserProfile.INCOMING_WEBHOOK_BOT, UserProfile.EMBEDDED_BOT):
        for key, value in config_data.items():
            set_bot_config(bot_profile, key, value)

    notify_created_bot(bot_profile)

    api_key = get_api_key(bot_profile)

    json_result = dict(
        user_id=bot_profile.id,
        api_key=api_key,
        avatar_url=avatar_url(bot_profile),
        default_sending_stream=get_stream_name(bot_profile.default_sending_stream),
        default_events_register_stream=get_stream_name(bot_profile.default_events_register_stream),
        default_all_public_streams=bot_profile.default_all_public_streams,
    )
    return json_success(request, data=json_result)


@require_member_or_admin
def get_bots_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True, bot_owner=user_profile)
    bot_profiles = bot_profiles.select_related(
        "default_sending_stream", "default_events_register_stream"
    )
    bot_profiles = bot_profiles.order_by("date_joined")

    def bot_info(bot_profile: UserProfile) -> Dict[str, Any]:
        default_sending_stream = get_stream_name(bot_profile.default_sending_stream)
        default_events_register_stream = get_stream_name(bot_profile.default_events_register_stream)

        # Bots are supposed to have only one API key, at least for now.
        # Therefore we can safely assume that one and only valid API key will be
        # the first one.
        api_key = get_api_key(bot_profile)

        return dict(
            username=bot_profile.email,
            full_name=bot_profile.full_name,
            api_key=api_key,
            avatar_url=avatar_url(bot_profile),
            default_sending_stream=default_sending_stream,
            default_events_register_stream=default_events_register_stream,
            default_all_public_streams=bot_profile.default_all_public_streams,
        )

    return json_success(request, data={"bots": list(map(bot_info, bot_profiles))})


def get_user_data(
    user_profile: UserProfile,
    include_custom_profile_fields: bool,
    client_gravatar: bool,
    target_user: Optional[UserProfile] = None,
) -> Dict[str, Any]:
    """
    The client_gravatar field here is set to True by default assuming that clients
    can compute their own gravatars, which saves bandwidth. This is more important of
    an optimization than it might seem because gravatar URLs contain MD5 hashes that
    compress very poorly compared to other data.
    """
    realm = user_profile.realm

    members = get_users_for_api(
        realm,
        user_profile,
        target_user=target_user,
        client_gravatar=client_gravatar,
        user_avatar_url_field_optional=False,
        include_custom_profile_fields=include_custom_profile_fields,
    )

    if target_user is not None:
        data: Dict[str, Any] = {"user": members[target_user.id]}
    else:
        data = {"members": [members[k] for k in members]}

    return data


@has_request_variables
def get_members_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_id: Optional[int] = None,
    include_custom_profile_fields: bool = REQ(json_validator=check_bool, default=False),
    client_gravatar: bool = REQ(json_validator=check_bool, default=True),
) -> HttpResponse:
    target_user = None
    if user_id is not None:
        target_user = access_user_by_id(
            user_profile, user_id, allow_deactivated=True, allow_bots=True, for_admin=False
        )

    data = get_user_data(user_profile, include_custom_profile_fields, client_gravatar, target_user)

    return json_success(request, data)


@require_realm_admin
@has_request_variables
def create_user_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    email: str = REQ(),
    password: str = REQ(),
    full_name_raw: str = REQ("full_name"),
) -> HttpResponse:
    if not user_profile.can_create_users:
        raise JsonableError(_("User not authorized to create users"))

    full_name = check_full_name(
        full_name_raw=full_name_raw, user_profile=user_profile, realm=user_profile.realm
    )
    form = CreateUserForm({"full_name": full_name, "email": email})
    if not form.is_valid():
        raise JsonableError(_("Bad name or username"))

    # Check that the new user's email address belongs to the admin's realm
    # (Since this is an admin API, we don't require the user to have been
    # invited first.)
    realm = user_profile.realm
    try:
        email_allowed_for_realm(email, user_profile.realm)
    except DomainNotAllowedForRealmError:
        raise JsonableError(
            _("Email '{email}' not allowed in this organization").format(
                email=email,
            )
        )
    except DisposableEmailError:
        raise JsonableError(_("Disposable email addresses are not allowed in this organization"))
    except EmailContainsPlusError:
        raise JsonableError(_("Email addresses containing + are not allowed."))

    try:
        get_user_by_delivery_email(email, user_profile.realm)
        raise JsonableError(_("Email '{email}' already in use").format(email=email))
    except UserProfile.DoesNotExist:
        pass

    if not check_password_strength(password):
        raise JsonableError(str(PASSWORD_TOO_WEAK_ERROR))

    target_user = do_create_user(
        email,
        password,
        realm,
        full_name,
        # Explicitly set tos_version=-1. This means that users
        # created via this mechanism would be prompted to set
        # the email_address_visibility setting on first login.
        # For servers that have configured Terms of Service,
        # users will also be prompted to accept the Terms of
        # Service on first login.
        tos_version=UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN,
        acting_user=user_profile,
    )
    return json_success(request, data={"user_id": target_user.id})


def get_profile_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    raw_user_data = get_users_for_api(
        user_profile.realm,
        user_profile,
        target_user=user_profile,
        client_gravatar=False,
        user_avatar_url_field_optional=False,
    )
    result: APIUserDict = raw_user_data[user_profile.id]

    result["max_message_id"] = max_message_id_for_user(user_profile)

    return json_success(request, data=result)


@has_request_variables
def get_subscription_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_id: int = REQ(json_validator=check_int, path_only=True),
    stream_id: int = REQ(json_validator=check_int, path_only=True),
) -> HttpResponse:
    target_user = access_user_by_id(user_profile, user_id, for_admin=False)
    (stream, sub) = access_stream_by_id(user_profile, stream_id, allow_realm_admin=True)

    subscription_status = {"is_subscribed": subscribed_to_stream(target_user, stream_id)}

    return json_success(request, data=subscription_status)


@has_request_variables
def get_user_by_email(
    request: HttpRequest,
    user_profile: UserProfile,
    email: str,
    include_custom_profile_fields: bool = REQ(json_validator=check_bool, default=False),
    client_gravatar: bool = REQ(json_validator=check_bool, default=True),
) -> HttpResponse:
    target_user = access_user_by_email(
        user_profile, email, allow_deactivated=True, allow_bots=True, for_admin=False
    )

    data = get_user_data(user_profile, include_custom_profile_fields, client_gravatar, target_user)
    return json_success(request, data)

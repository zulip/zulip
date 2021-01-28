from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from zerver.decorator import require_member_or_admin, require_realm_admin
from zerver.forms import PASSWORD_TOO_WEAK_ERROR, CreateUserForm
from zerver.lib.actions import (
    check_change_bot_full_name,
    check_change_full_name,
    check_remove_custom_profile_field_value,
    do_change_avatar_fields,
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
    do_change_user_role,
    do_create_user,
    do_deactivate_user,
    do_reactivate_user,
    do_regenerate_api_key,
    do_update_bot_config_data,
    do_update_outgoing_webhook_service,
    do_update_user_custom_profile_data_if_changed,
    notify_created_bot,
)
from zerver.lib.avatar import avatar_url, get_gravatar_url
from zerver.lib.bot_config import set_bot_config
from zerver.lib.email_validation import email_allowed_for_realm
from zerver.lib.exceptions import CannotDeactivateLastUserError, OrganizationOwnerRequired
from zerver.lib.integrations import EMBEDDED_BOTS
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.streams import access_stream_by_id, access_stream_by_name, subscribed_to_stream
from zerver.lib.types import Validator
from zerver.lib.upload import upload_avatar_image
from zerver.lib.url_encoding import add_query_arg_to_redirect_url
from zerver.lib.users import (
    access_bot_by_id,
    access_user_by_id,
    add_service,
    check_bot_creation_policy,
    check_bot_name_available,
    check_full_name,
    check_short_name,
    check_valid_bot_config,
    check_valid_bot_type,
    check_valid_interface_type,
    get_api_key,
    get_raw_user_data,
    validate_user_custom_profile_data,
)
from zerver.lib.utils import generate_api_key
from zerver.lib.validator import (
    check_bool,
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
from zerver.models import (
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    InvalidFakeEmailDomain,
    Message,
    Realm,
    Service,
    Stream,
    UserProfile,
    get_user_by_delivery_email,
    get_user_by_id_in_realm_including_cross_realm,
    get_user_including_cross_realm,
    get_user_profile_by_id_in_realm,
)
from zproject.backends import check_password_strength


def check_last_owner(user_profile: UserProfile) -> bool:
    owners = set(user_profile.realm.get_human_owner_users())
    return user_profile.is_realm_owner and not user_profile.is_bot and len(owners) == 1

def deactivate_user_backend(request: HttpRequest, user_profile: UserProfile,
                            user_id: int) -> HttpResponse:
    target = access_user_by_id(user_profile, user_id, for_admin=True)
    if target.is_realm_owner and not user_profile.is_realm_owner:
        raise OrganizationOwnerRequired()
    if check_last_owner(target):
        return json_error(_('Cannot deactivate the only organization owner'))
    return _deactivate_user_profile_backend(request, user_profile, target)

def deactivate_user_own_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if UserProfile.objects.filter(realm=user_profile.realm, is_active=True).count() == 1:
        raise CannotDeactivateLastUserError(is_last_owner=False)
    if user_profile.is_realm_owner and check_last_owner(user_profile):
        raise CannotDeactivateLastUserError(is_last_owner=True)

    do_deactivate_user(user_profile, acting_user=user_profile)
    return json_success()

def deactivate_bot_backend(request: HttpRequest, user_profile: UserProfile,
                           bot_id: int) -> HttpResponse:
    target = access_bot_by_id(user_profile, bot_id)
    return _deactivate_user_profile_backend(request, user_profile, target)

def _deactivate_user_profile_backend(request: HttpRequest, user_profile: UserProfile,
                                     target: UserProfile) -> HttpResponse:
    do_deactivate_user(target, acting_user=user_profile)
    return json_success()

def reactivate_user_backend(request: HttpRequest, user_profile: UserProfile,
                            user_id: int) -> HttpResponse:
    target = access_user_by_id(user_profile, user_id,
                               allow_deactivated=True, allow_bots=True, for_admin=True)
    if target.is_bot:
        assert target.bot_type is not None
        check_bot_creation_policy(user_profile, target.bot_type)
    do_reactivate_user(target, acting_user=user_profile)
    return json_success()

check_profile_data: Validator[List[Dict[str, Optional[Union[int, str, List[int]]]]]] = check_list(
    check_dict_only([
        ('id', check_int),
        ('value', check_none_or(
            check_union([check_int, check_string, check_list(check_int)]),
        )),
    ]),
)

@has_request_variables
def update_user_backend(
    request: HttpRequest, user_profile: UserProfile, user_id: int,
    full_name: Optional[str] = REQ(default=None, validator=check_string),
    role: Optional[int] = REQ(default=None, validator=check_int_in(
        UserProfile.ROLE_TYPES,
    )),
    profile_data: Optional[List[Dict[str, Optional[Union[int, str, List[int]]]]]] = REQ(
        default=None, validator=check_profile_data,
    ),
) -> HttpResponse:
    target = access_user_by_id(user_profile, user_id,
                               allow_deactivated=True, allow_bots=True, for_admin=True)

    if role is not None and target.role != role:
        # Require that the current user has permissions to
        # grant/remove the role in question.  access_user_by_id has
        # already verified we're an administrator; here we enforce
        # that only owners can toggle the is_realm_owner flag.
        if UserProfile.ROLE_REALM_OWNER in [role, target.role] and not user_profile.is_realm_owner:
            raise OrganizationOwnerRequired()

        if target.role == UserProfile.ROLE_REALM_OWNER and check_last_owner(user_profile):
            return json_error(_('The owner permission cannot be removed from the only organization owner.'))
        do_change_user_role(target, role, acting_user=user_profile)

    if (full_name is not None and target.full_name != full_name and
            full_name.strip() != ""):
        # We don't respect `name_changes_disabled` here because the request
        # is on behalf of the administrator.
        check_change_full_name(target, full_name, user_profile)

    if profile_data is not None:
        clean_profile_data = []
        for entry in profile_data:
            assert isinstance(entry["id"], int)
            if entry["value"] is None or not entry["value"]:
                field_id = entry["id"]
                check_remove_custom_profile_field_value(target, field_id)
            else:
                clean_profile_data.append({
                    "id": entry["id"],
                    "value": entry["value"],
                })
        validate_user_custom_profile_data(target.realm.id, clean_profile_data)
        do_update_user_custom_profile_data_if_changed(target, clean_profile_data)

    return json_success()

def avatar(request: HttpRequest, user_profile: UserProfile,
           email_or_id: str, medium: bool=False) -> HttpResponse:
    """Accepts an email address or user ID and returns the avatar"""
    is_email = False
    try:
        int(email_or_id)
    except ValueError:
        is_email = True

    try:
        realm = user_profile.realm
        if is_email:
            avatar_user_profile = get_user_including_cross_realm(email_or_id, realm)
        else:
            avatar_user_profile = get_user_by_id_in_realm_including_cross_realm(int(email_or_id), realm)
        # If there is a valid user account passed in, use its avatar
        url = avatar_url(avatar_user_profile, medium=medium)
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
    url = add_query_arg_to_redirect_url(url, request.META['QUERY_STRING'])
    return redirect(url)

def get_stream_name(stream: Optional[Stream]) -> Optional[str]:
    if stream:
        return stream.name
    return None

@require_member_or_admin
@has_request_variables
def patch_bot_backend(
        request: HttpRequest, user_profile: UserProfile, bot_id: int,
        full_name: Optional[str]=REQ(default=None),
        bot_owner_id: Optional[int]=REQ(validator=check_int, default=None),
        config_data: Optional[Dict[str, str]]=REQ(default=None,
                                                  validator=check_dict(value_validator=check_string)),
        service_payload_url: Optional[str]=REQ(validator=check_url, default=None),
        service_interface: int=REQ(validator=check_int, default=1),
        default_sending_stream: Optional[str]=REQ(default=None),
        default_events_register_stream: Optional[str]=REQ(default=None),
        default_all_public_streams: Optional[bool]=REQ(default=None, validator=check_bool),
) -> HttpResponse:
    bot = access_bot_by_id(user_profile, bot_id)

    if full_name is not None:
        check_change_bot_full_name(bot, full_name, user_profile)
    if bot_owner_id is not None:
        try:
            owner = get_user_profile_by_id_in_realm(bot_owner_id, user_profile.realm)
        except UserProfile.DoesNotExist:
            return json_error(_('Failed to change owner, no such user'))
        if not owner.is_active:
            return json_error(_('Failed to change owner, user is deactivated'))
        if owner.is_bot:
            return json_error(_("Failed to change owner, bots can't own other bots"))

        previous_owner = bot.bot_owner
        if previous_owner != owner:
            do_change_bot_owner(bot, owner, user_profile)

    if default_sending_stream is not None:
        if default_sending_stream == "":
            stream: Optional[Stream] = None
        else:
            (stream, sub) = access_stream_by_name(
                user_profile, default_sending_stream)
        do_change_default_sending_stream(bot, stream, acting_user=user_profile)
    if default_events_register_stream is not None:
        if default_events_register_stream == "":
            stream = None
        else:
            (stream, sub) = access_stream_by_name(
                user_profile, default_events_register_stream)
        do_change_default_events_register_stream(bot, stream, acting_user=user_profile)
    if default_all_public_streams is not None:
        do_change_default_all_public_streams(bot, default_all_public_streams, acting_user=user_profile)

    if service_payload_url is not None:
        check_valid_interface_type(service_interface)
        assert service_interface is not None
        do_update_outgoing_webhook_service(bot, service_interface, service_payload_url)

    if config_data is not None:
        do_update_bot_config_data(bot, config_data)

    if len(request.FILES) == 0:
        pass
    elif len(request.FILES) == 1:
        user_file = list(request.FILES.values())[0]
        upload_avatar_image(user_file, user_profile, bot)
        avatar_source = UserProfile.AVATAR_FROM_USER
        do_change_avatar_fields(bot, avatar_source, acting_user=user_profile)
    else:
        return json_error(_("You may only upload one file at a time"))

    json_result = dict(
        full_name=bot.full_name,
        avatar_url=avatar_url(bot),
        service_interface = service_interface,
        service_payload_url = service_payload_url,
        config_data = config_data,
        default_sending_stream=get_stream_name(bot.default_sending_stream),
        default_events_register_stream=get_stream_name(bot.default_events_register_stream),
        default_all_public_streams=bot.default_all_public_streams,
    )

    # Don't include the bot owner in case it is not set.
    # Default bots have no owner.
    if bot.bot_owner is not None:
        json_result['bot_owner'] = bot.bot_owner.email

    return json_success(json_result)

@require_member_or_admin
@has_request_variables
def regenerate_bot_api_key(request: HttpRequest, user_profile: UserProfile, bot_id: int) -> HttpResponse:
    bot = access_bot_by_id(user_profile, bot_id)

    new_api_key = do_regenerate_api_key(bot, user_profile)
    json_result = dict(
        api_key=new_api_key,
    )
    return json_success(json_result)

@require_member_or_admin
@has_request_variables
def add_bot_backend(
        request: HttpRequest, user_profile: UserProfile,
        full_name_raw: str=REQ("full_name"), short_name_raw: str=REQ("short_name"),
        bot_type: int=REQ(validator=check_int, default=UserProfile.DEFAULT_BOT),
        payload_url: str=REQ(validator=check_url, default=""),
        service_name: Optional[str]=REQ(default=None),
        config_data: Dict[str, str]=REQ(default={},
                                        validator=check_dict(value_validator=check_string)),
        interface_type: int=REQ(validator=check_int, default=Service.GENERIC),
        default_sending_stream_name: Optional[str]=REQ('default_sending_stream', default=None),
        default_events_register_stream_name: Optional[str]=REQ('default_events_register_stream',
                                                               default=None),
        default_all_public_streams: Optional[bool]=REQ(validator=check_bool, default=None),
) -> HttpResponse:
    short_name = check_short_name(short_name_raw)
    if bot_type != UserProfile.INCOMING_WEBHOOK_BOT:
        service_name = service_name or short_name
    short_name += "-bot"
    full_name = check_full_name(full_name_raw)
    try:
        email = f'{short_name}@{user_profile.realm.get_bot_domain()}'
    except InvalidFakeEmailDomain:
        return json_error(_("Can't create bots until FAKE_EMAIL_DOMAIN is correctly configured.\n"
                            "Please contact your server administrator."))
    form = CreateUserForm({'full_name': full_name, 'email': email})

    if bot_type == UserProfile.EMBEDDED_BOT:
        if not settings.EMBEDDED_BOTS_ENABLED:
            return json_error(_("Embedded bots are not enabled."))
        if service_name not in [bot.name for bot in EMBEDDED_BOTS]:
            return json_error(_("Invalid embedded bot name."))

    if not form.is_valid():
        # We validate client-side as well
        return json_error(_('Bad name or username'))
    try:
        get_user_by_delivery_email(email, user_profile.realm)
        return json_error(_("Username already in use"))
    except UserProfile.DoesNotExist:
        pass

    check_bot_name_available(
        realm_id=user_profile.realm_id,
        full_name=full_name,
    )

    check_bot_creation_policy(user_profile, bot_type)
    check_valid_bot_type(user_profile, bot_type)
    check_valid_interface_type(interface_type)

    if len(request.FILES) == 0:
        avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
    elif len(request.FILES) != 1:
        return json_error(_("You may only upload one file at a time"))
    else:
        avatar_source = UserProfile.AVATAR_FROM_USER

    default_sending_stream = None
    if default_sending_stream_name is not None:
        (default_sending_stream, ignored_sub) = access_stream_by_name(
            user_profile, default_sending_stream_name)

    default_events_register_stream = None
    if default_events_register_stream_name is not None:
        (default_events_register_stream, ignored_sub) = access_stream_by_name(
            user_profile, default_events_register_stream_name)

    if bot_type in (UserProfile.INCOMING_WEBHOOK_BOT, UserProfile.EMBEDDED_BOT) and service_name:
        check_valid_bot_config(bot_type, service_name, config_data)

    bot_profile = do_create_user(email=email, password=None,
                                 realm=user_profile.realm, full_name=full_name,
                                 bot_type=bot_type,
                                 bot_owner=user_profile,
                                 avatar_source=avatar_source,
                                 default_sending_stream=default_sending_stream,
                                 default_events_register_stream=default_events_register_stream,
                                 default_all_public_streams=default_all_public_streams,
                                 acting_user=user_profile)
    if len(request.FILES) == 1:
        user_file = list(request.FILES.values())[0]
        upload_avatar_image(user_file, user_profile, bot_profile)

    if bot_type in (UserProfile.OUTGOING_WEBHOOK_BOT, UserProfile.EMBEDDED_BOT):
        assert(isinstance(service_name, str))
        add_service(name=service_name,
                    user_profile=bot_profile,
                    base_url=payload_url,
                    interface=interface_type,
                    token=generate_api_key())

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
    return json_success(json_result)

@require_member_or_admin
def get_bots_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                              bot_owner=user_profile)
    bot_profiles = bot_profiles.select_related('default_sending_stream', 'default_events_register_stream')
    bot_profiles = bot_profiles.order_by('date_joined')

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

    return json_success({'bots': list(map(bot_info, bot_profiles))})

@has_request_variables
def get_members_backend(request: HttpRequest, user_profile: UserProfile, user_id: Optional[int]=None,
                        include_custom_profile_fields: bool=REQ(validator=check_bool,
                                                                default=False),
                        client_gravatar: bool=REQ(validator=check_bool, default=False),
                        ) -> HttpResponse:
    '''
    The client_gravatar field here is set to True if clients can compute
    their own gravatars, which saves us bandwidth.  We want to eventually
    make this the default behavior, but we have old clients that expect
    the server to compute this for us.
    '''
    realm = user_profile.realm
    if realm.email_address_visibility != Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
        # If email addresses are only available to administrators,
        # clients cannot compute gravatars, so we force-set it to false.
        client_gravatar = False
    target_user = None
    if user_id is not None:
        target_user = access_user_by_id(user_profile, user_id, allow_deactivated=True,
                                        allow_bots=True, for_admin=False)

    members = get_raw_user_data(realm, user_profile, target_user=target_user,
                                client_gravatar=client_gravatar,
                                user_avatar_url_field_optional=False,
                                include_custom_profile_fields=include_custom_profile_fields)

    if target_user is not None:
        data: Dict[str, Any] = {"user": members[target_user.id]}
    else:
        data = {"members": [members[k] for k in members]}

    return json_success(data)

@require_realm_admin
@has_request_variables
def create_user_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    email: str=REQ(),
    password: str=REQ(),
    full_name_raw: str=REQ("full_name"),
) -> HttpResponse:
    if not user_profile.can_create_users:
        return json_error(_("User not authorized for this query"))

    full_name = check_full_name(full_name_raw)
    form = CreateUserForm({'full_name': full_name, 'email': email})
    if not form.is_valid():
        return json_error(_('Bad name or username'))

    # Check that the new user's email address belongs to the admin's realm
    # (Since this is an admin API, we don't require the user to have been
    # invited first.)
    realm = user_profile.realm
    try:
        email_allowed_for_realm(email, user_profile.realm)
    except DomainNotAllowedForRealmError:
        return json_error(_("Email '{email}' not allowed in this organization").format(
            email=email,
        ))
    except DisposableEmailError:
        return json_error(_("Disposable email addresses are not allowed in this organization"))
    except EmailContainsPlusError:
        return json_error(_("Email addresses containing + are not allowed."))

    try:
        get_user_by_delivery_email(email, user_profile.realm)
        return json_error(_("Email '{}' already in use").format(email))
    except UserProfile.DoesNotExist:
        pass

    if not check_password_strength(password):
        return json_error(PASSWORD_TOO_WEAK_ERROR)

    target_user = do_create_user(email, password, realm, full_name, acting_user=user_profile)
    return json_success({'user_id': target_user.id})

def get_profile_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    raw_user_data = get_raw_user_data(user_profile.realm, user_profile,
                                      target_user=user_profile,
                                      client_gravatar=False,
                                      user_avatar_url_field_optional=False)
    result: Dict[str, Any] = raw_user_data[user_profile.id]

    result['max_message_id'] = -1

    messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
    if messages:
        result['max_message_id'] = messages[0].id

    return json_success(result)

@has_request_variables
def get_subscription_backend(request: HttpRequest, user_profile: UserProfile,
                             user_id: int=REQ(validator=check_int, path_only=True),
                             stream_id: int=REQ(validator=check_int, path_only=True),
                             ) -> HttpResponse:
    target_user = access_user_by_id(user_profile, user_id, for_admin=False)
    (stream, sub) = access_stream_by_id(user_profile, stream_id)

    subscription_status = {'is_subscribed': subscribed_to_stream(target_user, stream_id)}

    return json_success(subscription_status)

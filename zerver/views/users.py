from __future__ import absolute_import
from typing import Callable, Text, Union, Optional, Dict, Any, List, Tuple

import os
import simplejson as json

from django.http import HttpRequest, HttpResponse

from django.utils.translation import ugettext as _
from django.shortcuts import redirect, render
from django.conf import settings
from six.moves import map

from zerver.decorator import has_request_variables, REQ, JsonableError, \
    require_realm_admin, zulip_login_required
from zerver.forms import CreateUserForm
from zerver.lib.actions import do_change_avatar_fields, do_change_bot_owner, \
    do_change_is_admin, do_change_default_all_public_streams, \
    do_change_default_events_register_stream, do_change_default_sending_stream, \
    do_create_user, do_deactivate_user, do_reactivate_user, do_regenerate_api_key
from zerver.lib.avatar import avatar_url, get_gravatar_url
from zerver.lib.response import json_error, json_success
from zerver.lib.streams import access_stream_by_name
from zerver.lib.upload import upload_avatar_image
from zerver.lib.validator import check_bool, check_string, check_int, check_url
from zerver.lib.users import check_valid_bot_type, check_change_full_name, \
    check_full_name, check_short_name, check_valid_interface_type
from zerver.lib.utils import generate_random_token
from zerver.models import UserProfile, Stream, Message, email_allowed_for_realm, \
    get_user_profile_by_id, get_user, Service, get_user_including_cross_realm
from zerver.lib.create_user import random_api_key


def deactivate_user_backend(request, user_profile, email):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    try:
        target = get_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        return json_error(_('No such user'))
    if target.is_bot:
        return json_error(_('No such user'))
    if check_last_admin(target):
        return json_error(_('Cannot deactivate the only organization administrator'))
    return _deactivate_user_profile_backend(request, user_profile, target)

def deactivate_user_own_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse

    if user_profile.is_realm_admin and check_last_admin(user_profile):
        return json_error(_('Cannot deactivate the only organization administrator'))
    do_deactivate_user(user_profile, acting_user=user_profile)
    return json_success()

def check_last_admin(user_profile):
    # type: (UserProfile) -> bool
    admins = set(user_profile.realm.get_admin_users())
    return user_profile.is_realm_admin and len(admins) == 1

def deactivate_bot_backend(request, user_profile, email):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    try:
        target = get_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        return json_error(_('No such bot'))
    if not target.is_bot:
        return json_error(_('No such bot'))
    return _deactivate_user_profile_backend(request, user_profile, target)

def _deactivate_user_profile_backend(request, user_profile, target):
    # type: (HttpRequest, UserProfile, UserProfile) -> HttpResponse
    if not user_profile.can_admin_user(target):
        return json_error(_('Insufficient permission'))

    do_deactivate_user(target, acting_user=user_profile)
    return json_success()

def reactivate_user_backend(request, user_profile, email):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    try:
        target = get_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        return json_error(_('No such user'))

    if not user_profile.can_admin_user(target):
        return json_error(_('Insufficient permission'))

    do_reactivate_user(target, acting_user=user_profile)
    return json_success()

@has_request_variables
def update_user_backend(request, user_profile, email,
                        full_name=REQ(default="", validator=check_string),
                        is_admin=REQ(default=None, validator=check_bool)):
    # type: (HttpRequest, UserProfile, Text, Optional[Text], Optional[bool]) -> HttpResponse
    try:
        target = get_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        return json_error(_('No such user'))

    if not user_profile.can_admin_user(target):
        return json_error(_('Insufficient permission'))

    if is_admin is not None:
        if not is_admin and check_last_admin(user_profile):
            return json_error(_('Cannot remove the only organization administrator'))
        do_change_is_admin(target, is_admin)

    if (full_name is not None and target.full_name != full_name and
            full_name.strip() != ""):
        # We don't respect `name_changes_disabled` here because the request
        # is on behalf of the administrator.
        check_change_full_name(target, full_name, user_profile)

    return json_success()

# TODO: Since eventually we want to support using the same email with
# different organizations, we'll eventually want this to be a
# logged-in endpoint so that we can access the realm_id.
@zulip_login_required
def avatar(request, email_or_id, medium=False):
    # type: (HttpRequest, str, bool) -> HttpResponse
    """Accepts an email address or user ID and returns the avatar"""
    is_email = False
    try:
        int(email_or_id)
    except ValueError:
        is_email = True

    try:
        if is_email:
            realm = request.user.realm
            user_profile = get_user_including_cross_realm(email_or_id, realm)
        else:
            user_profile = get_user_profile_by_id(email_or_id)
        # If there is a valid user account passed in, use its avatar
        url = avatar_url(user_profile, medium=medium)
    except UserProfile.DoesNotExist:
        # If there is no such user, treat it as a new gravatar
        email = email_or_id
        avatar_version = 1
        url = get_gravatar_url(email, avatar_version, medium)

    # We can rely on the url already having query parameters. Because
    # our templates depend on being able to use the ampersand to
    # add query parameters to our url, get_avatar_url does '?x=x'
    # hacks to prevent us from having to jump through decode/encode hoops.
    assert '?' in url
    url += '&' + request.META['QUERY_STRING']
    return redirect(url)

def get_stream_name(stream):
    # type: (Optional[Stream]) -> Optional[Text]
    if stream:
        return stream.name
    return None

@has_request_variables
def patch_bot_backend(request, user_profile, email,
                      full_name=REQ(default=None),
                      bot_owner=REQ(default=None),
                      default_sending_stream=REQ(default=None),
                      default_events_register_stream=REQ(default=None),
                      default_all_public_streams=REQ(default=None, validator=check_bool)):
    # type: (HttpRequest, UserProfile, Text, Optional[Text], Optional[Text], Optional[Text], Optional[Text], Optional[bool]) -> HttpResponse
    try:
        bot = get_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        return json_error(_('No such user'))

    if not user_profile.can_admin_user(bot):
        return json_error(_('Insufficient permission'))

    if full_name is not None:
        check_change_full_name(bot, full_name, user_profile)
    if bot_owner is not None:
        owner = get_user(bot_owner, user_profile.realm)
        do_change_bot_owner(bot, owner, user_profile)
    if default_sending_stream is not None:
        if default_sending_stream == "":
            stream = None  # type: Optional[Stream]
        else:
            (stream, recipient, sub) = access_stream_by_name(
                user_profile, default_sending_stream)
        do_change_default_sending_stream(bot, stream)
    if default_events_register_stream is not None:
        if default_events_register_stream == "":
            stream = None
        else:
            (stream, recipient, sub) = access_stream_by_name(
                user_profile, default_events_register_stream)
        do_change_default_events_register_stream(bot, stream)
    if default_all_public_streams is not None:
        do_change_default_all_public_streams(bot, default_all_public_streams)

    if len(request.FILES) == 0:
        pass
    elif len(request.FILES) == 1:
        user_file = list(request.FILES.values())[0]
        upload_avatar_image(user_file, user_profile, bot)
        avatar_source = UserProfile.AVATAR_FROM_USER
        do_change_avatar_fields(bot, avatar_source)
    else:
        return json_error(_("You may only upload one file at a time"))

    json_result = dict(
        full_name=bot.full_name,
        avatar_url=avatar_url(bot),
        default_sending_stream=get_stream_name(bot.default_sending_stream),
        default_events_register_stream=get_stream_name(bot.default_events_register_stream),
        default_all_public_streams=bot.default_all_public_streams,
    )

    # Don't include the bot owner in case it is not set.
    # Default bots have no owner.
    if bot.bot_owner is not None:
        json_result['bot_owner'] = bot.bot_owner.email

    return json_success(json_result)

@has_request_variables
def regenerate_bot_api_key(request, user_profile, email):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    try:
        bot = get_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        return json_error(_('No such user'))

    if not user_profile.can_admin_user(bot):
        return json_error(_('Insufficient permission'))

    do_regenerate_api_key(bot, user_profile)
    json_result = dict(
        api_key = bot.api_key
    )
    return json_success(json_result)

def add_outgoing_webhook_service(name, user_profile, base_url, interface, token):
    # type: (Text, UserProfile, Text, int, Text) -> None
    Service.objects.create(name=name,
                           user_profile=user_profile,
                           base_url=base_url,
                           interface=interface,
                           token=token)

@has_request_variables
def add_bot_backend(request, user_profile, full_name_raw=REQ("full_name"), short_name_raw=REQ("short_name"),
                    bot_type=REQ(validator=check_int, default=UserProfile.DEFAULT_BOT),
                    payload_url=REQ(validator=check_url, default=None),
                    interface_type=REQ(validator=check_int, default=Service.GENERIC),
                    default_sending_stream_name=REQ('default_sending_stream', default=None),
                    default_events_register_stream_name=REQ('default_events_register_stream', default=None),
                    default_all_public_streams=REQ(validator=check_bool, default=None)):
    # type: (HttpRequest, UserProfile, Text, Text, int, Optional[Text], int, Optional[Text], Optional[Text], Optional[bool]) -> HttpResponse
    short_name = check_short_name(short_name_raw)
    service_name = short_name
    short_name += "-bot"
    full_name = check_full_name(full_name_raw)
    email = '%s@%s' % (short_name, user_profile.realm.get_bot_domain())
    form = CreateUserForm({'full_name': full_name, 'email': email})
    if not form.is_valid():
        # We validate client-side as well
        return json_error(_('Bad name or username'))
    try:
        get_user(email, user_profile.realm)
        return json_error(_("Username already in use"))
    except UserProfile.DoesNotExist:
        pass
    check_valid_bot_type(bot_type)
    check_valid_interface_type(interface_type)

    if len(request.FILES) == 0:
        avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
    elif len(request.FILES) != 1:
        return json_error(_("You may only upload one file at a time"))
    else:
        avatar_source = UserProfile.AVATAR_FROM_USER

    default_sending_stream = None
    if default_sending_stream_name is not None:
        (default_sending_stream, ignored_rec, ignored_sub) = access_stream_by_name(
            user_profile, default_sending_stream_name)

    default_events_register_stream = None
    if default_events_register_stream_name is not None:
        (default_events_register_stream, ignored_rec, ignored_sub) = access_stream_by_name(
            user_profile, default_events_register_stream_name)

    bot_profile = do_create_user(email=email, password='',
                                 realm=user_profile.realm, full_name=full_name,
                                 short_name=short_name, active=True,
                                 bot_type=bot_type,
                                 bot_owner=user_profile,
                                 avatar_source=avatar_source,
                                 default_sending_stream=default_sending_stream,
                                 default_events_register_stream=default_events_register_stream,
                                 default_all_public_streams=default_all_public_streams)
    if len(request.FILES) == 1:
        user_file = list(request.FILES.values())[0]
        upload_avatar_image(user_file, user_profile, bot_profile)

    if bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
        add_outgoing_webhook_service(name=service_name,
                                     user_profile=bot_profile,
                                     base_url=payload_url,
                                     interface=interface_type,
                                     token=random_api_key())

    json_result = dict(
        api_key=bot_profile.api_key,
        avatar_url=avatar_url(bot_profile),
        default_sending_stream=get_stream_name(bot_profile.default_sending_stream),
        default_events_register_stream=get_stream_name(bot_profile.default_events_register_stream),
        default_all_public_streams=bot_profile.default_all_public_streams,
    )
    return json_success(json_result)

def get_bots_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                              bot_owner=user_profile)
    bot_profiles = bot_profiles.select_related('default_sending_stream', 'default_events_register_stream')
    bot_profiles = bot_profiles.order_by('date_joined')

    def bot_info(bot_profile):
        # type: (UserProfile) -> Dict[str, Any]
        default_sending_stream = get_stream_name(bot_profile.default_sending_stream)
        default_events_register_stream = get_stream_name(bot_profile.default_events_register_stream)

        return dict(
            username=bot_profile.email,
            full_name=bot_profile.full_name,
            api_key=bot_profile.api_key,
            avatar_url=avatar_url(bot_profile),
            default_sending_stream=default_sending_stream,
            default_events_register_stream=default_events_register_stream,
            default_all_public_streams=bot_profile.default_all_public_streams,
        )

    return json_success({'bots': list(map(bot_info, bot_profiles))})

def get_members_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    realm = user_profile.realm
    admins = set(user_profile.realm.get_admin_users())
    members = []
    for profile in UserProfile.objects.select_related().filter(realm=realm):
        member = {"full_name": profile.full_name,
                  "is_bot": profile.is_bot,
                  "is_active": profile.is_active,
                  "is_admin": (profile in admins),
                  "bot_type": profile.bot_type,
                  "email": profile.email,
                  "user_id": profile.id,
                  "avatar_url": avatar_url(profile)}
        if profile.is_bot and profile.bot_owner is not None:
            member["bot_owner"] = profile.bot_owner.email
        members.append(member)
    return json_success({'members': members})

@require_realm_admin
@has_request_variables
def create_user_backend(request, user_profile, email=REQ(), password=REQ(),
                        full_name_raw=REQ("full_name"), short_name=REQ()):
    # type: (HttpRequest, UserProfile, Text, Text, Text, Text) -> HttpResponse
    full_name = check_full_name(full_name_raw)
    form = CreateUserForm({'full_name': full_name, 'email': email})
    if not form.is_valid():
        return json_error(_('Bad name or username'))

    # Check that the new user's email address belongs to the admin's realm
    # (Since this is an admin API, we don't require the user to have been
    # invited first.)
    realm = user_profile.realm
    if not email_allowed_for_realm(email, user_profile.realm):
        return json_error(_("Email '%(email)s' not allowed for realm '%(realm)s'") %
                          {'email': email, 'realm': realm.string_id})

    try:
        get_user(email, user_profile.realm)
        return json_error(_("Email '%s' already in use") % (email,))
    except UserProfile.DoesNotExist:
        pass

    do_create_user(email, password, realm, full_name, short_name)
    return json_success()

def generate_client_id():
    # type: () -> str
    return generate_random_token(32)

def get_profile_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    result = dict(pointer        = user_profile.pointer,
                  client_id      = generate_client_id(),
                  max_message_id = -1,
                  user_id        = user_profile.id,
                  full_name      = user_profile.full_name,
                  email          = user_profile.email,
                  is_bot         = user_profile.is_bot,
                  is_admin       = user_profile.is_realm_admin,
                  short_name     = user_profile.short_name)

    messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
    if messages:
        result['max_message_id'] = messages[0].id

    return json_success(result)

def about_view(request):
    # type: (HttpRequest) -> HttpResponse

    with open(settings.CONTRIBUTORS_DATA) as f:
        data = json.load(f)

    return render(
        request,
        'zerver/about.html',
        context=data,
    )

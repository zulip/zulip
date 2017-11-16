from typing import List, Text

from django.utils.translation import ugettext as _

from zerver.lib.request import JsonableError
from zerver.models import UserProfile, Service, Realm, \
    get_user_profile_by_id

def check_full_name(full_name_raw):
    # type: (Text) -> Text
    full_name = full_name_raw.strip()
    if len(full_name) > UserProfile.MAX_NAME_LENGTH:
        raise JsonableError(_("Name too long!"))
    if len(full_name) < UserProfile.MIN_NAME_LENGTH:
        raise JsonableError(_("Name too short!"))
    if list(set(full_name).intersection(UserProfile.NAME_INVALID_CHARS)):
        raise JsonableError(_("Invalid characters in name!"))
    return full_name

def check_short_name(short_name_raw):
    # type: (Text) -> Text
    short_name = short_name_raw.strip()
    if len(short_name) == 0:
        raise JsonableError(_("Bad name or username"))
    return short_name

def check_valid_bot_type(bot_type):
    # type: (int) -> None
    if bot_type not in UserProfile.ALLOWED_BOT_TYPES:
        raise JsonableError(_('Invalid bot type'))

def check_valid_interface_type(interface_type):
    # type: (int) -> None
    if interface_type not in Service.ALLOWED_INTERFACE_TYPES:
        raise JsonableError(_('Invalid interface type'))

def user_ids_to_users(user_ids: List[int], realm: Realm) -> List[UserProfile]:
    # TODO: Change this to do a single bulk query with
    # generic_bulk_cached_fetch; it'll be faster.
    #
    # TODO: Consider adding a flag to control whether deactivated
    # users should be included.
    user_profiles = []
    for user_id in user_ids:
        try:
            user_profile = get_user_profile_by_id(user_id)
        except UserProfile.DoesNotExist:
            raise JsonableError(_("Invalid user ID: %s" % (user_id,)))
        if user_profile.realm != realm:
            raise JsonableError(_("Invalid user ID: %s" % (user_id,)))
        user_profiles.append(user_profile)
    return user_profiles

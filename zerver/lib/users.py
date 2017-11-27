from typing import Dict, List, Optional, Text

from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _

from zerver.lib.cache import generic_bulk_cached_fetch, user_profile_cache_key_id
from zerver.lib.request import JsonableError
from zerver.models import UserProfile, Service, Realm, \
    get_user_profile_by_id

def check_full_name(full_name_raw: Text) -> Text:
    full_name = full_name_raw.strip()
    if len(full_name) > UserProfile.MAX_NAME_LENGTH:
        raise JsonableError(_("Name too long!"))
    if len(full_name) < UserProfile.MIN_NAME_LENGTH:
        raise JsonableError(_("Name too short!"))
    if list(set(full_name).intersection(UserProfile.NAME_INVALID_CHARS)):
        raise JsonableError(_("Invalid characters in name!"))
    return full_name

def check_short_name(short_name_raw: Text) -> Text:
    short_name = short_name_raw.strip()
    if len(short_name) == 0:
        raise JsonableError(_("Bad name or username"))
    return short_name

def check_valid_bot_type(bot_type: int) -> None:
    if bot_type not in UserProfile.ALLOWED_BOT_TYPES:
        raise JsonableError(_('Invalid bot type'))

def check_valid_interface_type(interface_type: int) -> None:
    if interface_type not in Service.ALLOWED_INTERFACE_TYPES:
        raise JsonableError(_('Invalid interface type'))

def bulk_get_users(emails: List[str], realm: Optional[Realm],
                   base_query: 'QuerySet[UserProfile]'=None) -> Dict[str, UserProfile]:
    if base_query is None:
        assert realm is not None
        base_query = UserProfile.objects.filter(realm=realm, is_active=True)
        realm_id = realm.id
    else:
        # WARNING: Currently, this code path only really supports one
        # version of `base_query` being used (because otherwise,
        # they'll share the cache, which can screw up the filtering).
        # If you're using this flow, you'll need to re-do any filters
        # in base_query in the code itself; base_query is just a perf
        # optimization.
        realm_id = 0

    def fetch_users_by_email(emails: List[str]) -> List[UserProfile]:
        # This should be just
        #
        # UserProfile.objects.select_related("realm").filter(email__iexact__in=emails,
        #                                                    realm=realm)
        #
        # But chaining __in and __iexact doesn't work with Django's
        # ORM, so we have the following hack to construct the relevant where clause
        if len(emails) == 0:
            return []

        upper_list = ", ".join(["UPPER(%s)"] * len(emails))
        where_clause = "UPPER(zerver_userprofile.email::text) IN (%s)" % (upper_list,)
        return base_query.select_related("realm").extra(
            where=[where_clause],
            params=emails)

    return generic_bulk_cached_fetch(
        # Use a separate cache key to protect us from conflicts with
        # the get_user cache.
        lambda email: 'bulk_get_users:' + user_profile_cache_key_id(email, realm_id),
        fetch_users_by_email,
        [email.lower() for email in emails],
        id_fetcher=lambda user_profile: user_profile.email.lower()
    )

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

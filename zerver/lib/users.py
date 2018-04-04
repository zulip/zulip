from typing import Dict, List, Optional, Text

from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _

from zerver.lib.cache import generic_bulk_cached_fetch, user_profile_cache_key_id, \
    user_profile_by_id_cache_key
from zerver.lib.request import JsonableError
from zerver.models import UserProfile, Service, Realm, \
    get_user_profile_by_id, query_for_ids

from zulip_bots.custom_exceptions import ConfigValidationError

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

def check_valid_bot_config(service_name: str, config_data: Dict[str, str]) -> None:
    try:
        from zerver.lib.bot_lib import get_bot_handler
        bot_handler = get_bot_handler(service_name)
        if hasattr(bot_handler, 'validate_config'):
            bot_handler.validate_config(config_data)
    except ConfigValidationError:
        # The exception provides a specific error message, but that
        # message is not tagged translatable, because it is
        # triggered in the external zulip_bots package.
        # TODO: Think of some clever way to provide a more specific
        # error message.
        raise JsonableError(_("Invalid configuration data!"))

def check_bot_creation_policy(user_profile: UserProfile, bot_type: int) -> None:
    # Realm administrators can always add bot
    if user_profile.is_realm_admin:
        return

    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_EVERYONE:
        return
    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_ADMINS_ONLY:
        raise JsonableError(_("Must be an organization administrator"))
    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_LIMIT_GENERIC_BOTS and \
            bot_type == UserProfile.DEFAULT_BOT:
        raise JsonableError(_("Must be an organization administrator"))

def check_valid_bot_type(user_profile: UserProfile, bot_type: int) -> None:
    if bot_type not in user_profile.allowed_bot_types:
        raise JsonableError(_('Invalid bot type'))

def check_valid_interface_type(interface_type: int) -> None:
    if interface_type not in Service.ALLOWED_INTERFACE_TYPES:
        raise JsonableError(_('Invalid interface type'))

def bulk_get_users(emails: List[str], realm: Optional[Realm],
                   base_query: 'QuerySet[UserProfile]'=None) -> Dict[str, UserProfile]:
    if base_query is None:
        assert realm is not None
        query = UserProfile.objects.filter(realm=realm, is_active=True)
        realm_id = realm.id
    else:
        # WARNING: Currently, this code path only really supports one
        # version of `base_query` being used (because otherwise,
        # they'll share the cache, which can screw up the filtering).
        # If you're using this flow, you'll need to re-do any filters
        # in base_query in the code itself; base_query is just a perf
        # optimization.
        query = base_query
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
        return query.select_related("realm").extra(
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
    # TODO: Consider adding a flag to control whether deactivated
    # users should be included.

    def fetch_users_by_id(user_ids: List[int]) -> List[UserProfile]:
        if len(user_ids) == 0:
            return []

        return list(UserProfile.objects.filter(id__in=user_ids).select_related())

    user_profiles_by_id = generic_bulk_cached_fetch(
        cache_key_function=user_profile_by_id_cache_key,
        query_function=fetch_users_by_id,
        object_ids=user_ids
    )  # type: Dict[int, UserProfile]

    found_user_ids = user_profiles_by_id.keys()
    missed_user_ids = [user_id for user_id in user_ids if user_id not in found_user_ids]
    if missed_user_ids:
        raise JsonableError(_("Invalid user ID: %s" % (missed_user_ids[0])))

    user_profiles = list(user_profiles_by_id.values())
    for user_profile in user_profiles:
        if user_profile.realm != realm:
            raise JsonableError(_("Invalid user ID: %s" % (user_profile.id,)))
    return user_profiles

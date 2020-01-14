from typing import Any, Dict, List, Optional, Tuple, Union, cast

import unicodedata
from collections import defaultdict

from django.conf import settings
from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _

from zerver.lib.cache import generic_bulk_cached_fetch, user_profile_cache_key_id, \
    user_profile_by_id_cache_key
from zerver.lib.request import JsonableError
from zerver.lib.avatar import avatar_url, get_avatar_field
from zerver.lib.exceptions import OrganizationAdministratorRequired
from zerver.models import UserProfile, Service, Realm, \
    get_user_profile_by_id_in_realm, CustomProfileFieldValue, \
    get_realm_user_dicts, \
    CustomProfileField

from zulip_bots.custom_exceptions import ConfigValidationError

def check_full_name(full_name_raw: str) -> str:
    full_name = full_name_raw.strip()
    if len(full_name) > UserProfile.MAX_NAME_LENGTH:
        raise JsonableError(_("Name too long!"))
    if len(full_name) < UserProfile.MIN_NAME_LENGTH:
        raise JsonableError(_("Name too short!"))
    for character in full_name:
        if (unicodedata.category(character)[0] == 'C' or
                character in UserProfile.NAME_INVALID_CHARS):
            raise JsonableError(_("Invalid characters in name!"))
    return full_name

# NOTE: We don't try to absolutely prevent 2 bots from having the same
# name (e.g. you can get there by reactivating a deactivated bot after
# making a new bot with the same name).  This is just a check designed
# to make it unlikely to happen by accident.
def check_bot_name_available(realm_id: int, full_name: str) -> None:
    dup_exists = UserProfile.objects.filter(
        realm_id=realm_id,
        full_name=full_name.strip(),
        is_active=True,
    ).exists()

    if dup_exists:
        raise JsonableError(_("Name is already in use!"))

def check_short_name(short_name_raw: str) -> str:
    short_name = short_name_raw.strip()
    if len(short_name) == 0:
        raise JsonableError(_("Bad name or username"))
    return short_name

def check_valid_bot_config(bot_type: int, service_name: str,
                           config_data: Dict[str, str]) -> None:
    if bot_type == UserProfile.INCOMING_WEBHOOK_BOT:
        from zerver.lib.integrations import WEBHOOK_INTEGRATIONS
        config_options = None
        for integration in WEBHOOK_INTEGRATIONS:
            if integration.name == service_name:
                # key: validator
                config_options = {c[1]: c[2] for c in integration.config_options}
                break
        if not config_options:
            raise JsonableError(_("Invalid integration '%s'.") % (service_name,))

        missing_keys = set(config_options.keys()) - set(config_data.keys())
        if missing_keys:
            raise JsonableError(_("Missing configuration parameters: %s") % (
                missing_keys,))

        for key, validator in config_options.items():
            value = config_data[key]
            error = validator(key, value)
            if error:
                raise JsonableError(_("Invalid {} value {} ({})").format(
                                    key, value, error))

    elif bot_type == UserProfile.EMBEDDED_BOT:
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

# Adds an outgoing webhook or embedded bot service.
def add_service(name: str, user_profile: UserProfile, base_url: Optional[str]=None,
                interface: Optional[int]=None, token: Optional[str]=None) -> None:
    Service.objects.create(name=name,
                           user_profile=user_profile,
                           base_url=base_url,
                           interface=interface,
                           token=token)

def check_bot_creation_policy(user_profile: UserProfile, bot_type: int) -> None:
    # Realm administrators can always add bot
    if user_profile.is_realm_admin:
        return

    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_EVERYONE:
        return
    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_ADMINS_ONLY:
        raise OrganizationAdministratorRequired()
    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_LIMIT_GENERIC_BOTS and \
            bot_type == UserProfile.DEFAULT_BOT:
        raise OrganizationAdministratorRequired()

def check_valid_bot_type(user_profile: UserProfile, bot_type: int) -> None:
    if bot_type not in user_profile.allowed_bot_types:
        raise JsonableError(_('Invalid bot type'))

def check_valid_interface_type(interface_type: Optional[int]) -> None:
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
        upper_list = ", ".join(["UPPER(%s)"] * len(emails))
        where_clause = "UPPER(zerver_userprofile.email::text) IN (%s)" % (upper_list,)
        return query.select_related("realm").extra(
            where=[where_clause],
            params=emails)

    def user_to_email(user_profile: UserProfile) -> str:
        return user_profile.email.lower()

    return generic_bulk_cached_fetch(
        # Use a separate cache key to protect us from conflicts with
        # the get_user cache.
        lambda email: 'bulk_get_users:' + user_profile_cache_key_id(email, realm_id),
        fetch_users_by_email,
        [email.lower() for email in emails],
        id_fetcher=user_to_email,
    )

def user_ids_to_users(user_ids: List[int], realm: Realm) -> List[UserProfile]:
    # TODO: Consider adding a flag to control whether deactivated
    # users should be included.

    def fetch_users_by_id(user_ids: List[int]) -> List[UserProfile]:
        return list(UserProfile.objects.filter(id__in=user_ids).select_related())

    user_profiles_by_id = generic_bulk_cached_fetch(
        cache_key_function=user_profile_by_id_cache_key,
        query_function=fetch_users_by_id,
        object_ids=user_ids
    )  # type: Dict[int, UserProfile]

    found_user_ids = user_profiles_by_id.keys()
    missed_user_ids = [user_id for user_id in user_ids if user_id not in found_user_ids]
    if missed_user_ids:
        raise JsonableError(_("Invalid user ID: %s") % (missed_user_ids[0],))

    user_profiles = list(user_profiles_by_id.values())
    for user_profile in user_profiles:
        if user_profile.realm != realm:
            raise JsonableError(_("Invalid user ID: %s") % (user_profile.id,))
    return user_profiles

def access_bot_by_id(user_profile: UserProfile, user_id: int) -> UserProfile:
    try:
        target = get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("No such bot"))
    if not target.is_bot:
        raise JsonableError(_("No such bot"))
    if not user_profile.can_admin_user(target):
        raise JsonableError(_("Insufficient permission"))
    return target

def access_user_by_id(user_profile: UserProfile, user_id: int,
                      allow_deactivated: bool=False, allow_bots: bool=False) -> UserProfile:
    try:
        target = get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("No such user"))
    if target.is_bot and not allow_bots:
        raise JsonableError(_("No such user"))
    if not target.is_active and not allow_deactivated:
        raise JsonableError(_("User is deactivated"))
    if not user_profile.can_admin_user(target):
        raise JsonableError(_("Insufficient permission"))
    return target

def get_accounts_for_email(email: str) -> List[Dict[str, Optional[str]]]:
    profiles = UserProfile.objects.select_related('realm').filter(delivery_email__iexact=email.strip(),
                                                                  is_active=True,
                                                                  realm__deactivated=False,
                                                                  is_bot=False).order_by('date_joined')
    return [{"realm_name": profile.realm.name,
             "string_id": profile.realm.string_id,
             "full_name": profile.full_name,
             "avatar": avatar_url(profile)}
            for profile in profiles]

def get_api_key(user_profile: UserProfile) -> str:
    return user_profile.api_key

def get_all_api_keys(user_profile: UserProfile) -> List[str]:
    # Users can only have one API key for now
    return [user_profile.api_key]

def validate_user_custom_profile_field(realm_id: int, field: CustomProfileField,
                                       value: Union[int, str, List[int]]) -> Optional[str]:
    validators = CustomProfileField.FIELD_VALIDATORS
    field_type = field.field_type
    var_name = '{}'.format(field.name)
    if field_type in validators:
        validator = validators[field_type]
        result = validator(var_name, value)
    elif field_type == CustomProfileField.CHOICE:
        choice_field_validator = CustomProfileField.CHOICE_FIELD_VALIDATORS[field_type]
        field_data = field.field_data
        # Put an assertion so that mypy doesn't complain.
        assert field_data is not None
        result = choice_field_validator(var_name, field_data, value)
    elif field_type == CustomProfileField.USER:
        user_field_validator = CustomProfileField.USER_FIELD_VALIDATORS[field_type]
        result = user_field_validator(realm_id, cast(List[int], value), False)
    else:
        raise AssertionError("Invalid field type")
    return result

def validate_user_custom_profile_data(realm_id: int,
                                      profile_data: List[Dict[str, Union[int, str, List[int]]]]) -> None:
    # This function validate all custom field values according to their field type.
    for item in profile_data:
        field_id = item['id']
        try:
            field = CustomProfileField.objects.get(id=field_id)
        except CustomProfileField.DoesNotExist:
            raise JsonableError(_('Field id {id} not found.').format(id=field_id))

        result = validate_user_custom_profile_field(realm_id, field, item['value'])
        if result is not None:
            raise JsonableError(result)

def compute_show_invites_and_add_streams(user_profile: UserProfile) -> Tuple[bool, bool]:
    show_invites = True
    show_add_streams = True

    # Some realms only allow admins to invite users
    if user_profile.realm.invite_by_admins_only and not user_profile.is_realm_admin:
        show_invites = False
    if user_profile.is_guest:
        show_invites = False
        show_add_streams = False

    return (show_invites, show_add_streams)

def format_user_row(realm: Realm, acting_user: UserProfile, row: Dict[str, Any],
                    client_gravatar: bool,
                    custom_profile_field_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Formats a user row returned by a database fetch using
    .values(*realm_user_dict_fields) into a dictionary representation
    of that user for API delivery to clients.  The acting_user
    argument is used for permissions checks.
    """

    avatar_url = get_avatar_field(user_id=row['id'],
                                  realm_id=realm.id,
                                  email=row['delivery_email'],
                                  avatar_source=row['avatar_source'],
                                  avatar_version=row['avatar_version'],
                                  medium=False,
                                  client_gravatar=client_gravatar,)

    is_admin = row['role'] == UserProfile.ROLE_REALM_ADMINISTRATOR
    is_guest = row['role'] == UserProfile.ROLE_GUEST
    is_bot = row['is_bot']
    # This format should align with get_cross_realm_dicts() and notify_created_user
    result = dict(
        email=row['email'],
        user_id=row['id'],
        avatar_url=avatar_url,
        is_admin=is_admin,
        is_guest=is_guest,
        is_bot=is_bot,
        full_name=row['full_name'],
        timezone=row['timezone'],
        is_active = row['is_active'],
        date_joined = row['date_joined'].isoformat(),
    )
    if (realm.email_address_visibility == Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS and
            acting_user.is_realm_admin):
        result['delivery_email'] = row['delivery_email']

    if is_bot:
        result["bot_type"] = row["bot_type"]
        if row['email'] in settings.CROSS_REALM_BOT_EMAILS:
            result['is_cross_realm_bot'] = True

        # Note that bot_owner_id can be None with legacy data.
        result['bot_owner_id'] = row['bot_owner_id']
    elif custom_profile_field_data is not None:
        result['profile_data'] = custom_profile_field_data
    return result

def get_cross_realm_dicts() -> List[Dict[str, Any]]:

    users = bulk_get_users(list(settings.CROSS_REALM_BOT_EMAILS), None,
                           base_query=UserProfile.objects.filter(
                           realm__string_id=settings.SYSTEM_BOT_REALM)).values()
    result = []
    for user in users:
        # Important: We filter here, is addition to in
        # `base_query`, because of how bulk_get_users shares its
        # cache with other UserProfile caches.
        if user.realm.string_id == settings.SYSTEM_BOT_REALM:
            result.append(format_user_row(user.realm,
                                          acting_user=user,
                                          row=dict(email=user.email,
                                                   id=user.id,
                                                   user_profile=user,
                                                   realm=user.realm,
                                                   is_bot=user.is_bot,
                                                   bot_type=user.bot_type,
                                                   bot_owner_id=None,
                                                   full_name=user.full_name,
                                                   timezone=user.timezone,
                                                   is_active=user.is_active,
                                                   date_joined=user.date_joined,
                                                   delivery_email=user.delivery_email,
                                                   avatar_source=user.avatar_source,
                                                   avatar_version=user.avatar_version,
                                                   role=user.role
                                                   ),
                                          client_gravatar=False,
                                          custom_profile_field_data=None
                                          ))

    return result

def get_custom_profile_field_values(realm_id: int) -> Dict[int, Dict[str, Any]]:
    # TODO: Consider optimizing this query away with caching.
    custom_profile_field_values = CustomProfileFieldValue.objects.select_related(
        "field").filter(user_profile__realm_id=realm_id)
    profiles_by_user_id = defaultdict(dict)  # type: Dict[int, Dict[str, Any]]
    for profile_field in custom_profile_field_values:
        user_id = profile_field.user_profile_id
        if profile_field.field.is_renderable():
            profiles_by_user_id[user_id][profile_field.field_id] = {
                "value": profile_field.value,
                "rendered_value": profile_field.rendered_value
            }
        else:
            profiles_by_user_id[user_id][profile_field.field_id] = {
                "value": profile_field.value
            }
    return profiles_by_user_id

def get_raw_user_data(realm: Realm, user_profile: UserProfile, client_gravatar: bool,
                      include_custom_profile_fields: bool=True) -> Dict[int, Dict[str, str]]:
    user_dicts = get_realm_user_dicts(realm.id)
    profiles_by_user_id = None
    custom_profile_field_data = None

    if include_custom_profile_fields:
        profiles_by_user_id = get_custom_profile_field_values(realm.id)
    result = {}
    for row in user_dicts:
        if profiles_by_user_id is not None:
            custom_profile_field_data = profiles_by_user_id.get(row['id'], {})

        result[row['id']] = format_user_row(realm,
                                            acting_user = user_profile,
                                            row=row,
                                            client_gravatar= client_gravatar,
                                            custom_profile_field_data = custom_profile_field_data
                                            )
    return result

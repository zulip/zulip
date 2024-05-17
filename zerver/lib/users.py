import itertools
import re
import unicodedata
from collections import defaultdict
from email.headerregistry import Address
from operator import itemgetter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, TypedDict

import dateutil.parser as date_parser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _
from django_otp.middleware import is_verified
from typing_extensions import NotRequired
from zulip_bots.custom_exceptions import ConfigValidationError

from zerver.lib.avatar import avatar_url, get_avatar_field, get_avatar_for_inaccessible_user
from zerver.lib.cache import cache_with_key, get_cross_realm_dicts_key
from zerver.lib.exceptions import (
    JsonableError,
    OrganizationAdministratorRequiredError,
    OrganizationOwnerRequiredError,
)
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.timezone import canonicalize_timezone
from zerver.lib.types import ProfileDataElementUpdateDict, ProfileDataElementValue, RawUserDict
from zerver.lib.user_groups import is_user_in_group
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    Message,
    Realm,
    Recipient,
    Service,
    Subscription,
    UserMessage,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_fake_email_domain, require_unique_names
from zerver.models.users import (
    active_non_guest_user_ids,
    active_user_ids,
    get_realm_user_dicts,
    get_user,
    get_user_by_id_in_realm_including_cross_realm,
    get_user_profile_by_id_in_realm,
    is_cross_realm_bot_email,
)


def check_full_name(
    full_name_raw: str, *, user_profile: Optional[UserProfile], realm: Optional[Realm]
) -> str:
    full_name = full_name_raw.strip()
    if len(full_name) > UserProfile.MAX_NAME_LENGTH:
        raise JsonableError(_("Name too long!"))
    if len(full_name) < UserProfile.MIN_NAME_LENGTH:
        raise JsonableError(_("Name too short!"))
    for character in full_name:
        if unicodedata.category(character)[0] == "C" or character in UserProfile.NAME_INVALID_CHARS:
            raise JsonableError(_("Invalid characters in name!"))
    # Names ending with e.g. `|15` could be ambiguous for
    # sloppily-written parsers of our Markdown syntax for mentioning
    # users with ambiguous names, and likely have no real use, so we
    # ban them.
    if re.search(r"\|\d+$", full_name_raw):
        raise JsonableError(_("Invalid format!"))

    if require_unique_names(realm):
        normalized_user_full_name = unicodedata.normalize("NFKC", full_name).casefold()
        users_query = UserProfile.objects.filter(realm=realm)
        # We want to exclude the user's full name while checking for
        # uniqueness.
        if user_profile is not None:
            existing_names = users_query.exclude(id=user_profile.id).values_list(
                "full_name", flat=True
            )
        else:
            existing_names = users_query.values_list("full_name", flat=True)

        normalized_existing_names = [
            unicodedata.normalize("NFKC", full_name).casefold() for full_name in existing_names
        ]

        if normalized_user_full_name in normalized_existing_names:
            raise JsonableError(_("Unique names required in this organization."))

    return full_name


# NOTE: We don't try to absolutely prevent 2 bots from having the same
# name (e.g. you can get there by reactivating a deactivated bot after
# making a new bot with the same name).  This is just a check designed
# to make it unlikely to happen by accident.
def check_bot_name_available(realm_id: int, full_name: str, *, is_activation: bool) -> None:
    dup_exists = UserProfile.objects.filter(
        realm_id=realm_id,
        full_name=full_name.strip(),
        is_active=True,
    ).exists()

    if dup_exists:
        if is_activation:
            raise JsonableError(
                f'There is already an active bot named "{full_name}" in this organization. To reactivate this bot, you must rename or deactivate the other one first.'
            )
        else:
            raise JsonableError(_("Name is already in use!"))


def check_short_name(short_name_raw: str) -> str:
    short_name = short_name_raw.strip()
    if len(short_name) == 0:
        raise JsonableError(_("Bad name or username"))
    return short_name


def check_valid_bot_config(
    bot_type: int, service_name: str, config_data: Mapping[str, str]
) -> None:
    if bot_type == UserProfile.INCOMING_WEBHOOK_BOT:
        from zerver.lib.integrations import WEBHOOK_INTEGRATIONS

        config_options = None
        for integration in WEBHOOK_INTEGRATIONS:
            if integration.name == service_name:
                # key: validator
                config_options = {c[1]: c[2] for c in integration.config_options}
                break
        if not config_options:
            raise JsonableError(
                _("Invalid integration '{integration_name}'.").format(integration_name=service_name)
            )

        missing_keys = set(config_options.keys()) - set(config_data.keys())
        if missing_keys:
            raise JsonableError(
                _("Missing configuration parameters: {keys}").format(
                    keys=missing_keys,
                )
            )

        for key, validator in config_options.items():
            value = config_data[key]
            error = validator(key, value)
            if error is not None:
                raise JsonableError(
                    _("Invalid {key} value {value} ({error})").format(
                        key=key, value=value, error=error
                    )
                )

    elif bot_type == UserProfile.EMBEDDED_BOT:
        try:
            from zerver.lib.bot_lib import get_bot_handler

            bot_handler = get_bot_handler(service_name)
            if hasattr(bot_handler, "validate_config"):
                bot_handler.validate_config(config_data)
        except ConfigValidationError:
            # The exception provides a specific error message, but that
            # message is not tagged translatable, because it is
            # triggered in the external zulip_bots package.
            # TODO: Think of some clever way to provide a more specific
            # error message.
            raise JsonableError(_("Invalid configuration data!"))


# Adds an outgoing webhook or embedded bot service.
def add_service(
    name: str,
    user_profile: UserProfile,
    base_url: str,
    interface: int,
    token: str,
) -> None:
    Service.objects.create(
        name=name, user_profile=user_profile, base_url=base_url, interface=interface, token=token
    )


def check_bot_creation_policy(user_profile: UserProfile, bot_type: int) -> None:
    # Realm administrators can always add bot
    if user_profile.is_realm_admin:
        return

    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_EVERYONE:
        return
    if user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_ADMINS_ONLY:
        raise OrganizationAdministratorRequiredError
    if (
        user_profile.realm.bot_creation_policy == Realm.BOT_CREATION_LIMIT_GENERIC_BOTS
        and bot_type == UserProfile.DEFAULT_BOT
    ):
        raise OrganizationAdministratorRequiredError


def check_valid_bot_type(user_profile: UserProfile, bot_type: int) -> None:
    if bot_type not in user_profile.allowed_bot_types:
        raise JsonableError(_("Invalid bot type"))


def check_valid_interface_type(interface_type: Optional[int]) -> None:
    if interface_type not in Service.ALLOWED_INTERFACE_TYPES:
        raise JsonableError(_("Invalid interface type"))


def is_administrator_role(role: int) -> bool:
    return role in {UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER}


def bulk_get_cross_realm_bots() -> Dict[str, UserProfile]:
    emails = list(settings.CROSS_REALM_BOT_EMAILS)

    # This should be just
    #
    # UserProfile.objects.select_related("realm").filter(email__iexact__in=emails,
    #                                                    realm=realm)
    #
    # But chaining __in and __iexact doesn't work with Django's
    # ORM, so we have the following hack to construct the relevant where clause
    where_clause = (
        "upper(zerver_userprofile.email::text) IN (SELECT upper(email) FROM unnest(%s) AS email)"
    )
    users = UserProfile.objects.filter(realm__string_id=settings.SYSTEM_BOT_REALM).extra(
        where=[where_clause], params=(emails,)
    )

    return {user.email.lower(): user for user in users}


def user_ids_to_users(user_ids: Sequence[int], realm: Realm) -> List[UserProfile]:
    # TODO: Consider adding a flag to control whether deactivated
    # users should be included.

    user_profiles = list(
        UserProfile.objects.filter(id__in=user_ids, realm=realm).select_related("realm")
    )

    found_user_ids = {user_profile.id for user_profile in user_profiles}

    for user_id in user_ids:
        if user_id not in found_user_ids:
            raise JsonableError(_("Invalid user ID: {user_id}").format(user_id=user_id))

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

    if target.can_create_users and not user_profile.is_realm_owner:
        # Organizations owners are required to administer a bot with
        # the can_create_users permission. User creation via the API
        # is a permission not available even to organization owners by
        # default, because it can be abused to send spam. Requiring an
        # owner is intended to ensure organizational responsibility
        # for use of this permission.
        raise OrganizationOwnerRequiredError

    return target


def access_user_common(
    target: UserProfile,
    user_profile: UserProfile,
    allow_deactivated: bool,
    allow_bots: bool,
    for_admin: bool,
) -> UserProfile:
    if target.is_bot and not allow_bots:
        raise JsonableError(_("No such user"))
    if not target.is_active and not allow_deactivated:
        raise JsonableError(_("User is deactivated"))
    if not for_admin:
        # Administrative access is not required just to read a user
        # but we need to check can_access_all_users_group setting.
        if not check_can_access_user(target, user_profile):
            raise JsonableError(_("Insufficient permission"))

        return target
    if not user_profile.can_admin_user(target):
        raise JsonableError(_("Insufficient permission"))
    return target


def access_user_by_id(
    user_profile: UserProfile,
    target_user_id: int,
    *,
    allow_deactivated: bool = False,
    allow_bots: bool = False,
    for_admin: bool,
) -> UserProfile:
    """Master function for accessing another user by ID in API code;
    verifies the user ID is in the same realm, and if requested checks
    for administrative privileges, with flags for various special
    cases.
    """
    try:
        target = get_user_profile_by_id_in_realm(target_user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("No such user"))

    return access_user_common(target, user_profile, allow_deactivated, allow_bots, for_admin)


def access_user_by_id_including_cross_realm(
    user_profile: UserProfile,
    target_user_id: int,
    *,
    allow_deactivated: bool = False,
    allow_bots: bool = False,
    for_admin: bool,
) -> UserProfile:
    """Variant of access_user_by_id allowing cross-realm bots to be accessed."""
    try:
        target = get_user_by_id_in_realm_including_cross_realm(target_user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("No such user"))

    return access_user_common(target, user_profile, allow_deactivated, allow_bots, for_admin)


def access_user_by_email(
    user_profile: UserProfile,
    email: str,
    *,
    allow_deactivated: bool = False,
    allow_bots: bool = False,
    for_admin: bool,
) -> UserProfile:
    try:
        target = get_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("No such user"))

    return access_user_common(target, user_profile, allow_deactivated, allow_bots, for_admin)


class Account(TypedDict):
    realm_name: str
    realm_id: int
    full_name: str
    avatar: Optional[str]


def get_accounts_for_email(email: str) -> List[Account]:
    profiles = (
        UserProfile.objects.select_related("realm")
        .filter(
            delivery_email__iexact=email.strip(),
            is_active=True,
            realm__deactivated=False,
            is_bot=False,
        )
        .order_by("date_joined")
    )
    return [
        dict(
            realm_name=profile.realm.name,
            realm_id=profile.realm.id,
            full_name=profile.full_name,
            avatar=avatar_url(profile),
        )
        for profile in profiles
    ]


def get_api_key(user_profile: UserProfile) -> str:
    return user_profile.api_key


def get_all_api_keys(user_profile: UserProfile) -> List[str]:
    # Users can only have one API key for now
    return [user_profile.api_key]


def validate_user_custom_profile_field(
    realm_id: int, field: CustomProfileField, value: ProfileDataElementValue
) -> ProfileDataElementValue:
    validators = CustomProfileField.FIELD_VALIDATORS
    field_type = field.field_type
    var_name = f"{field.name}"
    if field_type in validators:
        validator = validators[field_type]
        return validator(var_name, value)
    elif field_type == CustomProfileField.SELECT:
        choice_field_validator = CustomProfileField.SELECT_FIELD_VALIDATORS[field_type]
        field_data = field.field_data
        # Put an assertion so that mypy doesn't complain.
        assert field_data is not None
        return choice_field_validator(var_name, field_data, value)
    elif field_type == CustomProfileField.USER:
        user_field_validator = CustomProfileField.USER_FIELD_VALIDATORS[field_type]
        return user_field_validator(realm_id, value, False)
    else:
        raise AssertionError("Invalid field type")


def validate_user_custom_profile_data(
    realm_id: int, profile_data: List[ProfileDataElementUpdateDict]
) -> None:
    # This function validate all custom field values according to their field type.
    for item in profile_data:
        field_id = item["id"]
        try:
            field = CustomProfileField.objects.get(id=field_id)
        except CustomProfileField.DoesNotExist:
            raise JsonableError(_("Field id {id} not found.").format(id=field_id))

        try:
            validate_user_custom_profile_field(realm_id, field, item["value"])
        except ValidationError as error:
            raise JsonableError(error.message)


def can_access_delivery_email(
    user_profile: UserProfile,
    target_user_id: int,
    email_address_visibility: int,
) -> bool:
    if target_user_id == user_profile.id:
        return True

    # Bots always have email_address_visibility as EMAIL_ADDRESS_VISIBILITY_EVERYONE.
    if email_address_visibility == UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
        return True

    if email_address_visibility == UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS:
        return user_profile.is_realm_admin

    if email_address_visibility == UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS:
        return user_profile.is_realm_admin or user_profile.is_moderator

    if email_address_visibility == UserProfile.EMAIL_ADDRESS_VISIBILITY_MEMBERS:
        return not user_profile.is_guest

    return False


class APIUserDict(TypedDict):
    email: str
    user_id: int
    avatar_version: int
    is_admin: bool
    is_owner: bool
    is_guest: bool
    is_billing_admin: NotRequired[bool]
    role: int
    is_bot: bool
    full_name: str
    timezone: NotRequired[str]
    is_active: bool
    date_joined: str
    avatar_url: NotRequired[Optional[str]]
    delivery_email: Optional[str]
    bot_type: NotRequired[Optional[int]]
    bot_owner_id: NotRequired[Optional[int]]
    profile_data: NotRequired[Optional[Dict[str, Any]]]
    is_system_bot: NotRequired[bool]
    max_message_id: NotRequired[int]


def format_user_row(
    realm_id: int,
    acting_user: Optional[UserProfile],
    row: RawUserDict,
    client_gravatar: bool,
    user_avatar_url_field_optional: bool,
    custom_profile_field_data: Optional[Dict[str, Any]] = None,
) -> APIUserDict:
    """Formats a user row returned by a database fetch using
    .values(*realm_user_dict_fields) into a dictionary representation
    of that user for API delivery to clients.  The acting_user
    argument is used for permissions checks.
    """

    is_admin = is_administrator_role(row["role"])
    is_owner = row["role"] == UserProfile.ROLE_REALM_OWNER
    is_guest = row["role"] == UserProfile.ROLE_GUEST
    is_bot = row["is_bot"]

    delivery_email = None
    if acting_user is not None and can_access_delivery_email(
        acting_user, row["id"], row["email_address_visibility"]
    ):
        delivery_email = row["delivery_email"]

    result = APIUserDict(
        email=row["email"],
        user_id=row["id"],
        avatar_version=row["avatar_version"],
        is_admin=is_admin,
        is_owner=is_owner,
        is_guest=is_guest,
        is_billing_admin=row["is_billing_admin"],
        role=row["role"],
        is_bot=is_bot,
        full_name=row["full_name"],
        timezone=canonicalize_timezone(row["timezone"]),
        is_active=row["is_active"],
        date_joined=row["date_joined"].isoformat(),
        delivery_email=delivery_email,
    )

    if acting_user is None:
        # Remove data about other users which are not useful to spectators
        # or can reveal personal information about a user.
        # Only send day level precision date_joined data to spectators.
        del result["is_billing_admin"]
        del result["timezone"]
        assert isinstance(result["date_joined"], str)
        result["date_joined"] = str(date_parser.parse(result["date_joined"]).date())

    # Zulip clients that support using `GET /avatar/{user_id}` as a
    # fallback if we didn't send an avatar URL in the user object pass
    # user_avatar_url_field_optional in client_capabilities.
    #
    # This is a major network performance optimization for
    # organizations with 10,000s of users where we would otherwise
    # send avatar URLs in the payload (either because most users have
    # uploaded avatars or because EMAIL_ADDRESS_VISIBILITY_ADMINS
    # prevents the older client_gravatar optimization from helping).
    # The performance impact is large largely because the hashes in
    # avatar URLs structurally cannot compress well.
    #
    # The user_avatar_url_field_optional gives the server sole
    # discretion in deciding for which users we want to send the
    # avatar URL (Which saves clients an RTT at the cost of some
    # bandwidth).  At present, the server looks at `long_term_idle` to
    # decide which users to include avatars for, piggy-backing on a
    # different optimization for organizations with 10,000s of users.
    include_avatar_url = not user_avatar_url_field_optional or not row["long_term_idle"]
    if include_avatar_url:
        result["avatar_url"] = get_avatar_field(
            user_id=row["id"],
            realm_id=realm_id,
            email=row["delivery_email"],
            avatar_source=row["avatar_source"],
            avatar_version=row["avatar_version"],
            medium=False,
            client_gravatar=client_gravatar,
        )

    if is_bot:
        result["bot_type"] = row["bot_type"]
        if is_cross_realm_bot_email(row["email"]):
            result["is_system_bot"] = True

        # Note that bot_owner_id can be None with legacy data.
        result["bot_owner_id"] = row["bot_owner_id"]
    elif custom_profile_field_data is not None:
        result["profile_data"] = custom_profile_field_data
    return result


def user_access_restricted_in_realm(target_user: UserProfile) -> bool:
    if target_user.is_bot:
        return False

    realm = target_user.realm
    if realm.can_access_all_users_group.named_user_group.name == SystemGroups.EVERYONE:
        return False

    return True


def check_user_can_access_all_users(acting_user: Optional[UserProfile]) -> bool:
    if acting_user is None:
        # We allow spectators to access all users since they
        # have very limited access to the user already.
        return True

    if not acting_user.is_guest:
        return True

    realm = acting_user.realm
    if is_user_in_group(realm.can_access_all_users_group, acting_user):
        return True

    return False


def check_can_access_user(
    target_user: UserProfile, user_profile: Optional[UserProfile] = None
) -> bool:
    if not user_access_restricted_in_realm(target_user):
        return True

    if check_user_can_access_all_users(user_profile):
        return True

    assert user_profile is not None

    if target_user.id == user_profile.id:
        return True

    # These include Subscription objects for streams as well as group DMs.
    subscribed_recipient_ids = Subscription.objects.filter(
        user_profile=user_profile,
        active=True,
        recipient__type__in=[Recipient.STREAM, Recipient.DIRECT_MESSAGE_GROUP],
    ).values_list("recipient_id", flat=True)

    if Subscription.objects.filter(
        recipient_id__in=subscribed_recipient_ids,
        user_profile=target_user,
        active=True,
        is_user_active=True,
    ).exists():
        return True

    assert user_profile.recipient_id is not None
    assert target_user.recipient_id is not None

    # Querying the "Message" table is expensive so we do this last.
    direct_message_query = Message.objects.filter(
        recipient__type=Recipient.PERSONAL, realm=target_user.realm
    )
    if direct_message_query.filter(
        Q(sender_id=target_user.id, recipient_id=user_profile.recipient_id)
        | Q(recipient_id=target_user.recipient_id, sender_id=user_profile.id)
    ).exists():
        return True

    return False


def get_inaccessible_user_ids(
    target_user_ids: List[int], acting_user: Optional[UserProfile]
) -> Set[int]:
    if check_user_can_access_all_users(acting_user):
        return set()

    assert acting_user is not None

    # All users can access all the bots, so we just exclude them.
    target_human_user_ids = UserProfile.objects.filter(
        id__in=target_user_ids, is_bot=False
    ).values_list("id", flat=True)

    if not target_human_user_ids:
        return set()

    subscribed_recipient_ids = Subscription.objects.filter(
        user_profile=acting_user,
        active=True,
        recipient__type__in=[Recipient.STREAM, Recipient.DIRECT_MESSAGE_GROUP],
    ).values_list("recipient_id", flat=True)

    common_subscription_user_ids = (
        Subscription.objects.filter(
            recipient_id__in=subscribed_recipient_ids,
            user_profile_id__in=target_human_user_ids,
            active=True,
            is_user_active=True,
        )
        .distinct("user_profile_id")
        .values_list("user_profile_id", flat=True)
    )

    possible_inaccessible_user_ids = set(target_human_user_ids) - set(common_subscription_user_ids)
    if not possible_inaccessible_user_ids:
        return set()

    target_user_recipient_ids = UserProfile.objects.filter(
        id__in=possible_inaccessible_user_ids
    ).values_list("recipient_id", flat=True)

    direct_message_query = Message.objects.filter(
        recipient__type=Recipient.PERSONAL, realm=acting_user.realm
    )
    direct_messages_users = direct_message_query.filter(
        Q(sender_id__in=possible_inaccessible_user_ids, recipient_id=acting_user.recipient_id)
        | Q(recipient_id__in=target_user_recipient_ids, sender_id=acting_user.id)
    ).values_list("sender_id", "recipient__type_id")

    user_ids_involved_in_dms = set()
    for sender_id, recipient_user_id in direct_messages_users:
        if sender_id == acting_user.id:
            user_ids_involved_in_dms.add(recipient_user_id)
        else:
            user_ids_involved_in_dms.add(sender_id)

    inaccessible_user_ids = possible_inaccessible_user_ids - user_ids_involved_in_dms
    return inaccessible_user_ids


def get_user_ids_who_can_access_user(target_user: UserProfile) -> List[int]:
    # We assume that caller only needs active users here, since
    # this function is used to get users to send events and to
    # send presence update.
    realm = target_user.realm
    if not user_access_restricted_in_realm(target_user):
        return active_user_ids(realm.id)

    active_non_guest_user_ids_in_realm = active_non_guest_user_ids(realm.id)

    users_in_subscribed_streams_or_huddles_dict = get_subscribers_of_target_user_subscriptions(
        [target_user]
    )
    users_involved_in_dms_dict = get_users_involved_in_dms_with_target_users([target_user], realm)

    user_ids_who_can_access_target_user = (
        {target_user.id}
        | set(active_non_guest_user_ids_in_realm)
        | users_in_subscribed_streams_or_huddles_dict[target_user.id]
        | users_involved_in_dms_dict[target_user.id]
    )
    return list(user_ids_who_can_access_target_user)


def get_subscribers_of_target_user_subscriptions(
    target_users: List[UserProfile], include_deactivated_users_for_huddles: bool = False
) -> Dict[int, Set[int]]:
    target_user_ids = [user.id for user in target_users]
    target_user_subscriptions = (
        Subscription.objects.filter(
            user_profile__in=target_user_ids,
            active=True,
            recipient__type__in=[Recipient.STREAM, Recipient.DIRECT_MESSAGE_GROUP],
        )
        .order_by("user_profile_id")
        .values("user_profile_id", "recipient_id")
    )

    target_users_subbed_recipient_ids = set()
    target_user_subscriptions_dict: Dict[int, Set[int]] = defaultdict(set)

    for user_profile_id, sub_rows in itertools.groupby(
        target_user_subscriptions, itemgetter("user_profile_id")
    ):
        recipient_ids = {row["recipient_id"] for row in sub_rows}
        target_user_subscriptions_dict[user_profile_id] = recipient_ids
        target_users_subbed_recipient_ids |= recipient_ids

    subs_in_target_user_subscriptions_query = Subscription.objects.filter(
        recipient_id__in=list(target_users_subbed_recipient_ids),
        active=True,
    )

    if include_deactivated_users_for_huddles:
        subs_in_target_user_subscriptions_query = subs_in_target_user_subscriptions_query.filter(
            Q(recipient__type=Recipient.STREAM, is_user_active=True)
            | Q(recipient__type=Recipient.DIRECT_MESSAGE_GROUP)
        )
    else:
        subs_in_target_user_subscriptions_query = subs_in_target_user_subscriptions_query.filter(
            recipient__type__in=[Recipient.STREAM, Recipient.DIRECT_MESSAGE_GROUP],
            is_user_active=True,
        )

    subs_in_target_user_subscriptions = subs_in_target_user_subscriptions_query.order_by(
        "recipient_id"
    ).values("user_profile_id", "recipient_id")

    subscribers_dict_by_recipient_ids: Dict[int, Set[int]] = defaultdict(set)
    for recipient_id, sub_rows in itertools.groupby(
        subs_in_target_user_subscriptions, itemgetter("recipient_id")
    ):
        user_ids = {row["user_profile_id"] for row in sub_rows}
        subscribers_dict_by_recipient_ids[recipient_id] = user_ids

    users_subbed_to_target_user_subscriptions_dict: Dict[int, Set[int]] = defaultdict(set)
    for user_id in target_user_ids:
        target_user_subbed_recipients = target_user_subscriptions_dict[user_id]
        for recipient_id in target_user_subbed_recipients:
            users_subbed_to_target_user_subscriptions_dict[user_id] |= (
                subscribers_dict_by_recipient_ids[recipient_id]
            )

    return users_subbed_to_target_user_subscriptions_dict


def get_users_involved_in_dms_with_target_users(
    target_users: List[UserProfile], realm: Realm, include_deactivated_users: bool = False
) -> Dict[int, Set[int]]:
    target_user_ids = [user.id for user in target_users]

    direct_messages_recipient_users = (
        Message.objects.filter(
            sender_id__in=target_user_ids, realm=realm, recipient__type=Recipient.PERSONAL
        )
        .order_by("sender_id")
        .distinct("sender_id", "recipient__type_id")
        .values("sender_id", "recipient__type_id")
    )

    direct_messages_recipient_users_set = {
        obj["recipient__type_id"] for obj in direct_messages_recipient_users
    }
    active_direct_messages_recipient_user_ids = UserProfile.objects.filter(
        id__in=list(direct_messages_recipient_users_set), is_active=True
    ).values_list("id", flat=True)

    direct_message_participants_dict: Dict[int, Set[int]] = defaultdict(set)
    for sender_id, message_rows in itertools.groupby(
        direct_messages_recipient_users, itemgetter("sender_id")
    ):
        recipient_user_ids = {row["recipient__type_id"] for row in message_rows}
        if not include_deactivated_users:
            recipient_user_ids &= set(active_direct_messages_recipient_user_ids)

        direct_message_participants_dict[sender_id] = recipient_user_ids

    personal_recipient_ids_for_target_users = [user.recipient_id for user in target_users]
    direct_message_senders_query = Message.objects.filter(
        realm=realm,
        recipient_id__in=personal_recipient_ids_for_target_users,
        recipient__type=Recipient.PERSONAL,
    )

    if not include_deactivated_users:
        direct_message_senders_query = direct_message_senders_query.filter(sender__is_active=True)

    direct_messages_senders = (
        direct_message_senders_query.order_by("recipient__type_id")
        .distinct("sender_id", "recipient__type_id")
        .values("sender_id", "recipient__type_id")
    )

    for recipient_user_id, message_rows in itertools.groupby(
        direct_messages_senders, itemgetter("recipient__type_id")
    ):
        sender_ids = {row["sender_id"] for row in message_rows}
        direct_message_participants_dict[recipient_user_id] |= sender_ids

    return direct_message_participants_dict


def user_profile_to_user_row(user_profile: UserProfile) -> RawUserDict:
    return RawUserDict(
        id=user_profile.id,
        full_name=user_profile.full_name,
        email=user_profile.email,
        avatar_source=user_profile.avatar_source,
        avatar_version=user_profile.avatar_version,
        is_active=user_profile.is_active,
        role=user_profile.role,
        is_billing_admin=user_profile.is_billing_admin,
        is_bot=user_profile.is_bot,
        timezone=user_profile.timezone,
        date_joined=user_profile.date_joined,
        bot_owner_id=user_profile.bot_owner_id,
        delivery_email=user_profile.delivery_email,
        bot_type=user_profile.bot_type,
        long_term_idle=user_profile.long_term_idle,
        email_address_visibility=user_profile.email_address_visibility,
    )


@cache_with_key(get_cross_realm_dicts_key)
def get_cross_realm_dicts() -> List[APIUserDict]:
    user_dict = bulk_get_cross_realm_bots()
    users = sorted(user_dict.values(), key=lambda user: user.full_name)
    result = []
    for user in users:
        user_row = user_profile_to_user_row(user)
        # Because we want to avoid clients being exposed to the
        # implementation detail that these bots are self-owned, we
        # just set bot_owner_id=None.
        user_row["bot_owner_id"] = None

        result.append(
            format_user_row(
                user.realm_id,
                acting_user=user,
                row=user_row,
                client_gravatar=False,
                user_avatar_url_field_optional=False,
                custom_profile_field_data=None,
            )
        )

    return result


def get_data_for_inaccessible_user(realm: Realm, user_id: int) -> APIUserDict:
    fake_email = Address(
        username=f"user{user_id}", domain=get_fake_email_domain(realm.host)
    ).addr_spec

    # We just set date_joined field to UNIX epoch.
    user_date_joined = timestamp_to_datetime(0)

    user_dict = APIUserDict(
        email=fake_email,
        user_id=user_id,
        avatar_version=1,
        is_admin=False,
        is_owner=False,
        is_guest=False,
        is_billing_admin=False,
        role=UserProfile.ROLE_MEMBER,
        is_bot=False,
        full_name=str(UserProfile.INACCESSIBLE_USER_NAME),
        timezone="",
        is_active=True,
        date_joined=user_date_joined.isoformat(),
        delivery_email=None,
        avatar_url=get_avatar_for_inaccessible_user(),
        profile_data={},
    )
    return user_dict


def get_accessible_user_ids(
    realm: Realm, user_profile: UserProfile, include_deactivated_users: bool = False
) -> List[int]:
    subscribers_dict_of_target_user_subscriptions = get_subscribers_of_target_user_subscriptions(
        [user_profile], include_deactivated_users_for_huddles=include_deactivated_users
    )
    users_involved_in_dms_dict = get_users_involved_in_dms_with_target_users(
        [user_profile], realm, include_deactivated_users=include_deactivated_users
    )

    # This does not include bots, because either the caller
    # wants only human users or it handles bots separately.
    accessible_user_ids = (
        {user_profile.id}
        | subscribers_dict_of_target_user_subscriptions[user_profile.id]
        | users_involved_in_dms_dict[user_profile.id]
    )

    return list(accessible_user_ids)


def get_user_dicts_in_realm(
    realm: Realm, user_profile: Optional[UserProfile]
) -> Tuple[List[RawUserDict], List[APIUserDict]]:
    group_allowed_to_access_all_users = realm.can_access_all_users_group
    assert group_allowed_to_access_all_users is not None

    all_user_dicts = get_realm_user_dicts(realm.id)
    if check_user_can_access_all_users(user_profile):
        return (all_user_dicts, [])

    assert user_profile is not None
    accessible_user_ids = get_accessible_user_ids(
        realm, user_profile, include_deactivated_users=True
    )

    accessible_user_dicts: List[RawUserDict] = []
    inaccessible_user_dicts: List[APIUserDict] = []
    for user_dict in all_user_dicts:
        if user_dict["id"] in accessible_user_ids or user_dict["is_bot"]:
            accessible_user_dicts.append(user_dict)
        else:
            inaccessible_user_dicts.append(get_data_for_inaccessible_user(realm, user_dict["id"]))

    return (accessible_user_dicts, inaccessible_user_dicts)


def get_custom_profile_field_values(
    custom_profile_field_values: Iterable[CustomProfileFieldValue],
) -> Dict[int, Dict[str, Any]]:
    profiles_by_user_id: Dict[int, Dict[str, Any]] = defaultdict(dict)
    for profile_field in custom_profile_field_values:
        user_id = profile_field.user_profile_id
        if profile_field.field.is_renderable():
            profiles_by_user_id[user_id][str(profile_field.field_id)] = {
                "value": profile_field.value,
                "rendered_value": profile_field.rendered_value,
            }
        else:
            profiles_by_user_id[user_id][str(profile_field.field_id)] = {
                "value": profile_field.value,
            }
    return profiles_by_user_id


def get_users_for_api(
    realm: Realm,
    acting_user: Optional[UserProfile],
    *,
    target_user: Optional[UserProfile] = None,
    client_gravatar: bool,
    user_avatar_url_field_optional: bool,
    include_custom_profile_fields: bool = True,
    user_list_incomplete: bool = False,
) -> Dict[int, APIUserDict]:
    """Fetches data about the target user(s) appropriate for sending to
    acting_user via the standard format for the Zulip API.  If
    target_user is None, we fetch all users in the realm.
    """
    profiles_by_user_id = None
    custom_profile_field_data = None
    # target_user is an optional parameter which is passed when user data of a specific user
    # is required. It is 'None' otherwise.
    accessible_user_dicts: List[RawUserDict] = []
    inaccessible_user_dicts: List[APIUserDict] = []
    if target_user is not None:
        accessible_user_dicts = [user_profile_to_user_row(target_user)]
    else:
        accessible_user_dicts, inaccessible_user_dicts = get_user_dicts_in_realm(realm, acting_user)

    if include_custom_profile_fields:
        base_query = CustomProfileFieldValue.objects.select_related("field")
        # TODO: Consider optimizing this query away with caching.
        if target_user is not None:
            custom_profile_field_values = base_query.filter(user_profile=target_user)
        else:
            custom_profile_field_values = base_query.filter(field__realm_id=realm.id)
        profiles_by_user_id = get_custom_profile_field_values(custom_profile_field_values)

    result = {}
    for row in accessible_user_dicts:
        if profiles_by_user_id is not None:
            custom_profile_field_data = profiles_by_user_id.get(row["id"], {})
        client_gravatar_for_user = (
            client_gravatar
            and row["email_address_visibility"] == UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE
        )
        result[row["id"]] = format_user_row(
            realm.id,
            acting_user=acting_user,
            row=row,
            client_gravatar=client_gravatar_for_user,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            custom_profile_field_data=custom_profile_field_data,
        )

    if not user_list_incomplete:
        for inaccessible_user_row in inaccessible_user_dicts:
            # We already have the required data for inaccessible users
            # in row object, so we can just add it to result directly.
            user_id = inaccessible_user_row["user_id"]
            result[user_id] = inaccessible_user_row

    return result


def get_active_bots_owned_by_user(user_profile: UserProfile) -> QuerySet[UserProfile]:
    return UserProfile.objects.filter(is_bot=True, is_active=True, bot_owner=user_profile)


def is_2fa_verified(user: UserProfile) -> bool:
    """
    It is generally unsafe to call is_verified directly on `request.user` since
    the attribute `otp_device` does not exist on an `AnonymousUser`, and `is_verified`
    does not make sense without 2FA being enabled.

    This wraps the checks for all these assumptions to make sure the call is safe.
    """
    # Explicitly require the caller to ensure that settings.TWO_FACTOR_AUTHENTICATION_ENABLED
    # is True before calling `is_2fa_verified`.
    assert settings.TWO_FACTOR_AUTHENTICATION_ENABLED
    return is_verified(user)


def get_users_with_access_to_real_email(user_profile: UserProfile) -> List[int]:
    if not user_access_restricted_in_realm(user_profile):
        active_users = user_profile.realm.get_active_users()
    else:
        # The get_user_ids_who_can_access_user returns user IDs and not
        # user objects and we instead do one more query for UserProfile
        # objects. We need complete UserProfile objects only for a couple
        # of cases and it is not worth to query the whole UserProfile
        # objects in all the cases and it is fine to do the extra query
        # wherever needed.
        user_ids_who_can_access_user = get_user_ids_who_can_access_user(user_profile)
        active_users = UserProfile.objects.filter(
            id__in=user_ids_who_can_access_user, is_active=True
        )

    return [
        user.id
        for user in active_users
        if can_access_delivery_email(
            user,
            user_profile.id,
            user_profile.email_address_visibility,
        )
    ]


def max_message_id_for_user(user_profile: Optional[UserProfile]) -> int:
    if user_profile is None:
        return -1
    max_message = (
        UserMessage.objects.filter(user_profile=user_profile)
        .order_by("-message_id")
        .only("message_id")
        .first()
    )
    if max_message:
        return max_message.message_id
    else:
        return -1

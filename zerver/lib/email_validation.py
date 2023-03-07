from email.headerregistry import Address
from typing import Callable, Dict, Optional, Set, Tuple

from django.core import validators
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from zerver.lib.name_restrictions import is_disposable_domain

# TODO: Move DisposableEmailError, etc. into here.
from zerver.models import (
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    Realm,
    RealmDomain,
    get_users_by_delivery_email,
    is_cross_realm_bot_email,
)


def validate_disposable(email: str) -> None:
    if is_disposable_domain(Address(addr_spec=email).domain):
        raise DisposableEmailError


def get_realm_email_validator(realm: Realm) -> Callable[[str], None]:
    if not realm.emails_restricted_to_domains:
        # Should we also do '+' check for non-restricted realms?
        if realm.disallow_disposable_email_addresses:
            return validate_disposable

        # allow any email through
        return lambda email: None

    """
    RESTRICTIVE REALMS:

    Some realms only allow emails within a set
    of domains that are configured in RealmDomain.

    We get the set of domains up front so that
    folks can validate multiple emails without
    multiple round trips to the database.
    """

    query = RealmDomain.objects.filter(realm=realm)
    rows = list(query.values("allow_subdomains", "domain"))

    allowed_domains = {r["domain"] for r in rows}

    allowed_subdomains = {r["domain"] for r in rows if r["allow_subdomains"]}

    def validate(email: str) -> None:
        """
        We don't have to do a "disposable" check for restricted
        domains, since the realm is already giving us
        a small whitelist.
        """

        address = Address(addr_spec=email)
        if "+" in address.username:
            raise EmailContainsPlusError

        domain = address.domain.lower()

        if domain in allowed_domains:
            return

        while len(domain) > 0:
            subdomain, sep, domain = domain.partition(".")
            if domain in allowed_subdomains:
                return

        raise DomainNotAllowedForRealmError

    return validate


# Is a user with the given email address allowed to be in the given realm?
# (This function does not check whether the user has been invited to the realm.
# So for invite-only realms, this is the test for whether a user can be invited,
# not whether the user can sign up currently.)
def email_allowed_for_realm(email: str, realm: Realm) -> None:
    """
    Avoid calling this in a loop!
    Instead, call get_realm_email_validator()
    outside of the loop.
    """
    get_realm_email_validator(realm)(email)


def validate_email_is_valid(
    email: str,
    validate_email_allowed_in_realm: Callable[[str], None],
) -> Optional[str]:
    try:
        validators.validate_email(email)
    except ValidationError:
        return _("Invalid address.")

    try:
        validate_email_allowed_in_realm(email)
    except DomainNotAllowedForRealmError:
        return _("Outside your domain.")
    except DisposableEmailError:
        return _("Please use your real email address.")
    except EmailContainsPlusError:
        return _("Email addresses containing + are not allowed.")

    return None


def email_reserved_for_system_bots_error(email: str) -> str:
    return f"{email} is reserved for system bots"


def get_existing_user_errors(
    target_realm: Realm,
    emails: Set[str],
    verbose: bool = False,
) -> Dict[str, Tuple[str, bool]]:
    """
    We use this function even for a list of one emails.

    It checks "new" emails to make sure that they don't
    already exist.  There's a bit of fiddly logic related
    to cross-realm bots and mirror dummies too.
    """

    errors: Dict[str, Tuple[str, bool]] = {}

    users = get_users_by_delivery_email(emails, target_realm).only(
        "delivery_email",
        "is_active",
        "is_mirror_dummy",
    )

    """
    A note on casing: We will preserve the casing used by
    the user for email in most of this code.  The only
    exception is when we do existence checks against
    the `user_dict` dictionary.  (We don't allow two
    users in the same realm to have the same effective
    delivery email.)
    """
    user_dict = {user.delivery_email.lower(): user for user in users}

    def process_email(email: str) -> None:
        if is_cross_realm_bot_email(email):
            if verbose:
                msg = email_reserved_for_system_bots_error(email)
            else:
                msg = _("Reserved for system bots.")
            deactivated = False
            errors[email] = (msg, deactivated)
            return

        existing_user_profile = user_dict.get(email.lower())

        if existing_user_profile is None:
            # HAPPY PATH!  Most people invite users that don't exist yet.
            return

        if existing_user_profile.is_mirror_dummy:
            if existing_user_profile.is_active:
                raise AssertionError("Mirror dummy user is already active!")
            return

        """
        Email has already been taken by a "normal" user.
        """
        deactivated = not existing_user_profile.is_active

        if existing_user_profile.is_active:
            if verbose:
                msg = _("{email} already has an account").format(email=email)
            else:
                msg = _("Already has an account.")
        else:
            msg = _("Account has been deactivated.")

        errors[email] = (msg, deactivated)

    for email in emails:
        process_email(email)

    return errors


def validate_email_not_already_in_realm(
    target_realm: Realm, email: str, verbose: bool = True
) -> None:
    """
    NOTE:
        Only use this to validate that a single email
        is not already used in the realm.

        We should start using bulk_check_new_emails()
        for any endpoint that takes multiple emails,
        such as the "invite" interface.
    """
    error_dict = get_existing_user_errors(target_realm, {email}, verbose)

    # Loop through errors, the only key should be our email.
    for key, error_info in error_dict.items():
        assert key == email
        msg, deactivated = error_info
        raise ValidationError(msg)

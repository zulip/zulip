from typing import Callable

from zerver.lib.name_restrictions import is_disposable_domain

# TODO: Move DisposableEmailError, etc. into here.
from zerver.models import (
    email_to_username,
    email_to_domain,
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    Realm,
    RealmDomain,
)

def validate_disposable(email: str) -> None:
    if is_disposable_domain(email_to_domain(email)):
        raise DisposableEmailError

def get_realm_email_validator(realm: Realm) -> Callable[[str], None]:
    if not realm.emails_restricted_to_domains:
        # Should we also do '+' check for non-resticted realms?
        if realm.disallow_disposable_email_addresses:
            return validate_disposable

        # allow any email through
        return lambda email: None

    '''
    RESTRICTIVE REALMS:

    Some realms only allow emails within a set
    of domains that are configured in RealmDomain.

    We get the set of domains up front so that
    folks can validate multiple emails without
    multiple round trips to the database.
    '''

    query = RealmDomain.objects.filter(realm=realm)
    rows = list(query.values('allow_subdomains', 'domain'))

    allowed_domains = {
        r['domain'] for r in rows
    }

    allowed_subdomains = {
        r['domain'] for r in rows
        if r['allow_subdomains']
    }

    def validate(email: str) -> None:
        '''
        We don't have to do a "disposable" check for restricted
        domains, since the realm is already giving us
        a small whitelist.
        '''

        if '+' in email_to_username(email):
            raise EmailContainsPlusError

        domain = email_to_domain(email)

        if domain in allowed_domains:
            return

        while len(domain) > 0:
            subdomain, sep, domain = domain.partition('.')
            if domain in allowed_subdomains:
                return

        raise DomainNotAllowedForRealmError

    return validate

# Is a user with the given email address allowed to be in the given realm?
# (This function does not check whether the user has been invited to the realm.
# So for invite-only realms, this is the test for whether a user can be invited,
# not whether the user can sign up currently.)
def email_allowed_for_realm(email: str, realm: Realm) -> None:
    '''
    Avoid calling this in a loop!
    Instead, call get_realm_email_validator()
    outside of the loop.
    '''
    get_realm_email_validator(realm)(email)

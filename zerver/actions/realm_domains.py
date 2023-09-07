from typing import Optional

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.actions.realm_settings import do_set_realm_property
from zerver.models import (
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmDomainDict,
    UserProfile,
    active_user_ids,
    get_realm_domains,
)
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_add_realm_domain(
    realm: Realm, domain: str, allow_subdomains: bool, *, acting_user: Optional[UserProfile]
) -> RealmDomain:
    realm_domain = RealmDomain.objects.create(
        realm=realm, domain=domain, allow_subdomains=allow_subdomains
    )
    added_domain = RealmDomainDict(domain=domain, allow_subdomains=allow_subdomains)

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_ADDED,
        event_time=timezone_now(),
        extra_data={
            "realm_domains": get_realm_domains(realm),
            "added_domain": added_domain,
        },
    )

    event = dict(
        type="realm_domains",
        op="add",
        realm_domain=RealmDomainDict(
            domain=realm_domain.domain, allow_subdomains=realm_domain.allow_subdomains
        ),
    )
    send_event_on_commit(realm, event, active_user_ids(realm.id))

    return realm_domain


@transaction.atomic(durable=True)
def do_change_realm_domain(
    realm_domain: RealmDomain, allow_subdomains: bool, *, acting_user: Optional[UserProfile]
) -> None:
    realm_domain.allow_subdomains = allow_subdomains
    realm_domain.save(update_fields=["allow_subdomains"])
    changed_domain = RealmDomainDict(
        domain=realm_domain.domain,
        allow_subdomains=realm_domain.allow_subdomains,
    )

    RealmAuditLog.objects.create(
        realm=realm_domain.realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_CHANGED,
        event_time=timezone_now(),
        extra_data={
            "realm_domains": get_realm_domains(realm_domain.realm),
            "changed_domain": changed_domain,
        },
    )

    event = dict(
        type="realm_domains",
        op="change",
        realm_domain=dict(
            domain=realm_domain.domain, allow_subdomains=realm_domain.allow_subdomains
        ),
    )
    send_event_on_commit(realm_domain.realm, event, active_user_ids(realm_domain.realm_id))


@transaction.atomic(durable=True)
def do_remove_realm_domain(
    realm_domain: RealmDomain, *, acting_user: Optional[UserProfile]
) -> None:
    realm = realm_domain.realm
    domain = realm_domain.domain
    realm_domain.delete()
    removed_domain = RealmDomainDict(
        domain=realm_domain.domain,
        allow_subdomains=realm_domain.allow_subdomains,
    )

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_REMOVED,
        event_time=timezone_now(),
        extra_data={
            "realm_domains": get_realm_domains(realm),
            "removed_domain": removed_domain,
        },
    )

    if not RealmDomain.objects.filter(realm=realm).exists() and realm.emails_restricted_to_domains:
        # If this was the last realm domain, we mark the realm as no
        # longer restricted to domain, because the feature doesn't do
        # anything if there are no domains, and this is probably less
        # confusing than the alternative.
        do_set_realm_property(realm, "emails_restricted_to_domains", False, acting_user=acting_user)
    event = dict(type="realm_domains", op="remove", domain=domain)
    send_event_on_commit(realm, event, active_user_ids(realm.id))

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.realm_domains import (
    do_add_realm_domain,
    do_change_realm_domain,
    do_remove_realm_domain,
)
from zerver.decorator import require_realm_owner
from zerver.lib.domains import validate_domain
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import RealmDomain, UserProfile
from zerver.models.realms import get_realm_domains


def list_realm_domains(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    domains = get_realm_domains(user_profile.realm)
    return json_success(request, data={"domains": domains})


@require_realm_owner
@typed_endpoint
def create_realm_domain(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    allow_subdomains: Json[bool],
    domain: str,
) -> HttpResponse:
    domain = domain.strip().lower()
    try:
        validate_domain(domain)
    except ValidationError as e:
        raise JsonableError(_("Invalid domain: {error}").format(error=e.messages[0]))
    if RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists():
        raise JsonableError(
            _("The domain {domain} is already a part of your organization.").format(domain=domain)
        )
    realm_domain = do_add_realm_domain(
        user_profile.realm, domain, allow_subdomains, acting_user=user_profile
    )
    return json_success(request, data={"new_domain": [realm_domain.id, realm_domain.domain]})


@require_realm_owner
@typed_endpoint
def patch_realm_domain(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    allow_subdomains: Json[bool],
    domain: PathOnly[str],
) -> HttpResponse:
    try:
        realm_domain = RealmDomain.objects.get(realm=user_profile.realm, domain=domain)
        do_change_realm_domain(realm_domain, allow_subdomains, acting_user=user_profile)
    except RealmDomain.DoesNotExist:
        raise JsonableError(_("No entry found for domain {domain}.").format(domain=domain))
    return json_success(request)


@require_realm_owner
@typed_endpoint
def delete_realm_domain(
    request: HttpRequest, user_profile: UserProfile, *, domain: PathOnly[str]
) -> HttpResponse:
    try:
        realm_domain = RealmDomain.objects.get(realm=user_profile.realm, domain=domain)
        do_remove_realm_domain(realm_domain, acting_user=user_profile)
    except RealmDomain.DoesNotExist:
        raise JsonableError(_("No entry found for domain {domain}.").format(domain=domain))
    return json_success(request)

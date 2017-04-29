from __future__ import absolute_import

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import has_request_variables, require_realm_admin, REQ
from zerver.lib.actions import do_add_realm_domain, do_change_realm_domain, \
    do_remove_realm_domain
from zerver.lib.domains import validate_domain
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_bool, check_string
from zerver.models import can_add_realm_domain, RealmDomain, UserProfile, \
    get_realm_domains

from typing import Text

def list_realm_domains(request, user_profile):
    # type: (HttpRequest, UserProfile) -> (HttpResponse)
    domains = get_realm_domains(user_profile.realm)
    return json_success({'domains': domains})

@require_realm_admin
@has_request_variables
def create_realm_domain(request, user_profile, domain=REQ(validator=check_string), allow_subdomains=REQ(validator=check_bool)):
    # type: (HttpRequest, UserProfile, Text, bool) -> (HttpResponse)
    domain = domain.strip().lower()
    try:
        validate_domain(domain)
    except ValidationError as e:
        return json_error(_('Invalid domain: {}').format(e.messages[0]))
    if RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists():
        return json_error(_("The domain %(domain)s is already a part of your organization.") % {'domain': domain})
    if not can_add_realm_domain(domain):
        return json_error(_("The domain %(domain)s belongs to another organization.") % {'domain': domain})
    realm_domain = do_add_realm_domain(user_profile.realm, domain, allow_subdomains)
    return json_success({'new_domain': [realm_domain.id, realm_domain.domain]})

@require_realm_admin
@has_request_variables
def patch_realm_domain(request, user_profile, domain, allow_subdomains=REQ(validator=check_bool)):
    # type: (HttpRequest, UserProfile, Text, bool) -> (HttpResponse)
    try:
        realm_domain = RealmDomain.objects.get(realm=user_profile.realm, domain=domain)
        do_change_realm_domain(realm_domain, allow_subdomains)
    except RealmDomain.DoesNotExist:
        return json_error(_('No entry found for domain %(domain)s.' % {'domain': domain}))
    return json_success()

@require_realm_admin
@has_request_variables
def delete_realm_domain(request, user_profile, domain):
    # type: (HttpRequest, UserProfile, Text) -> (HttpResponse)
    try:
        realm_domain = RealmDomain.objects.get(realm=user_profile.realm, domain=domain)
        do_remove_realm_domain(realm_domain)
    except RealmDomain.DoesNotExist:
        return json_error(_('No entry found for domain %(domain)s.' % {'domain': domain}))
    return json_success()

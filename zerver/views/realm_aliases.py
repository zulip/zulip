from __future__ import absolute_import

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import has_request_variables, require_realm_admin, REQ
from zerver.lib.actions import do_add_realm_alias, do_change_realm_alias, \
    do_remove_realm_alias, get_realm_aliases
from zerver.lib.domains import validate_domain
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_bool, check_string
from zerver.models import can_add_alias, RealmAlias, UserProfile

from typing import Text

def list_aliases(request, user_profile):
    # type: (HttpRequest, UserProfile) -> (HttpResponse)
    aliases = get_realm_aliases(user_profile.realm)
    return json_success({'domains': aliases})

@require_realm_admin
@has_request_variables
def create_alias(request, user_profile, domain=REQ(validator=check_string), allow_subdomains=REQ(validator=check_bool)):
    # type: (HttpRequest, UserProfile, Text, bool) -> (HttpResponse)
    domain = domain.strip().lower()
    try:
        validate_domain(domain)
    except ValidationError as e:
        return json_error(_('Invalid domain: {}').format(e.messages[0]))
    if RealmAlias.objects.filter(realm=user_profile.realm, domain=domain).exists():
        return json_error(_("The domain %(domain)s is already a part of your organization.") % {'domain': domain})
    if not can_add_alias(domain):
        return json_error(_("The domain %(domain)s belongs to another organization.") % {'domain': domain})
    alias = do_add_realm_alias(user_profile.realm, domain, allow_subdomains)
    return json_success({'new_domain': [alias.id, alias.domain]})

@require_realm_admin
@has_request_variables
def patch_alias(request, user_profile, domain, allow_subdomains=REQ(validator=check_bool)):
    # type: (HttpRequest, UserProfile, Text, bool) -> (HttpResponse)
    try:
        alias = RealmAlias.objects.get(realm=user_profile.realm, domain=domain)
        do_change_realm_alias(alias, allow_subdomains)
    except RealmAlias.DoesNotExist:
        return json_error(_('No entry found for domain %(domain)s.' % {'domain': domain}))
    return json_success()

@require_realm_admin
@has_request_variables
def delete_alias(request, user_profile, domain):
    # type: (HttpRequest, UserProfile, Text) -> (HttpResponse)
    try:
        alias = RealmAlias.objects.get(realm=user_profile.realm, domain=domain)
        do_remove_realm_alias(alias)
    except RealmAlias.DoesNotExist:
        return json_error(_('No entry found for domain %(domain)s.' % {'domain': domain}))
    return json_success()

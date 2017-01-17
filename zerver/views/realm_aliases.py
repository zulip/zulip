from __future__ import absolute_import

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import has_request_variables, REQ, require_realm_admin
from zerver.lib.actions import get_realm_aliases, do_add_realm_alias, \
    do_remove_realm_alias
from zerver.lib.response import json_error, json_success
from zerver.models import can_add_alias, RealmAlias, UserProfile

from typing import Text

def list_aliases(request, user_profile):
    # type: (HttpRequest, UserProfile) -> (HttpResponse)
    aliases = get_realm_aliases(user_profile.realm)
    return json_success({'domains': aliases})

@require_realm_admin
@has_request_variables
def create_alias(request, user_profile, domain=REQ()):
    # type: (HttpRequest, UserProfile, Text) -> (HttpResponse)
    if can_add_alias(domain):
        try:
            alias = do_add_realm_alias(user_profile.realm, domain)
        except ValidationError:
            return json_error(_('Domain can\'t be empty.'))
    else:
        return json_error(_('A Realm for this domain already exists.'))
    return json_success({'new_domain': [alias.id, alias.domain]})

@require_realm_admin
@has_request_variables
def delete_alias(request, user_profile, alias_id):
    # type: (HttpRequest, UserProfile, int) -> (HttpResponse)
    try:
        # Ensure alias_id is an integer. Django passes captured url parameters as strings.
        do_remove_realm_alias(user_profile.realm, int(alias_id))
    except RealmAlias.DoesNotExist:
        return json_error(_('No such entry found.'))
    return json_success()

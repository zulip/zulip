from __future__ import absolute_import

from typing import Text
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext as _

from zerver.decorator import has_request_variables, REQ, require_realm_admin
from zerver.lib.actions import do_add_realm_filter, do_remove_realm_filter
from zerver.lib.response import json_success, json_error
from zerver.lib.rest import rest_dispatch as _rest_dispatch
from zerver.lib.validator import check_string
from zerver.models import realm_filters_for_realm, UserProfile, RealmFilter


# Custom realm filters
def list_filters(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    filters = realm_filters_for_realm(user_profile.realm_id)
    return json_success({'filters': filters})


@require_realm_admin
@has_request_variables
def create_filter(request, user_profile, pattern=REQ(),
                  url_format_string=REQ()):
    # type: (HttpRequest, UserProfile, Text, Text) -> HttpResponse
    try:
        filter_id = do_add_realm_filter(
            realm=user_profile.realm,
            pattern=pattern,
            url_format_string=url_format_string
        )
        return json_success({'id': filter_id})
    except ValidationError as e:
        return json_error(e.messages[0], data={"errors": dict(e)})


@require_realm_admin
def delete_filter(request, user_profile, filter_id):
    # type: (HttpRequest, UserProfile, int) -> HttpResponse
    try:
        do_remove_realm_filter(realm=user_profile.realm, id=filter_id)
    except RealmFilter.DoesNotExist:
        return json_error(_('Filter not found'))
    return json_success()

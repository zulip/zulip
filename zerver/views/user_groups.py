from django.http import HttpResponse, HttpRequest
from django.utils.translation import ugettext as _

from typing import List, Text

from zerver.context_processors import get_realm_from_request
from zerver.lib.actions import check_add_user_group, do_update_user_group_name, \
    do_update_user_group_description
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.users import user_ids_to_users
from zerver.lib.validator import check_list, check_string, check_int, \
    check_short_string
from zerver.lib.user_groups import access_user_group_by_id
from zerver.models import UserProfile, UserGroup

@has_request_variables
def add_user_group(request, user_profile,
                   name=REQ(),
                   members=REQ(validator=check_list(check_int), default=[]),
                   description=REQ()):
    # type: (HttpRequest, UserProfile, Text, List[int], Text) -> HttpResponse
    user_profiles = user_ids_to_users(members, user_profile.realm)
    check_add_user_group(user_profile.realm, name, user_profiles, description)
    return json_success()

@has_request_variables
def edit_user_group(request, user_profile,
                    user_group_id=REQ(validator=check_int),
                    name=REQ(default=""), description=REQ(default="")):
    # type: (HttpRequest, UserProfile, int, Text, Text) -> HttpResponse
    if not (name or description):
        return json_error(_("No new data supplied"))

    user_group = access_user_group_by_id(user_group_id, realm=user_profile.realm)

    result = {}
    if name != user_group.name:
        do_update_user_group_name(user_group, name)
        result['name'] = _("Name successfully updated.")

    if description != user_group.description:
        do_update_user_group_description(user_group, description)
        result['description'] = _("Description successfully updated.")

    return json_success(result)

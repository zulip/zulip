from django.http import HttpResponse, HttpRequest
from django.utils.translation import ugettext as _

from typing import List, Text

from zerver.context_processors import get_realm_from_request
from zerver.lib.actions import check_add_user_group, do_update_user_group_name, \
    do_update_user_group_description, bulk_add_members_to_user_group, \
    remove_members_from_user_group, check_delete_user_group
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.users import user_ids_to_users
from zerver.lib.validator import check_list, check_string, check_int, \
    check_short_string
from zerver.lib.user_groups import access_user_group_by_id, get_memberships_of_users, get_user_group_members
from zerver.models import UserProfile, UserGroup, UserGroupMembership
from zerver.views.streams import compose_views, FuncKwargPair

@has_request_variables
def add_user_group(request: HttpRequest, user_profile: UserProfile,
                   name: Text=REQ(),
                   members: List[int]=REQ(validator=check_list(check_int), default=[]),
                   description: Text=REQ()) -> HttpResponse:
    user_profiles = user_ids_to_users(members, user_profile.realm)
    check_add_user_group(user_profile.realm, name, user_profiles, description)
    return json_success()

@has_request_variables
def edit_user_group(request: HttpRequest, user_profile: UserProfile,
                    user_group_id: int=REQ(validator=check_int),
                    name: Text=REQ(default=""), description: Text=REQ(default="")
                    ) -> HttpResponse:
    if not (name or description):
        return json_error(_("No new data supplied"))

    user_group = access_user_group_by_id(user_group_id, user_profile)

    result = {}
    if name != user_group.name:
        do_update_user_group_name(user_group, name)
        result['name'] = _("Name successfully updated.")

    if description != user_group.description:
        do_update_user_group_description(user_group, description)
        result['description'] = _("Description successfully updated.")

    return json_success(result)

@has_request_variables
def delete_user_group(request: HttpRequest, user_profile: UserProfile,
                      user_group_id: int=REQ(validator=check_int)) -> HttpResponse:

    check_delete_user_group(user_group_id, user_profile)
    return json_success()

@has_request_variables
def update_user_group_backend(request: HttpRequest, user_profile: UserProfile,
                              user_group_id: int=REQ(validator=check_int),
                              delete: List[int]=REQ(validator=check_list(check_int), default=[]),
                              add: List[int]=REQ(validator=check_list(check_int), default=[])
                              ) -> HttpResponse:
    if not add and not delete:
        return json_error(_('Nothing to do. Specify at least one of "add" or "delete".'))

    method_kwarg_pairs = [
        (add_members_to_group_backend,
         dict(user_group_id=user_group_id, members=add)),
        (remove_members_from_group_backend,
         dict(user_group_id=user_group_id, members=delete))
    ]  # type: List[FuncKwargPair]
    return compose_views(request, user_profile, method_kwarg_pairs)

def add_members_to_group_backend(request: HttpRequest, user_profile: UserProfile,
                                 user_group_id: int, members: List[int]) -> HttpResponse:
    if not members:
        return json_success()

    user_group = access_user_group_by_id(user_group_id, user_profile)
    user_profiles = user_ids_to_users(members, user_profile.realm)
    existing_member_ids = set(get_memberships_of_users(user_group, user_profiles))

    for user_profile in user_profiles:
        if user_profile.id in existing_member_ids:
            raise JsonableError(_("User %s is already a member of this group" % (user_profile.id,)))

    bulk_add_members_to_user_group(user_group, user_profiles)
    return json_success()

def remove_members_from_group_backend(request: HttpRequest, user_profile: UserProfile,
                                      user_group_id: int, members: List[int]) -> HttpResponse:
    if not members:
        return json_success()

    user_profiles = user_ids_to_users(members, user_profile.realm)
    user_group = access_user_group_by_id(user_group_id, user_profile)
    group_member_ids = get_user_group_members(user_group)
    for member in members:
        if (member not in group_member_ids):
            raise JsonableError(_("There is no member '%s' in this user group" % (member,)))

    remove_members_from_user_group(user_group, user_profiles)
    return json_success()

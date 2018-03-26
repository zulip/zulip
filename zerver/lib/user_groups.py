from __future__ import absolute_import

from collections import defaultdict
from django.db import transaction
from django.utils.translation import ugettext as _
from zerver.lib.exceptions import JsonableError
from zerver.models import UserProfile, Realm, UserGroupMembership, UserGroup
from typing import Dict, Iterable, List, Text, Tuple, Any

def access_user_group_by_id(user_group_id: int, user_profile: UserProfile) -> UserGroup:
    try:
        user_group = UserGroup.objects.get(id=user_group_id, realm=user_profile.realm)
        group_member_ids = get_user_group_members(user_group)
        msg = _("Only group members and organization administrators can administer this group.")
        if (not user_profile.is_realm_admin and user_profile.id not in group_member_ids):
            raise JsonableError(msg)
    except UserGroup.DoesNotExist:
        raise JsonableError(_("Invalid user group"))
    return user_group

def user_groups_in_realm(realm: Realm) -> List[UserGroup]:
    user_groups = UserGroup.objects.filter(realm=realm)
    return list(user_groups)

def user_groups_in_realm_serialized(realm: Realm) -> List[Dict[Text, Any]]:
    """This function is used in do_events_register code path so this code
    should be performant.  We need to do 2 database queries because
    Django's ORM doesn't properly support the left join between
    UserGroup and UserGroupMembership that we need.
    """
    realm_groups = UserGroup.objects.filter(realm=realm)
    group_dicts = {}  # type: Dict[str, Any]
    for user_group in realm_groups:
        group_dicts[user_group.id] = dict(
            id=user_group.id,
            name=user_group.name,
            description=user_group.description,
            members=[],
        )

    membership = UserGroupMembership.objects.filter(user_group__realm=realm).values_list(
        'user_group_id', 'user_profile_id')
    for (user_group_id, user_profile_id) in membership:
        group_dicts[user_group_id]['members'].append(user_profile_id)
    for group_dict in group_dicts.values():
        group_dict['members'] = sorted(group_dict['members'])

    return sorted(group_dicts.values(), key=lambda group_dict: group_dict['id'])

def get_user_groups(user_profile: UserProfile) -> List[UserGroup]:
    return list(user_profile.usergroup_set.all())

def check_add_user_to_user_group(user_profile: UserProfile, user_group: UserGroup) -> bool:
    member_obj, created = UserGroupMembership.objects.get_or_create(
        user_group=user_group, user_profile=user_profile)
    return created

def remove_user_from_user_group(user_profile: UserProfile, user_group: UserGroup) -> int:
    num_deleted, _ = UserGroupMembership.objects.filter(
        user_profile=user_profile, user_group=user_group).delete()
    return num_deleted

def check_remove_user_from_user_group(user_profile: UserProfile, user_group: UserGroup) -> bool:
    try:
        num_deleted = remove_user_from_user_group(user_profile, user_group)
        return bool(num_deleted)
    except Exception:
        return False

def create_user_group(name: Text, members: List[UserProfile], realm: Realm,
                      description: Text='') -> UserGroup:
    with transaction.atomic():
        user_group = UserGroup.objects.create(name=name, realm=realm,
                                              description=description)
        UserGroupMembership.objects.bulk_create([
            UserGroupMembership(user_profile=member, user_group=user_group)
            for member in members
        ])
        return user_group

def get_user_group_members(user_group: UserGroup) -> List[UserProfile]:
    members = UserGroupMembership.objects.filter(user_group=user_group)
    return [member.user_profile.id for member in members]

def get_memberships_of_users(user_group: UserGroup, members: List[UserProfile]) -> List[int]:
    return list(UserGroupMembership.objects.filter(
        user_group=user_group,
        user_profile__in=members).values_list('user_profile_id', flat=True))

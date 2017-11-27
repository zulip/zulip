from __future__ import absolute_import

from collections import defaultdict
from django.db import transaction
from django.utils.translation import ugettext as _
from zerver.lib.exceptions import JsonableError
from zerver.models import UserProfile, Realm, UserGroupMembership, UserGroup
from typing import Dict, Iterable, List, Text, Tuple, Any

def access_user_group_by_id(user_group_id: int, realm: Realm) -> UserGroup:
    try:
        user_group = UserGroup.objects.get(id=user_group_id, realm=realm)
    except UserGroup.DoesNotExist:
        raise JsonableError(_("Invalid user group"))
    return user_group

def user_groups_in_realm(realm: Realm) -> List[UserGroup]:
    user_groups = UserGroup.objects.filter(realm=realm)
    return list(user_groups)

def user_groups_in_realm_serialized(realm: Realm) -> List[Dict[Text, Any]]:
    """
    This function is used in do_events_register code path so this code should
    be performant. This is the reason why we get the groups through
    UserGroupMembership table. It gives us the groups and members in one query.
    """
    memberships = UserGroupMembership.objects.filter(user_group__realm=realm)
    memberships = memberships.select_related('user_group')
    groups = defaultdict(list)  # type: Dict[Tuple[int, Text, Text], List[int]]
    for membership in memberships:
        group = (membership.user_group.id,
                 membership.user_group.name,
                 membership.user_group.description)
        groups[group].append(membership.user_profile_id)

    user_groups = [dict(id=group[0],
                        name=group[1],
                        description=group[2],
                        members=sorted(members))
                   for group, members in groups.items()]
    user_groups.sort(key=lambda item: item['id'])
    return user_groups

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

def get_memberships_of_users(user_group: UserGroup, members: List[UserProfile]) -> List[int]:
    return list(UserGroupMembership.objects.filter(
        user_group=user_group,
        user_profile__in=members).values_list('user_profile_id', flat=True))

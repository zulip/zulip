from __future__ import absolute_import

from django.db import transaction
from zerver.models import UserProfile, Realm, UserGroupMembership, UserGroup
from typing import Dict, Iterable, List, Text

def user_groups_in_realm(realm):
    # type: (Realm) -> List[UserGroup]
    user_groups = UserGroup.objects.filter(realm=realm)
    return list(user_groups)

def get_user_groups(user_profile):
    # type: (UserProfile) -> List[UserGroup]
    return list(user_profile.usergroup_set.all())

def check_add_user_to_user_group(user_profile, user_group):
    # type: (UserProfile, UserGroup) -> bool
    member_obj, created = UserGroupMembership.objects.get_or_create(
        user_group=user_group, user_profile=user_profile)
    return created

def remove_user_from_user_group(user_profile, user_group):
    # type: (UserProfile, UserGroup) -> int
    num_deleted, _ = UserGroupMembership.objects.filter(
        user_profile=user_profile, user_group=user_group).delete()
    return num_deleted

def check_remove_user_from_user_group(user_profile, user_group):
    # type: (UserProfile, UserGroup) -> bool
    try:
        num_deleted = remove_user_from_user_group(user_profile, user_group)
        return bool(num_deleted)
    except Exception:
        return False

def create_user_group(name, members, realm):
    # type: (Text, List[UserProfile], Realm) -> UserGroup
    with transaction.atomic():
        user_group = UserGroup.objects.create(name=name, realm=realm)
        UserGroupMembership.objects.bulk_create([
            UserGroupMembership(user_profile=member, user_group=user_group)
            for member in members
        ])
        return user_group

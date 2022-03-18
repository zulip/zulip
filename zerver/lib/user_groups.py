from typing import Any, Dict, List

from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext as _
from django_cte import With

from zerver.lib.exceptions import JsonableError
from zerver.models import GroupGroupMembership, Realm, UserGroup, UserGroupMembership, UserProfile


def access_user_group_by_id(user_group_id: int, user_profile: UserProfile) -> UserGroup:
    try:
        user_group = UserGroup.objects.get(id=user_group_id, realm=user_profile.realm)
        if user_group.is_system_group:
            raise JsonableError(_("Insufficient permission"))
        group_member_ids = get_user_group_direct_members(user_group)
        if (
            not user_profile.is_realm_admin
            and not user_profile.is_moderator
            and user_profile.id not in group_member_ids
        ):
            raise JsonableError(_("Insufficient permission"))
    except UserGroup.DoesNotExist:
        raise JsonableError(_("Invalid user group"))
    return user_group


def user_groups_in_realm_serialized(realm: Realm) -> List[Dict[str, Any]]:
    """This function is used in do_events_register code path so this code
    should be performant.  We need to do 2 database queries because
    Django's ORM doesn't properly support the left join between
    UserGroup and UserGroupMembership that we need.
    """
    realm_groups = UserGroup.objects.filter(realm=realm)
    group_dicts: Dict[str, Any] = {}
    for user_group in realm_groups:
        group_dicts[user_group.id] = dict(
            id=user_group.id,
            name=user_group.name,
            description=user_group.description,
            members=[],
            is_system_group=user_group.is_system_group,
        )

    membership = UserGroupMembership.objects.filter(user_group__realm=realm).values_list(
        "user_group_id", "user_profile_id"
    )
    for (user_group_id, user_profile_id) in membership:
        group_dicts[user_group_id]["members"].append(user_profile_id)
    for group_dict in group_dicts.values():
        group_dict["members"] = sorted(group_dict["members"])

    return sorted(group_dicts.values(), key=lambda group_dict: group_dict["id"])


def get_direct_user_groups(user_profile: UserProfile) -> List[UserGroup]:
    return list(user_profile.direct_groups.all())


def remove_user_from_user_group(user_profile: UserProfile, user_group: UserGroup) -> int:
    num_deleted, _ = UserGroupMembership.objects.filter(
        user_profile=user_profile, user_group=user_group
    ).delete()
    return num_deleted


def create_user_group(
    name: str,
    members: List[UserProfile],
    realm: Realm,
    *,
    description: str = "",
    is_system_group: bool = False,
) -> UserGroup:
    with transaction.atomic():
        user_group = UserGroup.objects.create(
            name=name, realm=realm, description=description, is_system_group=is_system_group
        )
        UserGroupMembership.objects.bulk_create(
            UserGroupMembership(user_profile=member, user_group=user_group) for member in members
        )
        return user_group


def get_user_group_direct_members(user_group: UserGroup) -> List[int]:
    return UserGroupMembership.objects.filter(user_group=user_group).values_list(
        "user_profile_id", flat=True
    )


def get_direct_memberships_of_users(user_group: UserGroup, members: List[UserProfile]) -> List[int]:
    return list(
        UserGroupMembership.objects.filter(
            user_group=user_group, user_profile__in=members
        ).values_list("user_profile_id", flat=True)
    )


# These recursive lookups use standard PostgreSQL common table
# expression (CTE) queries. These queries use the django-cte library,
# because upstream Django does not yet support CTE.
#
# https://www.postgresql.org/docs/current/queries-with.html
# https://pypi.org/project/django-cte/
# https://code.djangoproject.com/ticket/28919


def get_recursive_subgroups(user_group: UserGroup) -> "QuerySet[UserGroup]":
    cte = With.recursive(
        lambda cte: UserGroup.objects.filter(id=user_group.id)
        .values("id")
        .union(cte.join(UserGroup, direct_supergroups=cte.col.id).values("id"))
    )
    return cte.join(UserGroup, id=cte.col.id).with_cte(cte)


def get_recursive_group_members(user_group: UserGroup) -> "QuerySet[UserProfile]":
    return UserProfile.objects.filter(direct_groups__in=get_recursive_subgroups(user_group))


def get_recursive_membership_groups(user_profile: UserProfile) -> "QuerySet[UserGroup]":
    cte = With.recursive(
        lambda cte: user_profile.direct_groups.values("id").union(
            cte.join(UserGroup, direct_subgroups=cte.col.id).values("id")
        )
    )
    return cte.join(UserGroup, id=cte.col.id).with_cte(cte)


def create_system_user_groups_for_realm(realm: Realm) -> Dict[int, UserGroup]:
    """Any changes to this function likely require a migration to adjust
    existing realms.  See e.g. migration 0375_create_role_based_system_groups.py,
    which is a copy of this function from when we introduced system groups.
    """
    role_system_groups_dict: Dict[int, UserGroup] = {}
    for role in UserGroup.SYSTEM_USER_GROUP_ROLE_MAP.keys():
        user_group_params = UserGroup.SYSTEM_USER_GROUP_ROLE_MAP[role]
        user_group = UserGroup(
            name=user_group_params["name"],
            description=user_group_params["description"],
            realm=realm,
            is_system_group=True,
        )
        role_system_groups_dict[role] = user_group

    full_members_system_group = UserGroup(
        name="@role:fullmembers",
        description="Members of this organization, not including new accounts and guests",
        realm=realm,
        is_system_group=True,
    )
    everyone_on_internet_system_group = UserGroup(
        name="@role:internet",
        description="Everyone on the Internet",
        realm=realm,
        is_system_group=True,
    )
    # Order of this list here is important to create correct GroupGroupMembership objects
    system_user_groups_list = [
        role_system_groups_dict[UserProfile.ROLE_REALM_OWNER],
        role_system_groups_dict[UserProfile.ROLE_REALM_ADMINISTRATOR],
        role_system_groups_dict[UserProfile.ROLE_MODERATOR],
        full_members_system_group,
        role_system_groups_dict[UserProfile.ROLE_MEMBER],
        role_system_groups_dict[UserProfile.ROLE_GUEST],
        everyone_on_internet_system_group,
    ]

    UserGroup.objects.bulk_create(system_user_groups_list)

    subgroup_objects = []
    subgroup, remaining_groups = system_user_groups_list[0], system_user_groups_list[1:]
    for supergroup in remaining_groups:
        subgroup_objects.append(GroupGroupMembership(subgroup=subgroup, supergroup=supergroup))
        subgroup = supergroup

    GroupGroupMembership.objects.bulk_create(subgroup_objects)

    return role_system_groups_dict


def get_system_user_group_for_user(user_profile: UserProfile) -> UserGroup:
    system_user_group_name = UserGroup.SYSTEM_USER_GROUP_ROLE_MAP[user_profile.role]["name"]

    system_user_group = UserGroup.objects.get(
        name=system_user_group_name, realm=user_profile.realm, is_system_group=True
    )
    return system_user_group

from typing import Dict, Iterable, List, Sequence, TypedDict

from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext as _
from django_cte import With
from django_stubs_ext import ValuesQuerySet

from zerver.lib.exceptions import JsonableError
from zerver.models import GroupGroupMembership, Realm, UserGroup, UserGroupMembership, UserProfile


class UserGroupDict(TypedDict):
    id: int
    name: str
    description: str
    members: List[int]
    direct_subgroup_ids: List[int]
    is_system_group: bool


def access_user_group_by_id(
    user_group_id: int, user_profile: UserProfile, *, for_read: bool = False
) -> UserGroup:
    try:
        user_group = UserGroup.objects.get(id=user_group_id, realm=user_profile.realm)
        if for_read and not user_profile.is_guest:
            # Everyone is allowed to read a user group and check who
            # are its members. Guests should be unable to reach this
            # code path, since they can't access user groups API
            # endpoints, but we check for guests here for defense in
            # depth.
            return user_group
        if user_group.is_system_group:
            raise JsonableError(_("Insufficient permission"))
        group_member_ids = get_user_group_direct_member_ids(user_group)
        if (
            not user_profile.is_realm_admin
            and not user_profile.is_moderator
            and user_profile.id not in group_member_ids
        ):
            raise JsonableError(_("Insufficient permission"))
    except UserGroup.DoesNotExist:
        raise JsonableError(_("Invalid user group"))
    return user_group


def access_user_groups_as_potential_subgroups(
    user_group_ids: Sequence[int], acting_user: UserProfile
) -> List[UserGroup]:
    user_groups = UserGroup.objects.filter(id__in=user_group_ids, realm=acting_user.realm)

    valid_group_ids = [group.id for group in user_groups]
    invalid_group_ids = [group_id for group_id in user_group_ids if group_id not in valid_group_ids]
    if invalid_group_ids:
        raise JsonableError(_("Invalid user group ID: {}").format(invalid_group_ids[0]))

    return list(user_groups)


def user_groups_in_realm_serialized(realm: Realm) -> List[UserGroupDict]:
    """This function is used in do_events_register code path so this code
    should be performant.  We need to do 2 database queries because
    Django's ORM doesn't properly support the left join between
    UserGroup and UserGroupMembership that we need.
    """
    realm_groups = UserGroup.objects.filter(realm=realm)
    group_dicts: Dict[int, UserGroupDict] = {}
    for user_group in realm_groups:
        group_dicts[user_group.id] = dict(
            id=user_group.id,
            name=user_group.name,
            description=user_group.description,
            members=[],
            direct_subgroup_ids=[],
            is_system_group=user_group.is_system_group,
        )

    membership = UserGroupMembership.objects.filter(user_group__realm=realm).values_list(
        "user_group_id", "user_profile_id"
    )
    for user_group_id, user_profile_id in membership:
        group_dicts[user_group_id]["members"].append(user_profile_id)

    group_membership = GroupGroupMembership.objects.filter(subgroup__realm=realm).values_list(
        "subgroup_id", "supergroup_id"
    )
    for subgroup_id, supergroup_id in group_membership:
        group_dicts[supergroup_id]["direct_subgroup_ids"].append(subgroup_id)

    for group_dict in group_dicts.values():
        group_dict["members"] = sorted(group_dict["members"])
        group_dict["direct_subgroup_ids"] = sorted(group_dict["direct_subgroup_ids"])

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


def get_user_group_direct_member_ids(
    user_group: UserGroup,
) -> ValuesQuerySet[UserGroupMembership, int]:
    return UserGroupMembership.objects.filter(user_group=user_group).values_list(
        "user_profile_id", flat=True
    )


def get_user_group_direct_members(user_group: UserGroup) -> QuerySet[UserProfile]:
    return user_group.direct_members.all()


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


def get_recursive_subgroups(user_group: UserGroup) -> QuerySet[UserGroup]:
    cte = With.recursive(
        lambda cte: UserGroup.objects.filter(id=user_group.id)
        .values("id")
        .union(cte.join(UserGroup, direct_supergroups=cte.col.id).values("id"))
    )
    return cte.join(UserGroup, id=cte.col.id).with_cte(cte)


def get_recursive_group_members(user_group: UserGroup) -> QuerySet[UserProfile]:
    return UserProfile.objects.filter(direct_groups__in=get_recursive_subgroups(user_group))


def get_recursive_membership_groups(user_profile: UserProfile) -> QuerySet[UserGroup]:
    cte = With.recursive(
        lambda cte: user_profile.direct_groups.values("id").union(
            cte.join(UserGroup, direct_subgroups=cte.col.id).values("id")
        )
    )
    return cte.join(UserGroup, id=cte.col.id).with_cte(cte)


def is_user_in_group(
    user_group: UserGroup, user: UserProfile, *, direct_member_only: bool = False
) -> bool:
    if direct_member_only:
        return get_user_group_direct_members(user_group=user_group).filter(id=user.id).exists()

    return get_recursive_group_members(user_group=user_group).filter(id=user.id).exists()


def get_user_group_member_ids(
    user_group: UserGroup, *, direct_member_only: bool = False
) -> List[int]:
    if direct_member_only:
        member_ids: Iterable[int] = get_user_group_direct_member_ids(user_group)
    else:
        member_ids = get_recursive_group_members(user_group).values_list("id", flat=True)

    return list(member_ids)


def get_subgroup_ids(user_group: UserGroup, *, direct_subgroup_only: bool = False) -> List[int]:
    if direct_subgroup_only:
        subgroup_ids = user_group.direct_subgroups.all().values_list("id", flat=True)
    else:
        subgroup_ids = (
            get_recursive_subgroups(user_group)
            .exclude(id=user_group.id)
            .values_list("id", flat=True)
        )

    return list(subgroup_ids)


def create_system_user_groups_for_realm(realm: Realm) -> Dict[int, UserGroup]:
    """Any changes to this function likely require a migration to adjust
    existing realms.  See e.g. migration 0382_create_role_based_system_groups.py,
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
        name=UserGroup.FULL_MEMBERS_GROUP_NAME,
        description="Members of this organization, not including new accounts and guests",
        realm=realm,
        is_system_group=True,
    )
    everyone_on_internet_system_group = UserGroup(
        name=UserGroup.EVERYONE_ON_INTERNET_GROUP_NAME,
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

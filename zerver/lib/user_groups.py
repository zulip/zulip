from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import TypedDict

from django.conf import settings
from django.db import connection, transaction
from django.db.models import F, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django_cte import With
from psycopg2.sql import SQL, Literal

from zerver.lib.exceptions import (
    JsonableError,
    PreviousSettingValueMismatchedError,
    SystemGroupRequiredError,
)
from zerver.lib.types import GroupPermissionSetting, ServerSupportedPermissionSettings
from zerver.models import (
    GroupGroupMembership,
    NamedUserGroup,
    Realm,
    RealmAuditLog,
    Stream,
    UserGroup,
    UserGroupMembership,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realm_audit_logs import AuditLogEventType


@dataclass
class AnonymousSettingGroupDict:
    direct_members: list[int]
    direct_subgroups: list[int]


@dataclass
class GroupSettingChangeRequest:
    new: int | AnonymousSettingGroupDict
    old: int | AnonymousSettingGroupDict | None = None


class UserGroupDict(TypedDict):
    id: int
    name: str
    description: str
    members: list[int]
    direct_subgroup_ids: list[int]
    is_system_group: bool
    can_manage_group: int | AnonymousSettingGroupDict
    can_mention_group: int | AnonymousSettingGroupDict


@dataclass
class LockedUserGroupContext:
    """User groups in this dataclass are guaranteeed to be locked until the
    end of the current transaction.

    supergroup is the user group to have subgroups added or removed;
    direct_subgroups are user groups that are recursively queried for subgroups;
    recursive_subgroups include direct_subgroups and their descendants.
    """

    supergroup: NamedUserGroup
    direct_subgroups: list[NamedUserGroup]
    recursive_subgroups: list[NamedUserGroup]


def has_user_group_access(
    user_group: NamedUserGroup, user_profile: UserProfile, *, for_read: bool, as_subgroup: bool
) -> bool:
    if user_group.realm_id != user_profile.realm_id:
        return False

    if as_subgroup:
        # At this time, we only check for realm ID of a potential subgroup.
        return True

    if for_read and not user_profile.is_guest:
        # Everyone is allowed to read a user group and check who
        # are its members. Guests should be unable to reach this
        # code path, since they can't access user groups API
        # endpoints, but we check for guests here for defense in
        # depth.
        return True

    if user_group.is_system_group:
        return False

    can_edit_all_user_groups = user_profile.can_edit_all_user_groups()

    group_member_ids = get_user_group_direct_member_ids(user_group)
    if (
        not user_profile.is_realm_admin
        and not user_profile.is_moderator
        and user_profile.id not in group_member_ids
    ):
        can_edit_all_user_groups = False

    if can_edit_all_user_groups:
        return True

    return is_user_in_group(user_group.can_manage_group, user_profile)


def access_user_group_by_id(
    user_group_id: int, user_profile: UserProfile, *, for_read: bool
) -> NamedUserGroup:
    try:
        if for_read:
            user_group = NamedUserGroup.objects.get(id=user_group_id, realm=user_profile.realm)
        else:
            user_group = NamedUserGroup.objects.select_for_update().get(
                id=user_group_id, realm=user_profile.realm
            )
    except NamedUserGroup.DoesNotExist:
        raise JsonableError(_("Invalid user group"))

    if not has_user_group_access(user_group, user_profile, for_read=for_read, as_subgroup=False):
        raise JsonableError(_("Insufficient permission"))

    return user_group


@contextmanager
def lock_subgroups_with_respect_to_supergroup(
    potential_subgroup_ids: Collection[int], potential_supergroup_id: int, acting_user: UserProfile
) -> Iterator[LockedUserGroupContext]:
    """This locks the user groups with the given potential_subgroup_ids, as well
    as their indirect subgroups, followed by the potential supergroup. It
    ensures that we lock the user groups in a consistent order topologically to
    avoid unnecessary deadlocks on non-conflicting queries.

    Regardless of whether the user groups returned are used, always call this
    helper before making changes to subgroup memberships. This avoids
    introducing cycles among user groups when there is a race condition in
    which one of these subgroups become an ancestor of the parent user group in
    another transaction.

    Note that it only does a permission check on the potential supergroup,
    not the potential subgroups or their recursive subgroups.
    """
    with transaction.atomic(savepoint=False):
        # Calling list with the QuerySet forces its evaluation putting a lock on
        # the queried rows.
        recursive_subgroups = list(
            get_recursive_subgroups_for_groups(
                potential_subgroup_ids, acting_user.realm
            ).select_for_update(nowait=True)
        )
        # TODO: This select_for_update query is subject to deadlocking, and
        # better error handling is needed. We may use
        # select_for_update(nowait=True) and release the locks held by ending
        # the transaction with a JsonableError by handling the DatabaseError.
        # But at the current scale of concurrent requests, we rely on
        # Postgres's deadlock detection when it occurs.
        potential_supergroup = access_user_group_by_id(
            potential_supergroup_id, acting_user, for_read=False
        )
        # We avoid making a separate query for user_group_ids because the
        # recursive query already returns those user groups.
        potential_subgroups = [
            user_group
            for user_group in recursive_subgroups
            if user_group.id in potential_subgroup_ids
        ]

        # We expect that the passed user_group_ids each corresponds to an
        # existing user group.
        group_ids_found = [group.id for group in potential_subgroups]
        group_ids_not_found = [
            group_id for group_id in potential_subgroup_ids if group_id not in group_ids_found
        ]
        if group_ids_not_found:
            raise JsonableError(
                _("Invalid user group ID: {group_id}").format(group_id=group_ids_not_found[0])
            )

        for subgroup in potential_subgroups:
            # At this time, we only do a check on the realm ID of the fetched
            # subgroup. This would be caught by the check earlier, so there is
            # no coverage here.
            if not has_user_group_access(subgroup, acting_user, for_read=False, as_subgroup=True):
                raise JsonableError(_("Insufficient permission"))  # nocoverage

        yield LockedUserGroupContext(
            direct_subgroups=potential_subgroups,
            recursive_subgroups=recursive_subgroups,
            supergroup=potential_supergroup,
        )


def check_setting_configuration_for_system_groups(
    setting_group: NamedUserGroup,
    setting_name: str,
    permission_configuration: GroupPermissionSetting,
) -> None:
    if setting_name != "can_mention_group" and (
        not settings.ALLOW_GROUP_VALUED_SETTINGS and not setting_group.is_system_group
    ):
        raise SystemGroupRequiredError(setting_name)

    if permission_configuration.require_system_group and not setting_group.is_system_group:
        raise SystemGroupRequiredError(setting_name)

    if (
        not permission_configuration.allow_internet_group
        and setting_group.name == SystemGroups.EVERYONE_ON_INTERNET
    ):
        raise JsonableError(
            _("'{setting_name}' setting cannot be set to 'role:internet' group.").format(
                setting_name=setting_name
            )
        )

    if (
        not permission_configuration.allow_owners_group
        and setting_group.name == SystemGroups.OWNERS
    ):
        raise JsonableError(
            _("'{setting_name}' setting cannot be set to 'role:owners' group.").format(
                setting_name=setting_name
            )
        )

    if (
        not permission_configuration.allow_nobody_group
        and setting_group.name == SystemGroups.NOBODY
    ):
        raise JsonableError(
            _("'{setting_name}' setting cannot be set to 'role:nobody' group.").format(
                setting_name=setting_name
            )
        )

    if (
        not permission_configuration.allow_everyone_group
        and setting_group.name == SystemGroups.EVERYONE
    ):
        raise JsonableError(
            _("'{setting_name}' setting cannot be set to 'role:everyone' group.").format(
                setting_name=setting_name
            )
        )

    if (
        permission_configuration.allowed_system_groups
        and setting_group.name not in permission_configuration.allowed_system_groups
    ):
        raise JsonableError(
            _("'{setting_name}' setting cannot be set to '{group_name}' group.").format(
                setting_name=setting_name, group_name=setting_group.name
            )
        )


def update_or_create_user_group_for_setting(
    realm: Realm,
    direct_members: list[int],
    direct_subgroups: list[int],
    current_setting_value: UserGroup | None,
) -> UserGroup:
    if current_setting_value is not None and not hasattr(current_setting_value, "named_user_group"):
        # We do not create a new group if the setting was already set
        # to an anonymous group. The memberships of existing group
        # itself are updated.
        user_group = current_setting_value
    else:
        user_group = UserGroup.objects.create(realm=realm)

    from zerver.lib.users import user_ids_to_users

    member_users = user_ids_to_users(direct_members, realm)
    user_group.direct_members.set(member_users)

    potential_subgroups = NamedUserGroup.objects.filter(realm=realm, id__in=direct_subgroups)
    group_ids_found = [group.id for group in potential_subgroups]
    group_ids_not_found = [
        group_id for group_id in direct_subgroups if group_id not in group_ids_found
    ]
    if group_ids_not_found:
        raise JsonableError(
            _("Invalid user group ID: {group_id}").format(group_id=group_ids_not_found[0])
        )

    user_group.direct_subgroups.set(group_ids_found)

    return user_group


def access_user_group_for_setting(
    setting_user_group: int | AnonymousSettingGroupDict,
    user_profile: UserProfile,
    *,
    setting_name: str,
    permission_configuration: GroupPermissionSetting,
    current_setting_value: UserGroup | None = None,
) -> UserGroup:
    if isinstance(setting_user_group, int):
        named_user_group = access_user_group_by_id(setting_user_group, user_profile, for_read=True)
        check_setting_configuration_for_system_groups(
            named_user_group, setting_name, permission_configuration
        )
        return named_user_group.usergroup_ptr

    if permission_configuration.require_system_group:
        raise SystemGroupRequiredError(setting_name)

    user_group = update_or_create_user_group_for_setting(
        user_profile.realm,
        setting_user_group.direct_members,
        setting_user_group.direct_subgroups,
        current_setting_value,
    )

    return user_group


def check_user_group_name(group_name: str) -> str:
    if group_name.strip() == "":
        raise JsonableError(_("User group name can't be empty!"))

    if len(group_name) > NamedUserGroup.MAX_NAME_LENGTH:
        raise JsonableError(
            _("User group name cannot exceed {max_length} characters.").format(
                max_length=NamedUserGroup.MAX_NAME_LENGTH
            )
        )

    for invalid_prefix in NamedUserGroup.INVALID_NAME_PREFIXES:
        if group_name.startswith(invalid_prefix):
            raise JsonableError(
                _("User group name cannot start with '{prefix}'.").format(prefix=invalid_prefix)
            )

    return group_name


def get_group_setting_value_for_api(
    setting_value_group: UserGroup,
) -> int | AnonymousSettingGroupDict:
    if hasattr(setting_value_group, "named_user_group"):
        return setting_value_group.id

    return AnonymousSettingGroupDict(
        direct_members=[member.id for member in setting_value_group.direct_members.all()],
        direct_subgroups=[subgroup.id for subgroup in setting_value_group.direct_subgroups.all()],
    )


def get_setting_value_for_user_group_object(
    setting_value_group: UserGroup,
    direct_members_dict: dict[int, list[int]],
    direct_subgroups_dict: dict[int, list[int]],
) -> int | AnonymousSettingGroupDict:
    if hasattr(setting_value_group, "named_user_group"):
        return setting_value_group.id

    direct_members = []
    if setting_value_group.id in direct_members_dict:
        direct_members = direct_members_dict[setting_value_group.id]

    direct_subgroups = []
    if setting_value_group.id in direct_subgroups_dict:
        direct_subgroups = direct_subgroups_dict[setting_value_group.id]

    return AnonymousSettingGroupDict(
        direct_members=direct_members,
        direct_subgroups=direct_subgroups,
    )


def user_groups_in_realm_serialized(realm: Realm) -> list[UserGroupDict]:
    """This function is used in do_events_register code path so this code
    should be performant.  We need to do 2 database queries because
    Django's ORM doesn't properly support the left join between
    UserGroup and UserGroupMembership that we need.
    """
    realm_groups = NamedUserGroup.objects.select_related(
        "can_manage_group",
        "can_manage_group__named_user_group",
        "can_mention_group",
        "can_mention_group__named_user_group",
    ).filter(realm=realm)

    membership = UserGroupMembership.objects.filter(user_group__realm=realm).values_list(
        "user_group_id", "user_profile_id"
    )

    group_membership = GroupGroupMembership.objects.filter(subgroup__realm=realm).values_list(
        "subgroup_id", "supergroup_id"
    )

    group_members = defaultdict(list)
    for user_group_id, user_profile_id in membership:
        group_members[user_group_id].append(user_profile_id)

    group_subgroups = defaultdict(list)
    for subgroup_id, supergroup_id in group_membership:
        group_subgroups[supergroup_id].append(subgroup_id)

    group_dicts: dict[int, UserGroupDict] = {}
    for user_group in realm_groups:
        direct_member_ids = []
        if user_group.id in group_members:
            direct_member_ids = group_members[user_group.id]

        direct_subgroup_ids = []
        if user_group.id in group_subgroups:
            direct_subgroup_ids = group_subgroups[user_group.id]

        group_dicts[user_group.id] = dict(
            id=user_group.id,
            name=user_group.name,
            description=user_group.description,
            members=direct_member_ids,
            direct_subgroup_ids=direct_subgroup_ids,
            is_system_group=user_group.is_system_group,
            can_manage_group=get_setting_value_for_user_group_object(
                user_group.can_manage_group, group_members, group_subgroups
            ),
            can_mention_group=get_setting_value_for_user_group_object(
                user_group.can_mention_group, group_members, group_subgroups
            ),
        )

    for group_dict in group_dicts.values():
        group_dict["members"] = sorted(group_dict["members"])
        group_dict["direct_subgroup_ids"] = sorted(group_dict["direct_subgroup_ids"])

    return sorted(group_dicts.values(), key=lambda group_dict: group_dict["id"])


def get_direct_user_groups(user_profile: UserProfile) -> list[UserGroup]:
    return list(user_profile.direct_groups.all())


def get_user_group_direct_member_ids(
    user_group: UserGroup,
) -> QuerySet[UserGroupMembership, int]:
    return UserGroupMembership.objects.filter(user_group=user_group).values_list(
        "user_profile_id", flat=True
    )


def get_user_group_direct_members(user_group: UserGroup) -> QuerySet[UserProfile]:
    return user_group.direct_members.all()


def get_direct_memberships_of_users(user_group: UserGroup, members: list[UserProfile]) -> list[int]:
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
        .values(group_id=F("id"))
        .union(
            cte.join(NamedUserGroup, direct_supergroups=cte.col.group_id).values(group_id=F("id"))
        )
    )
    return cte.join(UserGroup, id=cte.col.group_id).with_cte(cte)


def get_recursive_strict_subgroups(user_group: UserGroup) -> QuerySet[NamedUserGroup]:
    # Same as get_recursive_subgroups but does not include the
    # user_group passed.
    direct_subgroup_ids = user_group.direct_subgroups.all().values("id")
    cte = With.recursive(
        lambda cte: NamedUserGroup.objects.filter(id__in=direct_subgroup_ids)
        .values(group_id=F("id"))
        .union(
            cte.join(NamedUserGroup, direct_supergroups=cte.col.group_id).values(group_id=F("id"))
        )
    )
    return cte.join(NamedUserGroup, id=cte.col.group_id).with_cte(cte)


def get_recursive_group_members(user_group: UserGroup) -> QuerySet[UserProfile]:
    return UserProfile.objects.filter(direct_groups__in=get_recursive_subgroups(user_group))


def get_recursive_membership_groups(user_profile: UserProfile) -> QuerySet[UserGroup]:
    cte = With.recursive(
        lambda cte: user_profile.direct_groups.values(group_id=F("id")).union(
            cte.join(UserGroup, direct_subgroups=cte.col.group_id).values(group_id=F("id"))
        )
    )
    return cte.join(UserGroup, id=cte.col.group_id).with_cte(cte)


def is_user_in_group(
    user_group: UserGroup, user: UserProfile, *, direct_member_only: bool = False
) -> bool:
    if direct_member_only:
        return get_user_group_direct_members(user_group=user_group).filter(id=user.id).exists()

    return get_recursive_group_members(user_group=user_group).filter(id=user.id).exists()


def is_any_user_in_group(
    user_group: UserGroup, user_ids: Iterable[int], *, direct_member_only: bool = False
) -> bool:
    if direct_member_only:
        return get_user_group_direct_members(user_group=user_group).filter(id__in=user_ids).exists()

    return get_recursive_group_members(user_group=user_group).filter(id__in=user_ids).exists()


def get_user_group_member_ids(
    user_group: UserGroup, *, direct_member_only: bool = False
) -> list[int]:
    if direct_member_only:
        member_ids: Iterable[int] = get_user_group_direct_member_ids(user_group)
    else:
        member_ids = get_recursive_group_members(user_group).values_list("id", flat=True)

    return list(member_ids)


def get_subgroup_ids(user_group: UserGroup, *, direct_subgroup_only: bool = False) -> list[int]:
    if direct_subgroup_only:
        subgroup_ids = user_group.direct_subgroups.all().values_list("id", flat=True)
    else:
        subgroup_ids = get_recursive_strict_subgroups(user_group).values_list("id", flat=True)

    return list(subgroup_ids)


def get_recursive_subgroups_for_groups(
    user_group_ids: Iterable[int], realm: Realm
) -> QuerySet[NamedUserGroup]:
    cte = With.recursive(
        lambda cte: NamedUserGroup.objects.filter(id__in=user_group_ids, realm=realm)
        .values(group_id=F("id"))
        .union(
            cte.join(NamedUserGroup, direct_supergroups=cte.col.group_id).values(group_id=F("id"))
        )
    )
    recursive_subgroups = cte.join(NamedUserGroup, id=cte.col.group_id).with_cte(cte)
    return recursive_subgroups


def get_role_based_system_groups_dict(realm: Realm) -> dict[str, NamedUserGroup]:
    system_groups = NamedUserGroup.objects.filter(realm=realm, is_system_group=True).select_related(
        "usergroup_ptr"
    )
    system_groups_name_dict = {}
    for group in system_groups:
        system_groups_name_dict[group.name] = group

    return system_groups_name_dict


def set_defaults_for_group_settings(
    user_group: NamedUserGroup,
    group_settings_map: Mapping[str, UserGroup],
    system_groups_name_dict: dict[str, NamedUserGroup],
) -> NamedUserGroup:
    for setting_name, permission_config in NamedUserGroup.GROUP_PERMISSION_SETTINGS.items():
        if setting_name in group_settings_map:
            # We skip the settings for which a value is passed
            # in user group creation API request.
            continue

        if user_group.is_system_group and permission_config.default_for_system_groups is not None:
            default_group_name = permission_config.default_for_system_groups
        else:
            default_group_name = permission_config.default_group_name

        default_group = system_groups_name_dict[default_group_name].usergroup_ptr
        setattr(user_group, setting_name, default_group)

    return user_group


def bulk_create_system_user_groups(groups: list[dict[str, str]], realm: Realm) -> None:
    # This value will be used to set the temporary initial value for different
    # settings since we can only set them to the correct values after the groups
    # are created.
    initial_group_setting_value = -1

    rows = [SQL("({})").format(Literal(realm.id))] * len(groups)
    query = SQL(
        """
        INSERT INTO zerver_usergroup (realm_id)
        VALUES {rows}
        RETURNING id
        """
    ).format(rows=SQL(", ").join(rows))
    with connection.cursor() as cursor:
        cursor.execute(query)
        user_group_ids = [id for (id,) in cursor.fetchall()]

    rows = [
        SQL("({},{},{},{},{},{},{})").format(
            Literal(user_group_ids[idx]),
            Literal(realm.id),
            Literal(group["name"]),
            Literal(group["description"]),
            Literal(True),
            Literal(initial_group_setting_value),
            Literal(initial_group_setting_value),
        )
        for idx, group in enumerate(groups)
    ]
    query = SQL(
        """
        INSERT INTO zerver_namedusergroup (usergroup_ptr_id, realm_id, name, description, is_system_group, can_manage_group_id, can_mention_group_id)
        VALUES {rows}
        """
    ).format(rows=SQL(", ").join(rows))
    with connection.cursor() as cursor:
        cursor.execute(query)


@transaction.atomic(savepoint=False)
def create_system_user_groups_for_realm(realm: Realm) -> dict[int, NamedUserGroup]:
    """Any changes to this function likely require a migration to adjust
    existing realms.  See e.g. migration 0382_create_role_based_system_groups.py,
    which is a copy of this function from when we introduced system groups.
    """
    role_system_groups_dict: dict[int, NamedUserGroup] = {}

    system_groups_info_list: list[dict[str, str]] = []

    nobody_group_info = {
        "name": SystemGroups.NOBODY,
        "description": "Nobody",
    }

    full_members_group_info = {
        "name": SystemGroups.FULL_MEMBERS,
        "description": "Members of this organization, not including new accounts and guests",
    }

    everyone_on_internet_group_info = {
        "name": SystemGroups.EVERYONE_ON_INTERNET,
        "description": "Everyone on the Internet",
    }

    system_groups_info_list = [
        nobody_group_info,
        NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[UserProfile.ROLE_REALM_OWNER],
        NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[UserProfile.ROLE_REALM_ADMINISTRATOR],
        NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[UserProfile.ROLE_MODERATOR],
        full_members_group_info,
        NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[UserProfile.ROLE_MEMBER],
        NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[UserProfile.ROLE_GUEST],
        everyone_on_internet_group_info,
    ]

    bulk_create_system_user_groups(system_groups_info_list, realm)

    system_groups_name_dict: dict[str, NamedUserGroup] = get_role_based_system_groups_dict(realm)
    for role in NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP:
        group_name = NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[role]["name"]
        role_system_groups_dict[role] = system_groups_name_dict[group_name]

    # Order of this list here is important to create correct GroupGroupMembership objects
    # Note that because we do not create user memberships here, no audit log entries for
    # user memberships are populated either.
    system_user_groups_list = [
        system_groups_name_dict[SystemGroups.NOBODY],
        system_groups_name_dict[SystemGroups.OWNERS],
        system_groups_name_dict[SystemGroups.ADMINISTRATORS],
        system_groups_name_dict[SystemGroups.MODERATORS],
        system_groups_name_dict[SystemGroups.FULL_MEMBERS],
        system_groups_name_dict[SystemGroups.MEMBERS],
        system_groups_name_dict[SystemGroups.EVERYONE],
        system_groups_name_dict[SystemGroups.EVERYONE_ON_INTERNET],
    ]

    creation_time = timezone_now()
    realmauditlog_objects = [
        RealmAuditLog(
            realm=realm,
            acting_user=None,
            event_type=AuditLogEventType.USER_GROUP_CREATED,
            event_time=creation_time,
            modified_user_group=user_group,
        )
        for user_group in system_user_groups_list
    ]

    groups_with_updated_settings = []
    for group in system_user_groups_list:
        user_group = set_defaults_for_group_settings(group, {}, system_groups_name_dict)
        groups_with_updated_settings.append(user_group)
    NamedUserGroup.objects.bulk_update(
        groups_with_updated_settings, ["can_manage_group", "can_mention_group"]
    )

    subgroup_objects: list[GroupGroupMembership] = []
    # "Nobody" system group is not a subgroup of any user group, since it is already empty.
    subgroup, remaining_groups = system_user_groups_list[1], system_user_groups_list[2:]
    for supergroup in remaining_groups:
        subgroup_objects.append(GroupGroupMembership(subgroup=subgroup, supergroup=supergroup))
        now = timezone_now()
        realmauditlog_objects.extend(
            [
                RealmAuditLog(
                    realm=realm,
                    modified_user_group=supergroup,
                    event_type=AuditLogEventType.USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
                    event_time=now,
                    acting_user=None,
                    extra_data={"subgroup_ids": [subgroup.id]},
                ),
                RealmAuditLog(
                    realm=realm,
                    modified_user_group=subgroup,
                    event_type=AuditLogEventType.USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
                    event_time=now,
                    acting_user=None,
                    extra_data={"supergroup_ids": [supergroup.id]},
                ),
            ]
        )
        subgroup = supergroup

    GroupGroupMembership.objects.bulk_create(subgroup_objects)
    RealmAuditLog.objects.bulk_create(realmauditlog_objects)

    return role_system_groups_dict


def get_system_user_group_for_user(user_profile: UserProfile) -> NamedUserGroup:
    system_user_group_name = NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[user_profile.role]["name"]

    system_user_group = NamedUserGroup.objects.get(
        name=system_user_group_name, realm=user_profile.realm, is_system_group=True
    )
    return system_user_group


def get_server_supported_permission_settings() -> ServerSupportedPermissionSettings:
    return ServerSupportedPermissionSettings(
        realm=Realm.REALM_PERMISSION_GROUP_SETTINGS,
        stream=Stream.stream_permission_group_settings,
        group=NamedUserGroup.GROUP_PERMISSION_SETTINGS,
    )


def parse_group_setting_value(
    setting_value: int | AnonymousSettingGroupDict,
    setting_name: str,
) -> int | AnonymousSettingGroupDict:
    if isinstance(setting_value, int):
        return setting_value

    if len(setting_value.direct_members) == 0 and len(setting_value.direct_subgroups) == 1:
        return setting_value.direct_subgroups[0]

    if not settings.ALLOW_GROUP_VALUED_SETTINGS:
        raise SystemGroupRequiredError(setting_name)

    return setting_value


def are_both_group_setting_values_equal(
    first_setting_value: int | AnonymousSettingGroupDict,
    second_setting_value: int | AnonymousSettingGroupDict,
) -> bool:
    if isinstance(first_setting_value, int) and isinstance(second_setting_value, int):
        return first_setting_value == second_setting_value

    if isinstance(first_setting_value, AnonymousSettingGroupDict) and isinstance(
        second_setting_value, AnonymousSettingGroupDict
    ):
        return set(first_setting_value.direct_members) == set(
            second_setting_value.direct_members
        ) and set(first_setting_value.direct_subgroups) == set(
            second_setting_value.direct_subgroups
        )

    return False


def validate_group_setting_value_change(
    current_setting_api_value: int | AnonymousSettingGroupDict,
    new_setting_value: int | AnonymousSettingGroupDict,
    expected_current_setting_value: int | AnonymousSettingGroupDict | None,
) -> bool:
    if expected_current_setting_value is not None and not are_both_group_setting_values_equal(
        expected_current_setting_value,
        current_setting_api_value,
    ):
        # This check is here to help prevent races, by refusing to
        # change a setting where the client (and thus the UI presented
        # to user) showed a different existing state.
        raise PreviousSettingValueMismatchedError

    return not are_both_group_setting_values_equal(current_setting_api_value, new_setting_value)


def get_group_setting_value_for_audit_log_data(
    setting_value: int | AnonymousSettingGroupDict,
) -> int | dict[str, list[int]]:
    if isinstance(setting_value, int):
        return setting_value

    return asdict(setting_value)

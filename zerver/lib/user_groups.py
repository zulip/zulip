from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, TypedDict

from django.db import connection, transaction
from django.db.models import F, Q, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django_cte import With
from psycopg2.sql import SQL, Literal

from zerver.lib.exceptions import (
    CannotDeactivateGroupInUseError,
    JsonableError,
    PreviousSettingValueMismatchedError,
    SystemGroupRequiredError,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import (
    AnonymousSettingGroupDict,
    GroupPermissionSetting,
    ServerSupportedPermissionSettings,
)
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
class GroupSettingChangeRequest:
    new: int | AnonymousSettingGroupDict
    old: int | AnonymousSettingGroupDict | None = None


class UserGroupDict(TypedDict):
    id: int
    name: str
    description: str
    members: list[int]
    direct_subgroup_ids: list[int]
    creator_id: int | None
    date_created: int | None
    is_system_group: bool
    can_add_members_group: int | AnonymousSettingGroupDict
    can_join_group: int | AnonymousSettingGroupDict
    can_leave_group: int | AnonymousSettingGroupDict
    can_manage_group: int | AnonymousSettingGroupDict
    can_mention_group: int | AnonymousSettingGroupDict
    can_remove_members_group: int | AnonymousSettingGroupDict
    deactivated: bool


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


def has_user_group_access_for_subgroup(
    user_group: NamedUserGroup,
    user_profile: UserProfile,
    *,
    allow_deactivated: bool = False,
) -> bool:
    """Minimal access control checks for whether the given group
    is visible to the given user for use as a subgroup.

    In the future, if groups whose existence is not visible to the
    entire organization are added, this may grow more complex.
    """
    if user_group.realm_id != user_profile.realm_id:
        return False

    if not allow_deactivated and user_group.deactivated:
        raise JsonableError(_("User group is deactivated."))

    return True


def get_user_group_by_id_in_realm(
    user_group_id: int,
    realm: Realm,
    *,
    for_read: bool,
    for_setting: bool = False,
    allow_deactivated: bool = False,
) -> NamedUserGroup:
    """
    Internal function for accessing a single user group from client
    code. Locks the group if for_read is False.

    Notably does not do any access control checks, beyond only fetching
    groups from the provided realm.
    """
    try:
        if for_read:
            user_group = NamedUserGroup.objects.get(id=user_group_id, realm=realm)
        else:
            user_group = NamedUserGroup.objects.select_for_update().get(
                id=user_group_id, realm=realm
            )

        if not allow_deactivated and user_group.deactivated:
            raise JsonableError(_("User group is deactivated."))
        return user_group
    except NamedUserGroup.DoesNotExist:
        raise JsonableError(_("Invalid user group"))


def access_user_group_to_read_membership(user_group_id: int, realm: Realm) -> NamedUserGroup:
    return get_user_group_by_id_in_realm(user_group_id, realm, for_read=True)


def access_user_group_for_update(
    user_group_id: int,
    user_profile: UserProfile,
    *,
    permission_setting: str,
    allow_deactivated: bool = False,
) -> NamedUserGroup:
    """
    Main entry point that views code should call when planning to modify
    a given user group on behalf of a given user.

    The permission_setting parameter indicates what permission to check;
    different features will be used when editing the membership vs.
    security-sensitive settings on a group.
    """
    user_group = get_user_group_by_id_in_realm(
        user_group_id, user_profile.realm, for_read=False, allow_deactivated=allow_deactivated
    )

    if user_group.is_system_group:
        raise JsonableError(_("Insufficient permission"))

    # Users with permission to manage the group have all the permissions
    # including joining/leaving the group and add others to group.
    if user_profile.can_manage_all_groups():
        return user_group

    user_has_permission = user_has_permission_for_group_setting(
        user_group.can_manage_group,
        user_profile,
        NamedUserGroup.GROUP_PERMISSION_SETTINGS["can_manage_group"],
    )
    if user_has_permission:
        return user_group

    if permission_setting != "can_manage_group":
        assert permission_setting in NamedUserGroup.GROUP_PERMISSION_SETTINGS
        user_has_permission = user_has_permission_for_group_setting(
            getattr(user_group, permission_setting),
            user_profile,
            NamedUserGroup.GROUP_PERMISSION_SETTINGS[permission_setting],
        )

        if user_has_permission:
            return user_group

    raise JsonableError(_("Insufficient permission"))


def access_user_group_for_deactivation(
    user_group_id: int, user_profile: UserProfile
) -> NamedUserGroup:
    """
    Main security check / access function for whether the acting
    user has permission to deactivate a given user group.
    """
    user_group = access_user_group_for_update(
        user_group_id, user_profile, permission_setting="can_manage_group"
    )

    objections: list[dict[str, Any]] = []
    supergroup_ids = (
        user_group.direct_supergroups.exclude(named_user_group=None)
        .filter(named_user_group__deactivated=False)
        .values_list("id", flat=True)
    )
    if supergroup_ids:
        objections.append(dict(type="subgroup", supergroup_ids=list(supergroup_ids)))

    anonymous_supergroup_ids = user_group.direct_supergroups.filter(
        named_user_group=None
    ).values_list("id", flat=True)

    # We check both the cases - whether the group is being directly used
    # as the value of a setting or as a subgroup of an anonymous group
    # used for a setting.
    setting_group_ids_using_deactivating_user_group = {
        *set(anonymous_supergroup_ids),
        user_group.id,
    }

    stream_setting_query = Q()
    for setting_name in Stream.stream_permission_group_settings:
        stream_setting_query |= Q(
            **{f"{setting_name}__in": setting_group_ids_using_deactivating_user_group}
        )

    for stream in Stream.objects.filter(realm_id=user_group.realm_id, deactivated=False).filter(
        stream_setting_query
    ):
        objection_settings = [
            setting_name
            for setting_name in Stream.stream_permission_group_settings
            if getattr(stream, setting_name + "_id")
            in setting_group_ids_using_deactivating_user_group
        ]
        if len(objection_settings) > 0:
            objections.append(
                dict(type="channel", channel_id=stream.id, settings=objection_settings)
            )

    group_setting_query = Q()
    for setting_name in NamedUserGroup.GROUP_PERMISSION_SETTINGS:
        group_setting_query |= Q(
            **{f"{setting_name}__in": setting_group_ids_using_deactivating_user_group}
        )

    for group in NamedUserGroup.objects.filter(
        realm_id=user_group.realm_id, deactivated=False
    ).filter(group_setting_query):
        objection_settings = []
        for setting_name in NamedUserGroup.GROUP_PERMISSION_SETTINGS:
            if (
                getattr(group, setting_name + "_id")
                in setting_group_ids_using_deactivating_user_group
            ):
                objection_settings.append(setting_name)

        if len(objection_settings) > 0:
            objections.append(
                dict(type="user_group", group_id=group.id, settings=objection_settings)
            )

    objection_settings = []
    realm = user_group.realm
    for setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
        if getattr(realm, setting_name + "_id") in setting_group_ids_using_deactivating_user_group:
            objection_settings.append(setting_name)

    if objection_settings:
        objections.append(dict(type="realm", settings=objection_settings))

    if len(objections) > 0:
        raise CannotDeactivateGroupInUseError(objections)
    return user_group


@contextmanager
def lock_subgroups_with_respect_to_supergroup(
    potential_subgroup_ids: Collection[int],
    potential_supergroup_id: int,
    acting_user: UserProfile,
    *,
    permission_setting: str | None,
    creating_group: bool = False,
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
        if creating_group:
            # User can add subgroups to the group while creating it irrespective
            # of whether the user has other permissions for that group.
            potential_supergroup = get_user_group_by_id_in_realm(
                potential_supergroup_id, acting_user.realm, for_read=False
            )
        else:
            assert permission_setting is not None
            potential_supergroup = access_user_group_for_update(
                potential_supergroup_id, acting_user, permission_setting=permission_setting
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
            # At this time, we only do a check on the realm ID of the subgroup and
            # whether the group is deactivated or not. Realm ID error would be caught
            # above and in case the user group is deactivated the error will be raised
            # in has_user_group_access_for_subgroup itself, so there is no coverage here.
            if not has_user_group_access_for_subgroup(subgroup, acting_user):
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
    user_profile: UserProfile,
    direct_members: list[int],
    direct_subgroups: list[int],
    current_setting_value: UserGroup | None,
) -> UserGroup:
    realm = user_profile.realm
    if current_setting_value is not None and not hasattr(current_setting_value, "named_user_group"):
        # We do not create a new group if the setting was already set
        # to an anonymous group. The memberships of existing group
        # itself are updated.
        user_group = current_setting_value
    else:
        user_group = UserGroup.objects.create(realm=realm)

    from zerver.lib.users import user_ids_to_users

    member_users = user_ids_to_users(direct_members, realm, allow_deactivated=False)
    user_group.direct_members.set(member_users)

    potential_subgroups = NamedUserGroup.objects.select_for_update().filter(
        realm=realm, id__in=direct_subgroups
    )
    group_ids_found = [group.id for group in potential_subgroups]
    group_ids_not_found = [
        group_id for group_id in direct_subgroups if group_id not in group_ids_found
    ]
    if group_ids_not_found:
        raise JsonableError(
            _("Invalid user group ID: {group_id}").format(group_id=group_ids_not_found[0])
        )

    for subgroup in potential_subgroups:
        # At this time, we only do a check on the realm ID of the subgroup and
        # whether the group is deactivated or not. Realm ID error would be caught
        # above and in case the user group is deactivated the error will be raised
        # in has_user_group_access_for_subgroup itself, so there is no coverage here.
        if not has_user_group_access_for_subgroup(subgroup, user_profile):
            raise JsonableError(_("Insufficient permission"))  # nocoverage

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
    """Given a permission setting and specification of what value it
    should have (setting_user_group), returns either a Named or
    anonymous `UserGroup` with the requested membership.
    """
    if isinstance(setting_user_group, int):
        named_user_group = get_user_group_by_id_in_realm(
            setting_user_group, user_profile.realm, for_read=False, for_setting=True
        )
        check_setting_configuration_for_system_groups(
            named_user_group, setting_name, permission_configuration
        )
        return named_user_group.usergroup_ptr

    if permission_configuration.require_system_group:
        raise SystemGroupRequiredError(setting_name)

    user_group = update_or_create_user_group_for_setting(
        user_profile,
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
        direct_members=[
            member.id for member in setting_value_group.direct_members.filter(is_active=True)
        ],
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


def user_groups_in_realm_serialized(
    realm: Realm, *, include_deactivated_groups: bool
) -> list[UserGroupDict]:
    """This function is used in do_events_register code path so this code
    should be performant.  We need to do 2 database queries because
    Django's ORM doesn't properly support the left join between
    UserGroup and UserGroupMembership that we need.
    """
    realm_groups = NamedUserGroup.objects.select_related(
        "can_add_members_group",
        "can_add_members_group__named_user_group",
        "can_join_group",
        "can_join_group__named_user_group",
        "can_leave_group",
        "can_leave_group__named_user_group",
        "can_manage_group",
        "can_manage_group__named_user_group",
        "can_mention_group",
        "can_mention_group__named_user_group",
        "can_remove_members_group",
        "can_remove_members_group__named_user_group",
    ).filter(realm=realm)

    if not include_deactivated_groups:
        realm_groups = realm_groups.filter(deactivated=False)

    membership = (
        UserGroupMembership.objects.filter(user_group__realm=realm)
        .exclude(user_profile__is_active=False)
        .values_list("user_group_id", "user_profile_id")
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

        creator_id = user_group.creator_id

        date_created = (
            datetime_to_timestamp(user_group.date_created)
            if user_group.date_created is not None
            else None
        )

        group_dicts[user_group.id] = dict(
            id=user_group.id,
            name=user_group.name,
            creator_id=creator_id,
            date_created=date_created,
            description=user_group.description,
            members=direct_member_ids,
            direct_subgroup_ids=direct_subgroup_ids,
            is_system_group=user_group.is_system_group,
            can_add_members_group=get_setting_value_for_user_group_object(
                user_group.can_add_members_group, group_members, group_subgroups
            ),
            can_join_group=get_setting_value_for_user_group_object(
                user_group.can_join_group, group_members, group_subgroups
            ),
            can_leave_group=get_setting_value_for_user_group_object(
                user_group.can_leave_group, group_members, group_subgroups
            ),
            can_manage_group=get_setting_value_for_user_group_object(
                user_group.can_manage_group, group_members, group_subgroups
            ),
            can_mention_group=get_setting_value_for_user_group_object(
                user_group.can_mention_group, group_members, group_subgroups
            ),
            can_remove_members_group=get_setting_value_for_user_group_object(
                user_group.can_remove_members_group, group_members, group_subgroups
            ),
            deactivated=user_group.deactivated,
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
    return UserGroupMembership.objects.filter(
        user_group=user_group, user_profile__is_active=True
    ).values_list("user_profile_id", flat=True)


def get_user_group_direct_members(user_group: UserGroup) -> QuerySet[UserProfile]:
    return user_group.direct_members.filter(is_active=True)


def get_direct_memberships_of_users(user_group: UserGroup, members: list[UserProfile]) -> list[int]:
    # Returns the subset of the provided members list who are direct subscribers of the group.
    # If a deactivated user is passed, it will be returned if the user was a member of the
    # group when deactivated.
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
    return UserProfile.objects.filter(
        is_active=True, direct_groups__in=get_recursive_subgroups(user_group)
    )


def get_recursive_membership_groups(user_profile: UserProfile) -> QuerySet[UserGroup]:
    cte = With.recursive(
        lambda cte: user_profile.direct_groups.values(group_id=F("id")).union(
            cte.join(UserGroup, direct_subgroups=cte.col.group_id).values(group_id=F("id"))
        )
    )
    return cte.join(UserGroup, id=cte.col.group_id).with_cte(cte)


def user_has_permission_for_group_setting(
    user_group: UserGroup,
    user: UserProfile,
    setting_config: GroupPermissionSetting,
    *,
    direct_member_only: bool = False,
) -> bool:
    if not setting_config.allow_everyone_group and user.is_guest:
        return False

    return is_user_in_group(user_group, user, direct_member_only=direct_member_only)


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

        if default_group_name == "group_creator":
            if user_group.creator:
                default_group = UserGroup(
                    realm=user_group.realm,
                )
                default_group.save()
                UserGroupMembership.objects.create(
                    user_profile=user_group.creator, user_group=default_group
                )
            else:
                raise AssertionError("Group creator should not be None.")
        else:
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
        SQL("({},{},{},{},{},{},{},{},{},{},{},{})").format(
            Literal(user_group_ids[idx]),
            Literal(realm.id),
            Literal(group["name"]),
            Literal(group["description"]),
            Literal(True),
            Literal(initial_group_setting_value),
            Literal(initial_group_setting_value),
            Literal(initial_group_setting_value),
            Literal(initial_group_setting_value),
            Literal(initial_group_setting_value),
            Literal(initial_group_setting_value),
            Literal(False),
        )
        for idx, group in enumerate(groups)
    ]
    query = SQL(
        """
        INSERT INTO zerver_namedusergroup (usergroup_ptr_id, realm_id, name, description, is_system_group, can_add_members_group_id, can_join_group_id, can_leave_group_id, can_manage_group_id, can_mention_group_id, can_remove_members_group_id, deactivated)
        VALUES {rows}
        """
    ).format(rows=SQL(", ").join(rows))
    with connection.cursor() as cursor:
        cursor.execute(query)


@transaction.atomic(savepoint=False)
def create_system_user_groups_for_realm(realm: Realm) -> dict[str, NamedUserGroup]:
    """Any changes to this function likely require a migration to adjust
    existing realms.  See e.g. migration 0382_create_role_based_system_groups.py,
    which is a copy of this function from when we introduced system groups.
    """

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
        groups_with_updated_settings,
        [
            "can_add_members_group",
            "can_join_group",
            "can_leave_group",
            "can_manage_group",
            "can_mention_group",
            "can_remove_members_group",
        ],
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

    return system_groups_name_dict


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

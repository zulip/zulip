from datetime import datetime
from typing import Dict, List, Mapping, Optional, Sequence, TypedDict, Union

import django.db.utils
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.user_groups import (
    get_role_based_system_groups_dict,
    set_defaults_for_group_settings,
)
from zerver.models import (
    GroupGroupMembership,
    NamedUserGroup,
    Realm,
    RealmAuditLog,
    UserGroup,
    UserGroupMembership,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event, send_event_on_commit


class MemberGroupUserDict(TypedDict):
    id: int
    role: int
    date_joined: datetime


@transaction.atomic
def create_user_group_in_database(
    name: str,
    members: List[UserProfile],
    realm: Realm,
    *,
    acting_user: Optional[UserProfile],
    description: str = "",
    group_settings_map: Mapping[str, UserGroup] = {},
    is_system_group: bool = False,
) -> NamedUserGroup:
    user_group = NamedUserGroup(
        name=name,
        realm=realm,
        description=description,
        is_system_group=is_system_group,
        realm_for_sharding=realm,
    )

    for setting_name, setting_value in group_settings_map.items():
        setattr(user_group, setting_name, setting_value)

    system_groups_name_dict = get_role_based_system_groups_dict(realm)
    user_group = set_defaults_for_group_settings(
        user_group, group_settings_map, system_groups_name_dict
    )
    user_group.save()

    UserGroupMembership.objects.bulk_create(
        UserGroupMembership(user_profile=member, user_group=user_group) for member in members
    )

    creation_time = timezone_now()
    audit_log_entries = [
        RealmAuditLog(
            realm=realm,
            acting_user=acting_user,
            event_type=RealmAuditLog.USER_GROUP_CREATED,
            event_time=creation_time,
            modified_user_group=user_group,
        ),
    ] + [
        RealmAuditLog(
            realm=realm,
            acting_user=acting_user,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
            event_time=creation_time,
            modified_user=member,
            modified_user_group=user_group,
        )
        for member in members
    ]
    RealmAuditLog.objects.bulk_create(audit_log_entries)
    return user_group


@transaction.atomic(savepoint=False)
def update_users_in_full_members_system_group(
    realm: Realm, affected_user_ids: Sequence[int] = [], *, acting_user: Optional[UserProfile]
) -> None:
    full_members_system_group = NamedUserGroup.objects.get(
        realm=realm, name=SystemGroups.FULL_MEMBERS, is_system_group=True
    )
    members_system_group = NamedUserGroup.objects.get(
        realm=realm, name=SystemGroups.MEMBERS, is_system_group=True
    )

    full_member_group_users: List[MemberGroupUserDict] = list()
    member_group_users: List[MemberGroupUserDict] = list()

    if affected_user_ids:
        full_member_group_users = list(
            full_members_system_group.direct_members.filter(id__in=affected_user_ids).values(
                "id", "role", "date_joined"
            )
        )
        member_group_users = list(
            members_system_group.direct_members.filter(id__in=affected_user_ids).values(
                "id", "role", "date_joined"
            )
        )
    else:
        full_member_group_users = list(
            full_members_system_group.direct_members.all().values("id", "role", "date_joined")
        )
        member_group_users = list(
            members_system_group.direct_members.all().values("id", "role", "date_joined")
        )

    def is_provisional_member(user: MemberGroupUserDict) -> bool:
        diff = (timezone_now() - user["date_joined"]).days
        if diff < realm.waiting_period_threshold:
            return True
        return False

    old_full_members = [
        user
        for user in full_member_group_users
        if is_provisional_member(user) or user["role"] != UserProfile.ROLE_MEMBER
    ]

    full_member_group_user_ids = [user["id"] for user in full_member_group_users]
    members_excluding_full_members = [
        user for user in member_group_users if user["id"] not in full_member_group_user_ids
    ]

    new_full_members = [
        user for user in members_excluding_full_members if not is_provisional_member(user)
    ]

    old_full_member_ids = [user["id"] for user in old_full_members]
    new_full_member_ids = [user["id"] for user in new_full_members]

    if len(old_full_members) > 0:
        bulk_remove_members_from_user_groups(
            [full_members_system_group], old_full_member_ids, acting_user=acting_user
        )

    if len(new_full_members) > 0:
        bulk_add_members_to_user_groups(
            [full_members_system_group], new_full_member_ids, acting_user=acting_user
        )


def promote_new_full_members() -> None:
    for realm in Realm.objects.filter(deactivated=False).exclude(waiting_period_threshold=0):
        update_users_in_full_members_system_group(realm, acting_user=None)


def do_send_create_user_group_event(
    user_group: NamedUserGroup,
    members: List[UserProfile],
    direct_subgroups: Sequence[UserGroup] = [],
) -> None:
    event = dict(
        type="user_group",
        op="add",
        group=dict(
            name=user_group.name,
            members=[member.id for member in members],
            description=user_group.description,
            id=user_group.id,
            is_system_group=user_group.is_system_group,
            direct_subgroup_ids=[direct_subgroup.id for direct_subgroup in direct_subgroups],
            can_mention_group=user_group.can_mention_group_id,
        ),
    )
    send_event(user_group.realm, event, active_user_ids(user_group.realm_id))


def check_add_user_group(
    realm: Realm,
    name: str,
    initial_members: List[UserProfile],
    description: str = "",
    group_settings_map: Mapping[str, UserGroup] = {},
    *,
    acting_user: Optional[UserProfile],
) -> NamedUserGroup:
    try:
        user_group = create_user_group_in_database(
            name,
            initial_members,
            realm,
            description=description,
            group_settings_map=group_settings_map,
            acting_user=acting_user,
        )
        do_send_create_user_group_event(user_group, initial_members)
        return user_group
    except django.db.utils.IntegrityError:
        raise JsonableError(_("User group '{group_name}' already exists.").format(group_name=name))


def do_send_user_group_update_event(
    user_group: NamedUserGroup, data: Dict[str, Union[str, int]]
) -> None:
    event = dict(type="user_group", op="update", group_id=user_group.id, data=data)
    send_event(user_group.realm, event, active_user_ids(user_group.realm_id))


@transaction.atomic(savepoint=False)
def do_update_user_group_name(
    user_group: NamedUserGroup, name: str, *, acting_user: Optional[UserProfile]
) -> None:
    try:
        old_value = user_group.name
        user_group.name = name
        user_group.save(update_fields=["name"])
        RealmAuditLog.objects.create(
            realm=user_group.realm,
            modified_user_group=user_group,
            event_type=RealmAuditLog.USER_GROUP_NAME_CHANGED,
            event_time=timezone_now(),
            acting_user=acting_user,
            extra_data={
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: name,
            },
        )
    except django.db.utils.IntegrityError:
        raise JsonableError(_("User group '{group_name}' already exists.").format(group_name=name))
    do_send_user_group_update_event(user_group, dict(name=name))


@transaction.atomic(savepoint=False)
def do_update_user_group_description(
    user_group: NamedUserGroup, description: str, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = user_group.description
    user_group.description = description
    user_group.save(update_fields=["description"])
    RealmAuditLog.objects.create(
        realm=user_group.realm,
        modified_user_group=user_group,
        event_type=RealmAuditLog.USER_GROUP_DESCRIPTION_CHANGED,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: description,
        },
    )
    do_send_user_group_update_event(user_group, dict(description=description))


def do_send_user_group_members_update_event(
    event_name: str, user_group: NamedUserGroup, user_ids: List[int]
) -> None:
    event = dict(type="user_group", op=event_name, group_id=user_group.id, user_ids=user_ids)
    send_event_on_commit(user_group.realm, event, active_user_ids(user_group.realm_id))


@transaction.atomic(savepoint=False)
def bulk_add_members_to_user_groups(
    user_groups: List[NamedUserGroup],
    user_profile_ids: List[int],
    *,
    acting_user: Optional[UserProfile],
) -> None:
    # All intended callers of this function involve a single user
    # being added to one or more groups, or many users being added to
    # a single group; but it's easy enough for the implementation to
    # support both.

    memberships = [
        UserGroupMembership(user_group_id=user_group.id, user_profile_id=user_id)
        for user_id in user_profile_ids
        for user_group in user_groups
    ]
    UserGroupMembership.objects.bulk_create(memberships)
    now = timezone_now()
    RealmAuditLog.objects.bulk_create(
        RealmAuditLog(
            realm=user_group.realm,
            modified_user_id=user_id,
            modified_user_group=user_group,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
            event_time=now,
            acting_user=acting_user,
        )
        for user_id in user_profile_ids
        for user_group in user_groups
    )

    for user_group in user_groups:
        do_send_user_group_members_update_event("add_members", user_group, user_profile_ids)


@transaction.atomic(savepoint=False)
def bulk_remove_members_from_user_groups(
    user_groups: List[NamedUserGroup],
    user_profile_ids: List[int],
    *,
    acting_user: Optional[UserProfile],
) -> None:
    # All intended callers of this function involve a single user
    # being added to one or more groups, or many users being added to
    # a single group; but it's easy enough for the implementation to
    # support both.

    UserGroupMembership.objects.filter(
        user_group__in=user_groups, user_profile_id__in=user_profile_ids
    ).delete()
    now = timezone_now()
    RealmAuditLog.objects.bulk_create(
        RealmAuditLog(
            realm=user_group.realm,
            modified_user_id=user_id,
            modified_user_group=user_group,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_REMOVED,
            event_time=now,
            acting_user=acting_user,
        )
        for user_id in user_profile_ids
        for user_group in user_groups
    )

    for user_group in user_groups:
        do_send_user_group_members_update_event("remove_members", user_group, user_profile_ids)


def do_send_subgroups_update_event(
    event_name: str, user_group: NamedUserGroup, subgroup_ids: List[int]
) -> None:
    event = dict(
        type="user_group", op=event_name, group_id=user_group.id, direct_subgroup_ids=subgroup_ids
    )
    send_event_on_commit(user_group.realm, event, active_user_ids(user_group.realm_id))


@transaction.atomic
def add_subgroups_to_user_group(
    user_group: NamedUserGroup,
    subgroups: List[NamedUserGroup],
    *,
    acting_user: Optional[UserProfile],
) -> None:
    group_memberships = [
        GroupGroupMembership(supergroup=user_group, subgroup=subgroup) for subgroup in subgroups
    ]
    GroupGroupMembership.objects.bulk_create(group_memberships)

    subgroup_ids = [subgroup.id for subgroup in subgroups]
    now = timezone_now()
    audit_log_entries = [
        RealmAuditLog(
            realm=user_group.realm,
            modified_user_group=user_group,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
            event_time=now,
            acting_user=acting_user,
            extra_data={"subgroup_ids": subgroup_ids},
        ),
        *(
            RealmAuditLog(
                realm=user_group.realm,
                modified_user_group_id=subgroup_id,
                event_type=RealmAuditLog.USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
                event_time=now,
                acting_user=acting_user,
                extra_data={"supergroup_ids": [user_group.id]},
            )
            for subgroup_id in subgroup_ids
        ),
    ]
    RealmAuditLog.objects.bulk_create(audit_log_entries)

    do_send_subgroups_update_event("add_subgroups", user_group, subgroup_ids)


@transaction.atomic
def remove_subgroups_from_user_group(
    user_group: NamedUserGroup,
    subgroups: List[NamedUserGroup],
    *,
    acting_user: Optional[UserProfile],
) -> None:
    GroupGroupMembership.objects.filter(supergroup=user_group, subgroup__in=subgroups).delete()

    subgroup_ids = [subgroup.id for subgroup in subgroups]
    now = timezone_now()
    audit_log_entries = [
        RealmAuditLog(
            realm=user_group.realm,
            modified_user_group=user_group,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_REMOVED,
            event_time=now,
            acting_user=acting_user,
            extra_data={"subgroup_ids": subgroup_ids},
        ),
        *(
            RealmAuditLog(
                realm=user_group.realm,
                modified_user_group_id=subgroup_id,
                event_type=RealmAuditLog.USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_REMOVED,
                event_time=now,
                acting_user=acting_user,
                extra_data={"supergroup_ids": [user_group.id]},
            )
            for subgroup_id in subgroup_ids
        ),
    ]
    RealmAuditLog.objects.bulk_create(audit_log_entries)

    do_send_subgroups_update_event("remove_subgroups", user_group, subgroup_ids)


def do_send_delete_user_group_event(realm: Realm, user_group_id: int, realm_id: int) -> None:
    event = dict(type="user_group", op="remove", group_id=user_group_id)
    send_event(realm, event, active_user_ids(realm_id))


def check_delete_user_group(user_group: NamedUserGroup, *, acting_user: UserProfile) -> None:
    user_group_id = user_group.id
    user_group.delete()
    do_send_delete_user_group_event(acting_user.realm, user_group_id, acting_user.realm.id)


@transaction.atomic(savepoint=False)
def do_change_user_group_permission_setting(
    user_group: NamedUserGroup,
    setting_name: str,
    setting_value_group: UserGroup,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    old_value = getattr(user_group, setting_name)
    setattr(user_group, setting_name, setting_value_group)
    user_group.save()
    RealmAuditLog.objects.create(
        realm=user_group.realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.USER_GROUP_GROUP_BASED_SETTING_CHANGED,
        event_time=timezone_now(),
        modified_user_group=user_group,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value.id,
            RealmAuditLog.NEW_VALUE: setting_value_group.id,
            "property": setting_name,
        },
    )

    event_data_dict: Dict[str, Union[str, int]] = {setting_name: setting_value_group.id}
    do_send_user_group_update_event(user_group, event_data_dict)

import datetime
from typing import Dict, List, Optional, Sequence, TypedDict

import django.db.utils
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.user_groups import access_user_group_by_id, create_user_group
from zerver.models import (
    GroupGroupMembership,
    Realm,
    UserGroup,
    UserGroupMembership,
    UserProfile,
    active_user_ids,
)
from zerver.tornado.django_api import send_event


class MemberGroupUserDict(TypedDict):
    id: int
    role: int
    date_joined: datetime.datetime


@transaction.atomic(savepoint=False)
def update_users_in_full_members_system_group(
    realm: Realm, affected_user_ids: Sequence[int] = [], *, acting_user: Optional[UserProfile]
) -> None:
    full_members_system_group = UserGroup.objects.get(
        realm=realm, name=UserGroup.FULL_MEMBERS_GROUP_NAME, is_system_group=True
    )
    members_system_group = UserGroup.objects.get(
        realm=realm, name=UserGroup.MEMBERS_GROUP_NAME, is_system_group=True
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
        remove_members_from_user_group(full_members_system_group, old_full_member_ids)

    if len(new_full_members) > 0:
        bulk_add_members_to_user_group(
            full_members_system_group, new_full_member_ids, acting_user=acting_user
        )


def promote_new_full_members() -> None:
    for realm in Realm.objects.filter(deactivated=False).exclude(waiting_period_threshold=0):
        update_users_in_full_members_system_group(realm, acting_user=None)


def do_send_create_user_group_event(
    user_group: UserGroup, members: List[UserProfile], direct_subgroups: Sequence[UserGroup] = []
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
        ),
    )
    send_event(user_group.realm, event, active_user_ids(user_group.realm_id))


def check_add_user_group(
    realm: Realm,
    name: str,
    initial_members: List[UserProfile],
    description: str,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    try:
        user_group = create_user_group(
            name, initial_members, realm, description=description, acting_user=acting_user
        )
        do_send_create_user_group_event(user_group, initial_members)
    except django.db.utils.IntegrityError:
        raise JsonableError(_("User group '{}' already exists.").format(name))


def do_send_user_group_update_event(user_group: UserGroup, data: Dict[str, str]) -> None:
    event = dict(type="user_group", op="update", group_id=user_group.id, data=data)
    send_event(user_group.realm, event, active_user_ids(user_group.realm_id))


def do_update_user_group_name(
    user_group: UserGroup, name: str, *, acting_user: Optional[UserProfile]
) -> None:
    try:
        user_group.name = name
        user_group.save(update_fields=["name"])
    except django.db.utils.IntegrityError:
        raise JsonableError(_("User group '{}' already exists.").format(name))
    do_send_user_group_update_event(user_group, dict(name=name))


def do_update_user_group_description(
    user_group: UserGroup, description: str, *, acting_user: Optional[UserProfile]
) -> None:
    user_group.description = description
    user_group.save(update_fields=["description"])
    do_send_user_group_update_event(user_group, dict(description=description))


def do_send_user_group_members_update_event(
    event_name: str, user_group: UserGroup, user_ids: List[int]
) -> None:
    event = dict(type="user_group", op=event_name, group_id=user_group.id, user_ids=user_ids)
    transaction.on_commit(
        lambda: send_event(user_group.realm, event, active_user_ids(user_group.realm_id))
    )


@transaction.atomic(savepoint=False)
def bulk_add_members_to_user_group(
    user_group: UserGroup, user_profile_ids: List[int], *, acting_user: Optional[UserProfile]
) -> None:
    memberships = [
        UserGroupMembership(user_group_id=user_group.id, user_profile_id=user_id)
        for user_id in user_profile_ids
    ]
    UserGroupMembership.objects.bulk_create(memberships)

    do_send_user_group_members_update_event("add_members", user_group, user_profile_ids)


@transaction.atomic(savepoint=False)
def remove_members_from_user_group(user_group: UserGroup, user_profile_ids: List[int]) -> None:
    UserGroupMembership.objects.filter(
        user_group_id=user_group.id, user_profile_id__in=user_profile_ids
    ).delete()

    do_send_user_group_members_update_event("remove_members", user_group, user_profile_ids)


def do_send_subgroups_update_event(
    event_name: str, user_group: UserGroup, subgroup_ids: List[int]
) -> None:
    event = dict(
        type="user_group", op=event_name, group_id=user_group.id, direct_subgroup_ids=subgroup_ids
    )
    transaction.on_commit(
        lambda: send_event(user_group.realm, event, active_user_ids(user_group.realm_id))
    )


@transaction.atomic
def add_subgroups_to_user_group(user_group: UserGroup, subgroups: List[UserGroup]) -> None:
    group_memberships = [
        GroupGroupMembership(supergroup=user_group, subgroup=subgroup) for subgroup in subgroups
    ]
    GroupGroupMembership.objects.bulk_create(group_memberships)

    subgroup_ids = [subgroup.id for subgroup in subgroups]
    do_send_subgroups_update_event("add_subgroups", user_group, subgroup_ids)


@transaction.atomic
def remove_subgroups_from_user_group(user_group: UserGroup, subgroups: List[UserGroup]) -> None:
    GroupGroupMembership.objects.filter(supergroup=user_group, subgroup__in=subgroups).delete()

    subgroup_ids = [subgroup.id for subgroup in subgroups]
    do_send_subgroups_update_event("remove_subgroups", user_group, subgroup_ids)


def do_send_delete_user_group_event(realm: Realm, user_group_id: int, realm_id: int) -> None:
    event = dict(type="user_group", op="remove", group_id=user_group_id)
    send_event(realm, event, active_user_ids(realm_id))


def check_delete_user_group(user_group_id: int, user_profile: UserProfile) -> None:
    user_group = access_user_group_by_id(user_group_id, user_profile)
    user_group.delete()
    do_send_delete_user_group_event(user_profile.realm, user_group_id, user_profile.realm.id)

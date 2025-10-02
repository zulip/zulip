from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from pydantic import Json

from zerver.actions.message_send import do_send_messages, internal_prep_private_message
from zerver.actions.user_groups import (
    add_subgroups_to_user_group,
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    check_add_user_group,
    do_change_user_group_permission_setting,
    do_deactivate_user_group,
    do_reactivate_user_group,
    do_update_user_group_description,
    do_update_user_group_name,
    remove_subgroups_from_user_group,
)
from zerver.decorator import require_member_or_admin, require_user_group_create_permission
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import MentionBackend, silent_mention_syntax_for_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.lib.types import UserGroupMembersData
from zerver.lib.user_groups import (
    GroupSettingChangeRequest,
    access_user_group_for_deactivation,
    access_user_group_for_setting,
    access_user_group_for_update,
    access_user_group_to_read_membership,
    check_user_group_name,
    get_direct_memberships_of_users,
    get_group_setting_value_for_api,
    get_subgroup_ids,
    get_system_user_group_by_name,
    get_user_group_direct_member_ids,
    get_user_group_member_ids,
    is_user_in_group,
    lock_subgroups_with_respect_to_supergroup,
    parse_group_setting_value,
    user_groups_in_realm_serialized,
    validate_group_setting_value_change,
)
from zerver.lib.users import access_user_by_id, user_ids_to_users
from zerver.models import NamedUserGroup, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.users import get_system_bot
from zerver.views.streams import compose_views


@transaction.atomic(durable=True)
@require_user_group_create_permission
@typed_endpoint
def add_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    can_add_members_group: Json[int | UserGroupMembersData] | None = None,
    can_join_group: Json[int | UserGroupMembersData] | None = None,
    can_leave_group: Json[int | UserGroupMembersData] | None = None,
    can_manage_group: Json[int | UserGroupMembersData] | None = None,
    can_mention_group: Json[int | UserGroupMembersData] | None = None,
    can_remove_members_group: Json[int | UserGroupMembersData] | None = None,
    description: str,
    members: Json[list[int]],
    name: str,
    subgroups: Json[list[int]] | None = None,
) -> HttpResponse:
    user_profile.realm.ensure_not_on_limited_plan()
    user_profiles = user_ids_to_users(members, user_profile.realm, allow_deactivated=False)
    name = check_user_group_name(name)

    group_settings_map = {}
    request_settings_dict = locals()
    nobody_group = get_system_user_group_by_name(SystemGroups.NOBODY, user_profile.realm_id)
    for setting_name, permission_config in NamedUserGroup.GROUP_PERMISSION_SETTINGS.items():
        if setting_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_name] is not None:
            setting_value = parse_group_setting_value(
                request_settings_dict[setting_name], nobody_group
            )
            setting_value_group = access_user_group_for_setting(
                setting_value,
                user_profile,
                setting_name=setting_name,
                permission_configuration=permission_config,
            )
            group_settings_map[setting_name] = setting_value_group

    user_group = check_add_user_group(
        user_profile.realm,
        name,
        user_profiles,
        description,
        group_settings_map=group_settings_map,
        acting_user=user_profile,
    )

    if subgroups is not None and len(subgroups) != 0:
        with lock_subgroups_with_respect_to_supergroup(
            subgroups, user_group.id, user_profile, permission_setting=None, creating_group=True
        ) as context:
            add_subgroups_to_user_group(
                context.supergroup, context.direct_subgroups, acting_user=user_profile
            )
    return json_success(request, data={"group_id": user_group.id})


@require_member_or_admin
@typed_endpoint
def get_user_groups(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    include_deactivated_groups: Json[bool] = False,
) -> HttpResponse:
    user_groups = user_groups_in_realm_serialized(
        user_profile.realm, include_deactivated_groups=include_deactivated_groups
    ).api_groups
    return json_success(request, data={"user_groups": user_groups})


@transaction.atomic(durable=True)
@require_member_or_admin
@typed_endpoint
def edit_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    can_add_members_group: Json[GroupSettingChangeRequest] | None = None,
    can_join_group: Json[GroupSettingChangeRequest] | None = None,
    can_leave_group: Json[GroupSettingChangeRequest] | None = None,
    can_manage_group: Json[GroupSettingChangeRequest] | None = None,
    can_mention_group: Json[GroupSettingChangeRequest] | None = None,
    can_remove_members_group: Json[GroupSettingChangeRequest] | None = None,
    deactivated: Json[bool] | None = None,
    description: str | None = None,
    name: str | None = None,
    user_group_id: PathOnly[int],
) -> HttpResponse:
    if (
        name is None
        and description is None
        and can_add_members_group is None
        and can_join_group is None
        and can_leave_group is None
        and can_manage_group is None
        and can_mention_group is None
        and can_remove_members_group is None
        and deactivated is None
    ):
        raise JsonableError(_("No new data supplied"))

    user_group = access_user_group_for_update(
        user_group_id, user_profile, permission_setting="can_manage_group", allow_deactivated=True
    )

    if name is not None and name != user_group.name:
        name = check_user_group_name(name)
        do_update_user_group_name(user_group, name, acting_user=user_profile)

    if description is not None and description != user_group.description:
        do_update_user_group_description(user_group, description, acting_user=user_profile)

    if deactivated is not None and not deactivated and user_group.deactivated:
        do_reactivate_user_group(user_group, acting_user=user_profile)

    request_settings_dict = locals()
    nobody_group = get_system_user_group_by_name(SystemGroups.NOBODY, user_profile.realm_id)
    for setting_name, permission_config in NamedUserGroup.GROUP_PERMISSION_SETTINGS.items():
        if setting_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_name] is None:
            continue

        setting_value = request_settings_dict[setting_name]
        new_setting_value = parse_group_setting_value(setting_value.new, nobody_group)

        expected_current_setting_value = None
        if setting_value.old is not None:
            expected_current_setting_value = parse_group_setting_value(
                setting_value.old, nobody_group
            )

        current_value = getattr(user_group, setting_name)
        current_setting_api_value = get_group_setting_value_for_api(current_value)
        if validate_group_setting_value_change(
            current_setting_api_value, new_setting_value, expected_current_setting_value
        ):
            setting_value_group = access_user_group_for_setting(
                new_setting_value,
                user_profile,
                setting_name=setting_name,
                permission_configuration=permission_config,
                current_setting_value=current_value,
            )
            do_change_user_group_permission_setting(
                user_group,
                setting_name,
                setting_value_group,
                old_setting_api_value=current_setting_api_value,
                acting_user=user_profile,
            )

    return json_success(request)


@typed_endpoint
@transaction.atomic(durable=True)
def deactivate_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_group_id: PathOnly[Json[int]],
) -> HttpResponse:
    user_group = access_user_group_for_deactivation(user_group_id, user_profile)
    do_deactivate_user_group(user_group, acting_user=user_profile)
    return json_success(request)


@require_member_or_admin
@typed_endpoint
@transaction.atomic(durable=True)
def update_user_group_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    add: Json[list[int]] | None = None,
    add_subgroups: Json[list[int]] | None = None,
    delete: Json[list[int]] | None = None,
    delete_subgroups: Json[list[int]] | None = None,
    user_group_id: PathOnly[Json[int]],
) -> HttpResponse:
    if not add and not delete and not add_subgroups and not delete_subgroups:
        raise JsonableError(
            _(
                'Nothing to do. Specify at least one of "add", "delete", "add_subgroups" or "delete_subgroups".'
            )
        )

    thunks = []
    if add:
        thunks.append(
            lambda: add_members_to_group_backend(
                request, user_profile, user_group_id=user_group_id, members=add
            )
        )
    if delete:
        thunks.append(
            lambda: remove_members_from_group_backend(
                request, user_profile, user_group_id=user_group_id, members=delete
            )
        )

    if add_subgroups:
        thunks.append(
            lambda: add_subgroups_to_group_backend(
                request, user_profile, user_group_id=user_group_id, subgroup_ids=add_subgroups
            )
        )

    if delete_subgroups:
        thunks.append(
            lambda: remove_subgroups_from_group_backend(
                request, user_profile, user_group_id=user_group_id, subgroup_ids=delete_subgroups
            )
        )

    data = compose_views(thunks)

    return json_success(request, data)


def notify_for_user_group_subscription_changes(
    acting_user: UserProfile,
    recipient_users: list[UserProfile],
    user_group: NamedUserGroup,
    *,
    send_subscription_message: bool = False,
    send_unsubscription_message: bool = False,
) -> None:
    realm = acting_user.realm
    mention_backend = MentionBackend(realm.id)

    notifications = []
    notification_bot = get_system_bot(settings.NOTIFICATION_BOT, realm.id)
    for recipient_user in recipient_users:
        if recipient_user.id == acting_user.id:
            # Don't send notification message if you subscribed/unsubscribed yourself.
            continue
        if recipient_user.is_bot:
            # Don't send notification message to bots.
            continue

        assert recipient_user.is_active

        with override_language(recipient_user.default_language):
            if send_subscription_message:
                message = _("{user_full_name} added you to the group {group_name}.").format(
                    user_full_name=silent_mention_syntax_for_user(acting_user),
                    group_name=f"@_*{user_group.name}*",
                )
            if send_unsubscription_message:
                message = _("{user_full_name} removed you from the group {group_name}.").format(
                    user_full_name=silent_mention_syntax_for_user(acting_user),
                    group_name=f"@_*{user_group.name}*",
                )

        notifications.append(
            internal_prep_private_message(
                sender=notification_bot,
                recipient_user=recipient_user,
                content=message,
                mention_backend=mention_backend,
                acting_user=acting_user,
            )
        )

    if len(notifications) > 0:
        do_send_messages(notifications)


def add_members_to_group_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int,
    members: list[int],
) -> HttpResponse:
    if len(members) == 1 and user_profile.id == members[0]:
        try:
            user_group = access_user_group_for_update(
                user_group_id,
                user_profile,
                permission_setting="can_join_group",
                allow_deactivated=True,
            )
        except JsonableError:
            # User can still join the group if user has permission to add
            # anyone in the group.
            user_group = access_user_group_for_update(
                user_group_id,
                user_profile,
                permission_setting="can_add_members_group",
                allow_deactivated=True,
            )
    else:
        user_group = access_user_group_for_update(
            user_group_id,
            user_profile,
            permission_setting="can_add_members_group",
            allow_deactivated=True,
        )

    member_users = user_ids_to_users(members, user_profile.realm, allow_deactivated=False)
    existing_member_ids = set(
        get_direct_memberships_of_users(user_group.usergroup_ptr, member_users)
    )

    for member_user in member_users:
        if member_user.id in existing_member_ids:
            raise JsonableError(
                _("User {user_id} is already a member of this group").format(
                    user_id=member_user.id,
                )
            )

    member_user_ids = [member_user.id for member_user in member_users]
    bulk_add_members_to_user_groups([user_group], member_user_ids, acting_user=user_profile)
    notify_for_user_group_subscription_changes(
        acting_user=user_profile,
        recipient_users=member_users,
        user_group=user_group,
        send_subscription_message=True,
    )
    return json_success(request)


def remove_members_from_group_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int,
    members: list[int],
) -> HttpResponse:
    user_profiles = user_ids_to_users(members, user_profile.realm, allow_deactivated=False)
    if len(members) == 1 and user_profile.id == members[0]:
        try:
            user_group = access_user_group_for_update(
                user_group_id,
                user_profile,
                permission_setting="can_leave_group",
                allow_deactivated=True,
            )
        except JsonableError:
            # User can still leave the group if user has permission to remove
            # anyone from the group.
            user_group = access_user_group_for_update(
                user_group_id,
                user_profile,
                permission_setting="can_remove_members_group",
                allow_deactivated=True,
            )
    else:
        user_group = access_user_group_for_update(
            user_group_id,
            user_profile,
            permission_setting="can_remove_members_group",
            allow_deactivated=True,
        )

    group_member_ids = get_user_group_direct_member_ids(user_group)
    for member in members:
        if member not in group_member_ids:
            raise JsonableError(
                _("There is no member '{user_id}' in this user group").format(user_id=member)
            )

    user_profile_ids = [user.id for user in user_profiles]
    bulk_remove_members_from_user_groups([user_group], user_profile_ids, acting_user=user_profile)
    notify_for_user_group_subscription_changes(
        acting_user=user_profile,
        recipient_users=user_profiles,
        user_group=user_group,
        send_unsubscription_message=True,
    )
    return json_success(request)


def add_subgroups_to_group_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int,
    subgroup_ids: list[int],
) -> HttpResponse:
    with lock_subgroups_with_respect_to_supergroup(
        subgroup_ids, user_group_id, user_profile, permission_setting="can_add_members_group"
    ) as context:
        existing_direct_subgroup_ids = context.supergroup.direct_subgroups.all().values_list(
            "id", flat=True
        )
        for group in context.direct_subgroups:
            if group.id in existing_direct_subgroup_ids:
                raise JsonableError(
                    _("User group {group_id} is already a subgroup of this group.").format(
                        group_id=group.id
                    )
                )

        recursive_subgroup_ids = {
            recursive_subgroup.id for recursive_subgroup in context.recursive_subgroups
        }
        if user_group_id in recursive_subgroup_ids:
            raise JsonableError(
                _(
                    "User group {user_group_id} is already a subgroup of one of the passed subgroups."
                ).format(user_group_id=user_group_id)
            )

        add_subgroups_to_user_group(
            context.supergroup, context.direct_subgroups, acting_user=user_profile
        )
    return json_success(request)


def remove_subgroups_from_group_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int,
    subgroup_ids: list[int],
) -> HttpResponse:
    with lock_subgroups_with_respect_to_supergroup(
        subgroup_ids, user_group_id, user_profile, permission_setting="can_manage_group"
    ) as context:
        # While the recursive subgroups in the context are not used, it is important that
        # we acquire a lock for these rows while updating the subgroups to acquire the locks
        # in a consistent order for subgroup membership changes.
        existing_direct_subgroup_ids = context.supergroup.direct_subgroups.all().values_list(
            "id", flat=True
        )
        for group in context.direct_subgroups:
            if group.id not in existing_direct_subgroup_ids:
                raise JsonableError(
                    _("User group {group_id} is not a subgroup of this group.").format(
                        group_id=group.id
                    )
                )

        remove_subgroups_from_user_group(
            context.supergroup, context.direct_subgroups, acting_user=user_profile
        )

    return json_success(request)


@require_member_or_admin
@typed_endpoint
@transaction.atomic(durable=True)
def update_subgroups_of_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    add: Json[list[int]] | None = None,
    delete: Json[list[int]] | None = None,
    user_group_id: PathOnly[Json[int]],
) -> HttpResponse:
    if not add and not delete:
        raise JsonableError(_('Nothing to do. Specify at least one of "add" or "delete".'))

    thunks = []
    if add:
        thunks.append(
            lambda: add_subgroups_to_group_backend(
                request, user_profile, user_group_id=user_group_id, subgroup_ids=add
            )
        )
    if delete:
        thunks.append(
            lambda: remove_subgroups_from_group_backend(
                request, user_profile, user_group_id=user_group_id, subgroup_ids=delete
            )
        )

    data = compose_views(thunks)

    return json_success(request, data)


@require_member_or_admin
@typed_endpoint
def get_is_user_group_member(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    direct_member_only: Json[bool] = False,
    user_group_id: PathOnly[Json[int]],
    user_id: PathOnly[Json[int]],
) -> HttpResponse:
    user_group = access_user_group_to_read_membership(user_group_id, user_profile.realm)
    target_user = access_user_by_id(user_profile, user_id, for_admin=False)

    return json_success(
        request,
        data={
            "is_user_group_member": is_user_in_group(
                user_group.id, target_user, direct_member_only=direct_member_only
            )
        },
    )


@require_member_or_admin
@typed_endpoint
def get_user_group_members(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    direct_member_only: Json[bool] = False,
    user_group_id: PathOnly[Json[int]],
) -> HttpResponse:
    user_group = access_user_group_to_read_membership(user_group_id, user_profile.realm)

    return json_success(
        request,
        data={
            "members": get_user_group_member_ids(user_group, direct_member_only=direct_member_only)
        },
    )


@require_member_or_admin
@typed_endpoint
def get_subgroups_of_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    direct_subgroup_only: Json[bool] = False,
    user_group_id: PathOnly[Json[int]],
) -> HttpResponse:
    user_group = access_user_group_to_read_membership(user_group_id, user_profile.realm)

    return json_success(
        request,
        data={"subgroups": get_subgroup_ids(user_group, direct_subgroup_only=direct_subgroup_only)},
    )

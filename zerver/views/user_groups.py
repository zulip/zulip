from typing import List, Optional, Sequence

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.message_send import do_send_messages, internal_prep_private_message
from zerver.actions.user_groups import (
    add_subgroups_to_user_group,
    bulk_add_members_to_user_group,
    check_add_user_group,
    check_delete_user_group,
    do_change_user_group_permission_setting,
    do_update_user_group_description,
    do_update_user_group_name,
    remove_members_from_user_group,
    remove_subgroups_from_user_group,
)
from zerver.decorator import require_member_or_admin, require_user_group_edit_permission
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import MentionBackend, silent_mention_syntax_for_user
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.user_groups import (
    access_user_group_by_id,
    access_user_group_for_setting,
    access_user_groups_as_potential_subgroups,
    get_direct_memberships_of_users,
    get_recursive_subgroups_for_groups,
    get_subgroup_ids,
    get_user_group_direct_member_ids,
    get_user_group_member_ids,
    is_user_in_group,
    user_groups_in_realm_serialized,
)
from zerver.lib.users import access_user_by_id, user_ids_to_users
from zerver.lib.validator import check_bool, check_int, check_list
from zerver.models import UserGroup, UserProfile, get_system_bot
from zerver.views.streams import compose_views


@require_user_group_edit_permission
@has_request_variables
def add_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    name: str = REQ(),
    members: Sequence[int] = REQ(json_validator=check_list(check_int), default=[]),
    description: str = REQ(),
    can_mention_group_id: Optional[int] = REQ(json_validator=check_int, default=None),
) -> HttpResponse:
    user_profiles = user_ids_to_users(members, user_profile.realm)

    group_settings_map = {}
    request_settings_dict = locals()
    for setting_name, permission_config in UserGroup.GROUP_PERMISSION_SETTINGS.items():
        setting_group_id_name = setting_name + "_id"

        if setting_group_id_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_group_id_name] is not None:
            setting_value_group_id = request_settings_dict[setting_group_id_name]
            setting_value_group = access_user_group_for_setting(
                setting_value_group_id,
                user_profile,
                setting_name=setting_name,
                require_system_group=permission_config.require_system_group,
                allow_internet_group=permission_config.allow_internet_group,
                allow_owners_group=permission_config.allow_owners_group,
                allow_nobody_group=permission_config.allow_nobody_group,
            )
            group_settings_map[setting_name] = setting_value_group

    check_add_user_group(
        user_profile.realm,
        name,
        user_profiles,
        description,
        group_settings_map=group_settings_map,
        acting_user=user_profile,
    )
    return json_success(request)


@require_member_or_admin
@has_request_variables
def get_user_group(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    user_groups = user_groups_in_realm_serialized(user_profile.realm)
    return json_success(request, data={"user_groups": user_groups})


@require_user_group_edit_permission
@has_request_variables
def edit_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
    name: Optional[str] = REQ(default=None),
    description: Optional[str] = REQ(default=None),
    can_mention_group_id: Optional[int] = REQ(json_validator=check_int, default=None),
) -> HttpResponse:
    if name is None and description is None and can_mention_group_id is None:
        raise JsonableError(_("No new data supplied"))

    user_group = access_user_group_by_id(user_group_id, user_profile)

    if name is not None and name != user_group.name:
        do_update_user_group_name(user_group, name, acting_user=user_profile)

    if description is not None and description != user_group.description:
        do_update_user_group_description(user_group, description, acting_user=user_profile)

    request_settings_dict = locals()
    for setting_name, permission_config in UserGroup.GROUP_PERMISSION_SETTINGS.items():
        setting_group_id_name = setting_name + "_id"

        if setting_group_id_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_group_id_name] is not None:
            setting_value_group_id = request_settings_dict[setting_group_id_name]
            setting_value_group = access_user_group_for_setting(
                setting_value_group_id,
                user_profile,
                setting_name=setting_name,
                require_system_group=permission_config.require_system_group,
                allow_internet_group=permission_config.allow_internet_group,
                allow_owners_group=permission_config.allow_owners_group,
                allow_nobody_group=permission_config.allow_nobody_group,
            )
            do_change_user_group_permission_setting(
                user_group, setting_name, setting_value_group, acting_user=user_profile
            )

    return json_success(request)


@require_user_group_edit_permission
@has_request_variables
def delete_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
) -> HttpResponse:
    check_delete_user_group(user_group_id, user_profile, acting_user=user_profile)
    return json_success(request)


@require_user_group_edit_permission
@has_request_variables
def update_user_group_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
    delete: Sequence[int] = REQ(json_validator=check_list(check_int), default=[]),
    add: Sequence[int] = REQ(json_validator=check_list(check_int), default=[]),
) -> HttpResponse:
    if not add and not delete:
        raise JsonableError(_('Nothing to do. Specify at least one of "add" or "delete".'))

    thunks = [
        lambda: add_members_to_group_backend(
            request, user_profile, user_group_id=user_group_id, members=add
        ),
        lambda: remove_members_from_group_backend(
            request, user_profile, user_group_id=user_group_id, members=delete
        ),
    ]
    data = compose_views(thunks)

    return json_success(request, data)


def notify_for_user_group_subscription_changes(
    acting_user: UserProfile,
    recipient_users: List[UserProfile],
    user_group: UserGroup,
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
        if not recipient_user.is_active:
            # Don't send notification message to deactivated users.
            continue

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
            )
        )

    if len(notifications) > 0:
        do_send_messages(notifications)


def add_members_to_group_backend(
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, members: Sequence[int]
) -> HttpResponse:
    if not members:
        return json_success(request)

    user_group = access_user_group_by_id(user_group_id, user_profile)
    member_users = user_ids_to_users(members, user_profile.realm)
    existing_member_ids = set(get_direct_memberships_of_users(user_group, member_users))

    for member_user in member_users:
        if member_user.id in existing_member_ids:
            raise JsonableError(
                _("User {user_id} is already a member of this group").format(
                    user_id=member_user.id,
                )
            )

    member_user_ids = [member_user.id for member_user in member_users]
    bulk_add_members_to_user_group(user_group, member_user_ids, acting_user=user_profile)
    notify_for_user_group_subscription_changes(
        acting_user=user_profile,
        recipient_users=member_users,
        user_group=user_group,
        send_subscription_message=True,
    )
    return json_success(request)


def remove_members_from_group_backend(
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, members: Sequence[int]
) -> HttpResponse:
    if not members:
        return json_success(request)

    user_profiles = user_ids_to_users(members, user_profile.realm)
    user_group = access_user_group_by_id(user_group_id, user_profile)
    group_member_ids = get_user_group_direct_member_ids(user_group)
    for member in members:
        if member not in group_member_ids:
            raise JsonableError(_("There is no member '{}' in this user group").format(member))

    user_profile_ids = [user.id for user in user_profiles]
    remove_members_from_user_group(user_group, user_profile_ids, acting_user=user_profile)
    notify_for_user_group_subscription_changes(
        acting_user=user_profile,
        recipient_users=user_profiles,
        user_group=user_group,
        send_unsubscription_message=True,
    )
    return json_success(request)


def add_subgroups_to_group_backend(
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, subgroup_ids: Sequence[int]
) -> HttpResponse:
    if not subgroup_ids:
        return json_success(request)

    subgroups = access_user_groups_as_potential_subgroups(subgroup_ids, user_profile)
    user_group = access_user_group_by_id(user_group_id, user_profile)
    existing_direct_subgroup_ids = user_group.direct_subgroups.all().values_list("id", flat=True)
    for group in subgroups:
        if group.id in existing_direct_subgroup_ids:
            raise JsonableError(
                _("User group {group_id} is already a subgroup of this group.").format(
                    group_id=group.id
                )
            )

    subgroup_ids = [group.id for group in subgroups]
    if user_group_id in get_recursive_subgroups_for_groups(subgroup_ids):
        raise JsonableError(
            _(
                "User group {user_group_id} is already a subgroup of one of the passed subgroups."
            ).format(user_group_id=user_group_id)
        )

    add_subgroups_to_user_group(user_group, subgroups, acting_user=user_profile)
    return json_success(request)


def remove_subgroups_from_group_backend(
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, subgroup_ids: Sequence[int]
) -> HttpResponse:
    if not subgroup_ids:
        return json_success(request)

    subgroups = access_user_groups_as_potential_subgroups(subgroup_ids, user_profile)
    user_group = access_user_group_by_id(user_group_id, user_profile)
    existing_direct_subgroup_ids = user_group.direct_subgroups.all().values_list("id", flat=True)
    for group in subgroups:
        if group.id not in existing_direct_subgroup_ids:
            raise JsonableError(
                _("User group {group_id} is not a subgroup of this group.").format(
                    group_id=group.id
                )
            )

    remove_subgroups_from_user_group(user_group, subgroups, acting_user=user_profile)
    return json_success(request)


@require_user_group_edit_permission
@has_request_variables
def update_subgroups_of_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
    delete: Sequence[int] = REQ(json_validator=check_list(check_int), default=[]),
    add: Sequence[int] = REQ(json_validator=check_list(check_int), default=[]),
) -> HttpResponse:
    if not add and not delete:
        raise JsonableError(_('Nothing to do. Specify at least one of "add" or "delete".'))

    thunks = [
        lambda: add_subgroups_to_group_backend(
            request, user_profile, user_group_id=user_group_id, subgroup_ids=add
        ),
        lambda: remove_subgroups_from_group_backend(
            request, user_profile, user_group_id=user_group_id, subgroup_ids=delete
        ),
    ]
    data = compose_views(thunks)

    return json_success(request, data)


@require_member_or_admin
@has_request_variables
def get_is_user_group_member(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
    user_id: int = REQ(json_validator=check_int, path_only=True),
    direct_member_only: bool = REQ(json_validator=check_bool, default=False),
) -> HttpResponse:
    user_group = access_user_group_by_id(user_group_id, user_profile, for_read=True)
    target_user = access_user_by_id(user_profile, user_id, for_admin=False)

    return json_success(
        request,
        data={
            "is_user_group_member": is_user_in_group(
                user_group, target_user, direct_member_only=direct_member_only
            )
        },
    )


@require_member_or_admin
@has_request_variables
def get_user_group_members(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
    direct_member_only: bool = REQ(json_validator=check_bool, default=False),
) -> HttpResponse:
    user_group = access_user_group_by_id(user_group_id, user_profile, for_read=True)

    return json_success(
        request,
        data={
            "members": get_user_group_member_ids(user_group, direct_member_only=direct_member_only)
        },
    )


@require_member_or_admin
@has_request_variables
def get_subgroups_of_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
    direct_subgroup_only: bool = REQ(json_validator=check_bool, default=False),
) -> HttpResponse:
    user_group = access_user_group_by_id(user_group_id, user_profile, for_read=True)

    return json_success(
        request,
        data={"subgroups": get_subgroup_ids(user_group, direct_subgroup_only=direct_subgroup_only)},
    )

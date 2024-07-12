from typing import Optional, Sequence, Union

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
    check_delete_user_group,
    do_change_user_group_permission_setting,
    do_update_user_group_description,
    do_update_user_group_name,
    remove_subgroups_from_user_group,
)
from zerver.decorator import require_member_or_admin, require_user_group_edit_permission
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import MentionBackend, silent_mention_syntax_for_user
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.lib.user_groups import (
    AnonymousSettingGroupDict,
    GroupSettingChangeRequest,
    access_user_group_by_id,
    access_user_group_for_setting,
    check_user_group_name,
    get_direct_memberships_of_users,
    get_group_setting_value_for_api,
    get_subgroup_ids,
    get_user_group_direct_member_ids,
    get_user_group_member_ids,
    is_user_in_group,
    lock_subgroups_with_respect_to_supergroup,
    parse_group_setting_value,
    user_groups_in_realm_serialized,
    validate_group_setting_value_change,
)
from zerver.lib.users import access_user_by_id, user_ids_to_users
from zerver.lib.validator import check_bool, check_int, check_list
from zerver.models import NamedUserGroup, UserProfile
from zerver.models.users import get_system_bot
from zerver.views.streams import compose_views


@require_user_group_edit_permission
@typed_endpoint
def add_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    name: str,
    members: Json[Sequence[int]],
    description: str,
    can_mention_group: Optional[Json[Union[int, AnonymousSettingGroupDict]]] = None,
) -> HttpResponse:
    user_profiles = user_ids_to_users(members, user_profile.realm)
    name = check_user_group_name(name)

    group_settings_map = {}
    request_settings_dict = locals()
    for setting_name, permission_config in NamedUserGroup.GROUP_PERMISSION_SETTINGS.items():
        if setting_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_name] is not None:
            setting_value = parse_group_setting_value(
                request_settings_dict[setting_name], setting_name
            )
            setting_value_group = access_user_group_for_setting(
                setting_value,
                user_profile,
                setting_name=setting_name,
                permission_configuration=permission_config,
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


@transaction.atomic
@require_user_group_edit_permission
@typed_endpoint
def edit_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_group_id: PathOnly[int],
    name: Optional[str] = None,
    description: Optional[str] = None,
    can_mention_group: Optional[Json[GroupSettingChangeRequest]] = None,
) -> HttpResponse:
    if name is None and description is None and can_mention_group is None:
        raise JsonableError(_("No new data supplied"))

    user_group = access_user_group_by_id(user_group_id, user_profile, for_read=False)

    if name is not None and name != user_group.name:
        name = check_user_group_name(name)
        do_update_user_group_name(user_group, name, acting_user=user_profile)

    if description is not None and description != user_group.description:
        do_update_user_group_description(user_group, description, acting_user=user_profile)

    request_settings_dict = locals()
    for setting_name, permission_config in NamedUserGroup.GROUP_PERMISSION_SETTINGS.items():
        if setting_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_name] is None:
            continue

        setting_value = request_settings_dict[setting_name]
        new_setting_value = parse_group_setting_value(setting_value.new, setting_name)

        expected_current_setting_value = None
        if setting_value.old is not None:
            expected_current_setting_value = parse_group_setting_value(
                setting_value.old, setting_name
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


@require_user_group_edit_permission
@has_request_variables
def delete_user_group(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
) -> HttpResponse:
    # For deletion, the user group's recursive subgroups and the user group itself are locked.
    with lock_subgroups_with_respect_to_supergroup(
        [user_group_id], user_group_id, acting_user=user_profile
    ) as context:
        check_delete_user_group(context.supergroup, acting_user=user_profile)
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


@transaction.atomic
def add_members_to_group_backend(
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, members: Sequence[int]
) -> HttpResponse:
    if not members:
        return json_success(request)

    user_group = access_user_group_by_id(user_group_id, user_profile, for_read=False)
    member_users = user_ids_to_users(members, user_profile.realm)
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


@transaction.atomic
def remove_members_from_group_backend(
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, members: Sequence[int]
) -> HttpResponse:
    if not members:
        return json_success(request)

    user_profiles = user_ids_to_users(members, user_profile.realm)
    user_group = access_user_group_by_id(user_group_id, user_profile, for_read=False)
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
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, subgroup_ids: Sequence[int]
) -> HttpResponse:
    if not subgroup_ids:
        return json_success(request)

    with lock_subgroups_with_respect_to_supergroup(
        subgroup_ids, user_group_id, user_profile
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
    request: HttpRequest, user_profile: UserProfile, user_group_id: int, subgroup_ids: Sequence[int]
) -> HttpResponse:
    if not subgroup_ids:
        return json_success(request)

    with lock_subgroups_with_respect_to_supergroup(
        subgroup_ids, user_group_id, user_profile
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

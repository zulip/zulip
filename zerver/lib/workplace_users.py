from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.types import UserGroupMembersData
from zerver.lib.user_groups import (
    check_group_membership_management_permissions_with_admins_only,
    get_recursive_subgroups_for_groups,
    get_role_based_system_groups_dict,
    get_user_group_by_id_in_realm,
)
from zerver.models import NamedUserGroup, Realm


def validate_workplace_users_group(
    workplace_users_group: int | UserGroupMembersData, realm: Realm
) -> None:
    system_groups_name_dict = get_role_based_system_groups_dict(realm)
    if isinstance(workplace_users_group, int):
        group = get_user_group_by_id_in_realm(workplace_users_group, realm, for_read=True)
        if group.is_system_group:
            # System group memberships can only change when a user's role
            # changes, which only admins can do.
            return

        workplace_users_group_subgroups = get_recursive_subgroups_for_groups(
            [workplace_users_group], realm
        )
    else:
        subgroup_ids = workplace_users_group.direct_subgroups
        subgroups = NamedUserGroup.objects.filter(id__in=subgroup_ids, realm_for_sharding=realm)
        non_system_group_subgroup_ids = [
            subgroup.id for subgroup in subgroups if not subgroup.is_system_group
        ]
        if len(non_system_group_subgroup_ids) == 0:
            # All direct subgroups are system groups, whose memberships can
            # only change when a user's role changes, which only admins can do.
            return

        workplace_users_group_subgroups = get_recursive_subgroups_for_groups(
            non_system_group_subgroup_ids, realm
        )

    if not check_group_membership_management_permissions_with_admins_only(
        list(workplace_users_group_subgroups), realm, system_groups_name_dict
    ):
        raise JsonableError(
            _(
                "'workplace_users_group' must be a group whose membership can only be managed by organization administrators."
            )
        )

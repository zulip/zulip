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


def realm_eligible_for_non_workplace_pricing(realm: Realm) -> bool:
    if realm.plan_type == Realm.PLAN_TYPE_SELF_HOSTED:
        # Non-workplace plan pricing is not yet implemented
        # for self-hosted plans.
        return False

    if realm.plan_type == Realm.PLAN_TYPE_STANDARD_FREE:
        # Fully sponsored plans are completely free, so it
        # would be distracting to offer menu options for
        # discounted pricing.
        return False

    if realm.plan_type == Realm.PLAN_TYPE_LIMITED:
        # We want to allow organizations to enable discounted
        # pricing for non workplace users before they upgrade.
        return True

    from corporate.models.plans import get_current_plan_by_realm

    customer_plan = get_current_plan_by_realm(realm)
    assert customer_plan is not None
    if customer_plan.fixed_price is not None:
        # Discounted pricing for non-workplace users is
        # currently incompatible with a fixed-price plan.
        return False

    return True


def realm_on_discounted_cloud_plan(realm: Realm) -> bool:
    if realm.plan_type == Realm.PLAN_TYPE_SELF_HOSTED:
        return False

    if realm.plan_type in {Realm.PLAN_TYPE_LIMITED, Realm.PLAN_TYPE_STANDARD_FREE}:
        # Realm is on free plan or is fully sponsored.
        return False

    from corporate.models.customers import get_customer_by_realm

    # We can assume that an active plan will be present
    # if realm is not on free or fully sponsored plan.
    customer = get_customer_by_realm(realm)
    assert customer is not None
    return customer.monthly_discounted_price > 0 or customer.annual_discounted_price > 0

from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from zerver.models import Realm, UserProfile


@dataclass
class BillingInfo:
    show_billing: bool
    show_plans: bool


@dataclass
class UserPermissionInfo:
    color_scheme: int
    is_guest: bool
    is_realm_admin: bool
    is_realm_owner: bool
    show_webathena: bool


def get_billing_info(user_profile: UserProfile) -> BillingInfo:
    show_billing = False
    show_plans = False
    if settings.CORPORATE_ENABLED and user_profile is not None:
        if user_profile.has_billing_access:
            from corporate.models import CustomerPlan, get_customer_by_realm

            customer = get_customer_by_realm(user_profile.realm)
            if customer is not None:
                if customer.sponsorship_pending:
                    show_billing = True
                elif CustomerPlan.objects.filter(customer=customer).exists():
                    show_billing = True

        if not user_profile.is_guest and user_profile.realm.plan_type == Realm.LIMITED:
            show_plans = True

    return BillingInfo(show_billing=show_billing, show_plans=show_plans)


def get_user_permission_info(user_profile: Optional[UserProfile]) -> UserPermissionInfo:
    if user_profile is not None:
        return UserPermissionInfo(
            color_scheme=user_profile.color_scheme,
            is_guest=user_profile.is_guest,
            is_realm_owner=user_profile.is_realm_owner,
            is_realm_admin=user_profile.is_realm_admin,
            show_webathena=user_profile.realm.webathena_enabled,
        )
    else:  # nocoverage
        return UserPermissionInfo(
            color_scheme=UserProfile.COLOR_SCHEME_AUTOMATIC,
            is_guest=False,
            is_realm_admin=False,
            is_realm_owner=False,
            show_webathena=False,
        )

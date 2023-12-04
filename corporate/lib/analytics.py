from decimal import Decimal
from typing import Any, Dict

from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import renewal_amount
from corporate.models import Customer, CustomerPlan
from zerver.lib.utils import assert_is_not_none


def get_realms_with_default_discount_dict() -> Dict[str, Decimal]:
    realms_with_default_discount: Dict[str, Any] = {}
    customers = (
        Customer.objects.exclude(default_discount=None)
        .exclude(default_discount=0)
        .exclude(realm=None)
    )
    for customer in customers:
        assert customer.realm is not None
        realms_with_default_discount[customer.realm.string_id] = assert_is_not_none(
            customer.default_discount
        )
    return realms_with_default_discount


def estimate_annual_recurring_revenue_by_realm() -> Dict[str, int]:  # nocoverage
    annual_revenue = {}
    for plan in CustomerPlan.objects.filter(status=CustomerPlan.ACTIVE).select_related(
        "customer__realm"
    ):
        if plan.customer.realm is not None:
            # TODO: figure out what to do for plans that don't automatically
            # renew, but which probably will renew
            renewal_cents = renewal_amount(plan, timezone_now())
            if plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
                renewal_cents *= 12
            # TODO: Decimal stuff
            annual_revenue[plan.customer.realm.string_id] = int(renewal_cents / 100)
    return annual_revenue

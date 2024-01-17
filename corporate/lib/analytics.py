from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict

from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import (
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
)
from corporate.models import Customer, CustomerPlan
from zerver.lib.utils import assert_is_not_none


@dataclass
class RemoteActivityPlanData:
    current_status: str
    current_plan_name: str
    annual_revenue: int


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
            renewal_cents = RealmBillingSession(
                realm=plan.customer.realm
            ).get_customer_plan_renewal_amount(plan, timezone_now())
            if plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
                renewal_cents *= 12
            # TODO: Decimal stuff
            annual_revenue[plan.customer.realm.string_id] = int(renewal_cents / 100)
    return annual_revenue


def get_plan_data_by_remote_server() -> Dict[int, RemoteActivityPlanData]:  # nocoverage
    remote_server_plan_data: Dict[int, RemoteActivityPlanData] = {}
    for plan in CustomerPlan.objects.filter(
        status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD,
        customer__realm__isnull=True,
        customer__remote_realm__isnull=True,
        customer__remote_server__deactivated=False,
    ).select_related("customer__remote_server"):
        renewal_cents = 0
        server_id = None

        assert plan.customer.remote_server is not None
        server_id = plan.customer.remote_server.id
        renewal_cents = RemoteServerBillingSession(
            remote_server=plan.customer.remote_server
        ).get_customer_plan_renewal_amount(plan, timezone_now())

        assert server_id is not None

        if plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
            renewal_cents *= 12

        current_data = remote_server_plan_data.get(server_id)
        if current_data is not None:
            current_revenue = remote_server_plan_data[server_id].annual_revenue
            current_plans = remote_server_plan_data[server_id].current_plan_name
            # There should only ever be one CustomerPlan for a remote server with
            # a status that is less than the CustomerPlan.LIVE_STATUS_THRESHOLD.
            remote_server_plan_data[server_id] = RemoteActivityPlanData(
                current_status="ERROR: MULTIPLE PLANS",
                current_plan_name=f"{current_plans}, {plan.name}",
                annual_revenue=current_revenue + renewal_cents,
            )
        else:
            remote_server_plan_data[server_id] = RemoteActivityPlanData(
                current_status=plan.get_plan_status_as_text(),
                current_plan_name=plan.name,
                annual_revenue=renewal_cents,
            )
    return remote_server_plan_data


def get_plan_data_by_remote_realm() -> Dict[int, Dict[int, RemoteActivityPlanData]]:  # nocoverage
    remote_server_plan_data_by_realm: Dict[int, Dict[int, RemoteActivityPlanData]] = {}
    for plan in CustomerPlan.objects.filter(
        status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD,
        customer__realm__isnull=True,
        customer__remote_server__isnull=True,
        customer__remote_realm__is_system_bot_realm=False,
        customer__remote_realm__realm_deactivated=False,
    ).select_related("customer__remote_realm"):
        renewal_cents = 0
        server_id = None

        assert plan.customer.remote_realm is not None
        server_id = plan.customer.remote_realm.server.id
        renewal_cents = RemoteRealmBillingSession(
            remote_realm=plan.customer.remote_realm
        ).get_customer_plan_renewal_amount(plan, timezone_now())

        assert server_id is not None

        if plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
            renewal_cents *= 12

        plan_data = RemoteActivityPlanData(
            current_status=plan.get_plan_status_as_text(),
            current_plan_name=plan.name,
            annual_revenue=renewal_cents,
        )

        current_server_data = remote_server_plan_data_by_realm.get(server_id)
        realm_id = plan.customer.remote_realm.id

        if current_server_data is None:
            realm_dict = {realm_id: plan_data}
            remote_server_plan_data_by_realm[server_id] = realm_dict
        else:
            assert current_server_data is not None
            current_realm_data = current_server_data.get(realm_id)
            if current_realm_data is not None:
                # There should only ever be one CustomerPlan for a remote realm with
                # a status that is less than the CustomerPlan.LIVE_STATUS_THRESHOLD.
                current_revenue = current_realm_data.annual_revenue
                current_plans = current_realm_data.current_plan_name
                current_server_data[realm_id] = RemoteActivityPlanData(
                    current_status="ERROR: MULTIPLE PLANS",
                    current_plan_name=f"{current_plans}, {plan.name}",
                    annual_revenue=current_revenue + renewal_cents,
                )
            else:
                current_server_data[realm_id] = plan_data

    return remote_server_plan_data_by_realm

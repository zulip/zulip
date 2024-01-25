from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from django.db.models import Prefetch
from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import (
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
)
from corporate.models import Customer, CustomerPlan, LicenseLedger
from zerver.lib.utils import assert_is_not_none
from zilencer.models import (
    RemoteCustomerUserCount,
    RemoteRealmAuditLog,
    get_remote_customer_user_count,
)


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
    plans = (
        CustomerPlan.objects.filter(
            status=CustomerPlan.ACTIVE,
            customer__remote_realm__isnull=True,
            customer__remote_server__isnull=True,
        )
        .prefetch_related(
            Prefetch(
                "licenseledger_set",
                queryset=LicenseLedger.objects.order_by("plan", "-id").distinct("plan"),
                to_attr="latest_ledger_entry",
            )
        )
        .select_related("customer__realm")
    )

    for plan in plans:
        assert plan.customer.realm is not None
        latest_ledger_entry = plan.latest_ledger_entry[0]  # type: ignore[attr-defined] # attribute from prefetch_related query
        assert latest_ledger_entry is not None
        renewal_cents = RealmBillingSession(
            realm=plan.customer.realm
        ).get_customer_plan_renewal_amount(plan, latest_ledger_entry)
        if plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
            renewal_cents *= 12
        annual_revenue[plan.customer.realm.string_id] = renewal_cents
    return annual_revenue


def get_plan_data_by_remote_server() -> Dict[int, RemoteActivityPlanData]:  # nocoverage
    remote_server_plan_data: Dict[int, RemoteActivityPlanData] = {}
    plans = (
        CustomerPlan.objects.filter(
            status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD,
            customer__realm__isnull=True,
            customer__remote_realm__isnull=True,
            customer__remote_server__deactivated=False,
        )
        .prefetch_related(
            Prefetch(
                "licenseledger_set",
                queryset=LicenseLedger.objects.order_by("plan", "-id").distinct("plan"),
                to_attr="latest_ledger_entry",
            )
        )
        .select_related("customer__remote_server")
    )

    for plan in plans:
        renewal_cents = 0
        server_id = None

        assert plan.customer.remote_server is not None
        server_id = plan.customer.remote_server.id
        assert server_id is not None
        latest_ledger_entry = plan.latest_ledger_entry[0]  # type: ignore[attr-defined] # attribute from prefetch_related query
        assert latest_ledger_entry is not None
        if plan.tier in (
            CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
        ) or plan.status in (
            CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
            CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
        ):
            renewal_cents = 0
        else:
            renewal_cents = RemoteServerBillingSession(
                remote_server=plan.customer.remote_server
            ).get_customer_plan_renewal_amount(plan, latest_ledger_entry)
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
    plans = (
        CustomerPlan.objects.filter(
            status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD,
            customer__realm__isnull=True,
            customer__remote_server__isnull=True,
            customer__remote_realm__is_system_bot_realm=False,
            customer__remote_realm__realm_deactivated=False,
        )
        .prefetch_related(
            Prefetch(
                "licenseledger_set",
                queryset=LicenseLedger.objects.order_by("plan", "-id").distinct("plan"),
                to_attr="latest_ledger_entry",
            )
        )
        .select_related("customer__remote_realm")
    )

    for plan in plans:
        renewal_cents = 0
        server_id = None

        assert plan.customer.remote_realm is not None
        server_id = plan.customer.remote_realm.server_id
        assert server_id is not None
        latest_ledger_entry = plan.latest_ledger_entry[0]  # type: ignore[attr-defined] # attribute from prefetch_related query
        assert latest_ledger_entry is not None
        if plan.tier in (
            CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
        ) or plan.status in (
            CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
            CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
        ):
            renewal_cents = 0
        else:
            renewal_cents = RemoteRealmBillingSession(
                remote_realm=plan.customer.remote_realm
            ).get_customer_plan_renewal_amount(plan, latest_ledger_entry)
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


def get_remote_realm_user_counts(
    event_time: datetime = timezone_now(),
) -> Dict[int, RemoteCustomerUserCount]:  # nocoverage
    user_counts_by_realm: Dict[int, RemoteCustomerUserCount] = {}
    for log in (
        RemoteRealmAuditLog.objects.filter(
            event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            event_time__lte=event_time,
            remote_realm__isnull=False,
        )
        # Important: extra_data is empty for some pre-2020 audit logs
        # prior to the introduction of realm_user_count_by_role
        # logging. Meanwhile, modern Zulip servers using
        # bulk_create_users to create the users in the system bot
        # realm also generate such audit logs. Such audit logs should
        # never be the latest in a normal realm.
        .exclude(extra_data={})
        .order_by("remote_realm", "-event_time")
        .distinct("remote_realm")
        .select_related("remote_realm")
    ):
        assert log.remote_realm is not None
        user_counts_by_realm[log.remote_realm.id] = get_remote_customer_user_count([log])

    return user_counts_by_realm


def get_remote_server_audit_logs(
    event_time: datetime = timezone_now(),
) -> Dict[int, List[RemoteRealmAuditLog]]:
    logs_per_server: Dict[int, List[RemoteRealmAuditLog]] = defaultdict(list)
    for log in (
        RemoteRealmAuditLog.objects.filter(
            event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            event_time__lte=event_time,
        )
        # Important: extra_data is empty for some pre-2020 audit logs
        # prior to the introduction of realm_user_count_by_role
        # logging. Meanwhile, modern Zulip servers using
        # bulk_create_users to create the users in the system bot
        # realm also generate such audit logs. Such audit logs should
        # never be the latest in a normal realm.
        .exclude(extra_data={})
        .order_by("server_id", "realm_id", "-event_time")
        .distinct("server_id", "realm_id")
        .select_related("server")
    ):
        logs_per_server[log.server.id].append(log)

    return logs_per_server

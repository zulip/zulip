from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import connection
from django.db.backends.utils import CursorWrapper
from django.db.models import Prefetch
from django.template import loader
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from markupsafe import Markup
from psycopg2.sql import Composable

from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan
from zerver.lib.pysa import mark_sanitized
from zerver.models import Realm
from zilencer.models import (
    RemoteCustomerUserCount,
    RemoteRealm,
    RemoteRealmAuditLog,
    RemoteZulipServer,
    get_remote_customer_user_count,
)


@dataclass
class RemoteActivityPlanData:
    current_status: str
    current_plan_name: str
    annual_revenue: int
    rate: str


@dataclass
class ActivityHeaderEntry:
    name: str
    value: str | Markup


def make_table(
    title: str,
    cols: Sequence[str],
    rows: Sequence[Any],
    *,
    header: list[ActivityHeaderEntry] | None = None,
    totals: Any | None = None,
    title_link: Markup | None = None,
    has_row_class: bool = False,
) -> str:
    if not has_row_class:

        def fix_row(row: Any) -> dict[str, Any]:
            return dict(cells=row, row_class=None)

        rows = list(map(fix_row, rows))

    data = dict(
        title=title, cols=cols, rows=rows, header=header, totals=totals, title_link=title_link
    )

    content = loader.render_to_string(
        "corporate/activity/activity_table.html",
        dict(data=data),
    )

    return content


def fix_rows(
    rows: list[list[Any]],
    i: int,
    fixup_func: Callable[[str], Markup] | Callable[[datetime], str] | Callable[[int], int],
) -> None:
    for row in rows:
        row[i] = fixup_func(row[i])


def get_query_data(query: Composable) -> list[list[Any]]:
    cursor = connection.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    rows = list(map(list, rows))
    cursor.close()
    return rows


def dictfetchall(cursor: CursorWrapper) -> list[dict[str, Any]]:
    """Returns all rows from a cursor as a dict"""
    desc = cursor.description
    return [dict(zip((col[0] for col in desc), row, strict=False)) for row in cursor.fetchall()]


def format_optional_datetime(date: datetime | None, display_none: bool = False) -> str:
    if date:
        return date.strftime("%Y-%m-%d %H:%M")
    elif display_none:
        return "None"
    else:
        return ""


def format_datetime_as_date(date: datetime) -> str:
    return date.strftime("%Y-%m-%d")


def format_none_as_zero(value: int | None) -> int:
    if value:
        return value
    else:
        return 0


def user_activity_link(email: str, user_profile_id: int) -> Markup:
    from corporate.views.user_activity import get_user_activity

    url = reverse(get_user_activity, kwargs=dict(user_profile_id=user_profile_id))
    return Markup('<a href="{url}">{email}</a>').format(url=url, email=email)


def realm_activity_link(realm_str: str) -> Markup:
    from corporate.views.realm_activity import get_realm_activity

    url = reverse(get_realm_activity, kwargs=dict(realm_str=realm_str))
    return Markup('<a href="{url}"><i class="fa fa-table"></i></a>').format(url=url)


def realm_stats_link(realm_str: str) -> Markup:
    from analytics.views.stats import stats_for_realm

    url = reverse(stats_for_realm, kwargs=dict(realm_str=realm_str))
    return Markup('<a href="{url}"><i class="fa fa-pie-chart"></i></a>').format(url=url)


def user_support_link(email: str) -> Markup:
    url = reverse("support", query={"q": email})
    return Markup('<a href="{url}"><i class="fa fa-gear"></i></a>').format(url=url)


def realm_support_link(realm_str: str) -> Markup:
    url = reverse("support", query={"q": realm_str})
    return Markup('<a href="{url}">{realm}</i></a>').format(url=url, realm=realm_str)


def realm_url_link(realm_str: str) -> Markup:
    host = Realm.host_for_subdomain(realm_str)
    url = settings.EXTERNAL_URI_SCHEME + mark_sanitized(host)
    return Markup('<a href="{url}"><i class="fa fa-home"></i></a>').format(url=url)


def remote_installation_stats_link(server_id: int) -> Markup:
    from analytics.views.stats import stats_for_remote_installation

    url = reverse(stats_for_remote_installation, kwargs=dict(remote_server_id=server_id))
    return Markup('<a href="{url}"><i class="fa fa-pie-chart"></i></a>').format(url=url)


def remote_installation_support_link(hostname: str) -> Markup:
    url = reverse("remote_servers_support", query={"q": hostname})
    return Markup('<a href="{url}"><i class="fa fa-gear"></i></a>').format(url=url)


def get_plan_rate_percentage(discount: str | None, has_fixed_price: bool) -> str:
    # We want to clearly note plans with a fixed price, and not show
    # them as paying 100%, as they are usually a special, negotiated
    # rate with the customer.
    if has_fixed_price:
        return "Fixed"

    # CustomerPlan.discount is a string field that stores the discount.
    if discount is None or discount == "0":
        return "100%"

    rate = 100 - Decimal(discount)
    if rate * 100 % 100 == 0:
        precision = 0
    else:
        precision = 2
    return f"{rate:.{precision}f}%"


def get_remote_activity_plan_data(
    plan: CustomerPlan,
    license_ledger: LicenseLedger,
    *,
    remote_realm: RemoteRealm | None = None,
    remote_server: RemoteZulipServer | None = None,
) -> RemoteActivityPlanData:
    from corporate.lib.stripe import RemoteRealmBillingSession, RemoteServerBillingSession

    has_fixed_price = plan.fixed_price is not None
    if plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY or plan.status in (
        CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
        CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
    ):
        renewal_cents = 0
        current_rate = "---"
    elif plan.tier == CustomerPlan.TIER_SELF_HOSTED_COMMUNITY:
        renewal_cents = 0
        current_rate = "0%"
    elif remote_realm is not None:
        renewal_cents = RemoteRealmBillingSession(
            remote_realm=remote_realm
        ).get_annual_recurring_revenue_for_support_data(plan, license_ledger)
        current_rate = get_plan_rate_percentage(plan.discount, has_fixed_price)
    else:
        assert remote_server is not None
        renewal_cents = RemoteServerBillingSession(
            remote_server=remote_server
        ).get_annual_recurring_revenue_for_support_data(plan, license_ledger)
        current_rate = get_plan_rate_percentage(plan.discount, has_fixed_price)

    return RemoteActivityPlanData(
        current_status=plan.get_plan_status_as_text(),
        current_plan_name=plan.name,
        annual_revenue=renewal_cents,
        rate=current_rate,
    )


def get_estimated_arr_and_rate_by_realm() -> tuple[dict[str, int], dict[str, str]]:  # nocoverage
    from corporate.lib.stripe import RealmBillingSession

    # NOTE: Customers without a plan might still have a discount attached to them which
    # are not included in `plan_rate`.
    annual_revenue = {}
    plan_rate = {}
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
        ).get_annual_recurring_revenue_for_support_data(plan, latest_ledger_entry)
        annual_revenue[plan.customer.realm.string_id] = renewal_cents
        has_fixed_price = plan.fixed_price is not None
        plan_rate[plan.customer.realm.string_id] = get_plan_rate_percentage(
            plan.discount, has_fixed_price
        )
    return annual_revenue, plan_rate


def get_plan_data_by_remote_server() -> dict[int, RemoteActivityPlanData]:  # nocoverage
    remote_server_plan_data: dict[int, RemoteActivityPlanData] = {}
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
        server_id = None
        assert plan.customer.remote_server is not None
        server_id = plan.customer.remote_server.id
        assert server_id is not None

        latest_ledger_entry = plan.latest_ledger_entry[0]  # type: ignore[attr-defined] # attribute from prefetch_related query
        assert latest_ledger_entry is not None

        plan_data = get_remote_activity_plan_data(
            plan, latest_ledger_entry, remote_server=plan.customer.remote_server
        )

        current_data = remote_server_plan_data.get(server_id)
        if current_data is not None:
            current_revenue = remote_server_plan_data[server_id].annual_revenue
            current_plans = remote_server_plan_data[server_id].current_plan_name
            # There should only ever be one CustomerPlan for a remote server with
            # a status that is less than the CustomerPlan.LIVE_STATUS_THRESHOLD.
            remote_server_plan_data[server_id] = RemoteActivityPlanData(
                current_status="ERROR: MULTIPLE PLANS",
                current_plan_name=f"{current_plans}, {plan_data.current_plan_name}",
                annual_revenue=current_revenue + plan_data.annual_revenue,
                rate="",
            )
        else:
            remote_server_plan_data[server_id] = plan_data
    return remote_server_plan_data


def get_plan_data_by_remote_realm() -> dict[int, dict[int, RemoteActivityPlanData]]:  # nocoverage
    remote_server_plan_data_by_realm: dict[int, dict[int, RemoteActivityPlanData]] = {}
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
        server_id = None
        assert plan.customer.remote_realm is not None
        server_id = plan.customer.remote_realm.server_id
        assert server_id is not None

        latest_ledger_entry = plan.latest_ledger_entry[0]  # type: ignore[attr-defined] # attribute from prefetch_related query
        assert latest_ledger_entry is not None

        plan_data = get_remote_activity_plan_data(
            plan, latest_ledger_entry, remote_realm=plan.customer.remote_realm
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
                    current_plan_name=f"{current_plans}, {plan_data.current_plan_name}",
                    annual_revenue=current_revenue + plan_data.annual_revenue,
                    rate="",
                )
            else:
                current_server_data[realm_id] = plan_data

    return remote_server_plan_data_by_realm


def get_remote_realm_user_counts(
    event_time: datetime | None = None,
) -> dict[int, RemoteCustomerUserCount]:  # nocoverage
    user_counts_by_realm: dict[int, RemoteCustomerUserCount] = {}
    for log in (
        RemoteRealmAuditLog.objects.filter(
            event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            event_time__lte=timezone_now() if event_time is None else event_time,
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
    event_time: datetime | None = None,
) -> dict[int, list[RemoteRealmAuditLog]]:
    logs_per_server: dict[int, list[RemoteRealmAuditLog]] = defaultdict(list)
    for log in (
        RemoteRealmAuditLog.objects.filter(
            event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            event_time__lte=timezone_now() if event_time is None else event_time,
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

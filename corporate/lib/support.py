from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, TypedDict, Union
from urllib.parse import urlencode, urljoin, urlunsplit

from django.conf import settings
from django.db.models import Sum
from django.urls import reverse
from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import (
    BillingSession,
    PushNotificationsEnabledStatus,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    get_configured_fixed_price_plan_offer,
    get_push_status_for_remote_request,
    start_of_next_billing_cycle,
)
from corporate.models import (
    Customer,
    CustomerPlan,
    CustomerPlanOffer,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
)
from zerver.models import Realm
from zerver.models.realms import get_org_type_display_name, get_realm
from zilencer.lib.remote_counts import MissingDataError
from zilencer.models import (
    RemoteCustomerUserCount,
    RemoteInstallationCount,
    RemotePushDeviceToken,
    RemoteRealm,
    RemoteRealmCount,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
    get_remote_realm_guest_and_non_guest_count,
    get_remote_server_guest_and_non_guest_count,
    has_stale_audit_log,
)

USER_DATA_STALE_WARNING = "Recent audit log data missing: No information for used licenses"


class SponsorshipRequestDict(TypedDict):
    org_type: str
    org_website: str
    org_description: str
    total_users: str
    paid_users: str
    paid_users_description: str
    requested_plan: str


@dataclass
class SponsorshipData:
    sponsorship_pending: bool = False
    default_discount: Optional[Decimal] = None
    minimum_licenses: Optional[int] = None
    required_plan_tier: Optional[int] = None
    latest_sponsorship_request: Optional[SponsorshipRequestDict] = None


@dataclass
class NextPlanData:
    plan: Union["CustomerPlan", "CustomerPlanOffer", None] = None
    estimated_revenue: Optional[int] = None


@dataclass
class PlanData:
    customer: Optional["Customer"] = None
    current_plan: Optional["CustomerPlan"] = None
    next_plan: Union["CustomerPlan", "CustomerPlanOffer", None] = None
    licenses: Optional[int] = None
    licenses_used: Optional[int] = None
    next_billing_cycle_start: Optional[datetime] = None
    is_legacy_plan: bool = False
    has_fixed_price: bool = False
    is_current_plan_billable: bool = False
    warning: Optional[str] = None
    annual_recurring_revenue: Optional[int] = None
    estimated_next_plan_revenue: Optional[int] = None


@dataclass
class MobilePushData:
    total_mobile_users: int
    push_notification_status: PushNotificationsEnabledStatus
    uncategorized_mobile_users: Optional[int] = None
    mobile_pushes_forwarded: Optional[int] = None
    last_mobile_push_sent: str = ""


@dataclass
class RemoteSupportData:
    date_created: datetime
    has_stale_audit_log: bool
    plan_data: PlanData
    sponsorship_data: SponsorshipData
    user_data: RemoteCustomerUserCount
    mobile_push_data: MobilePushData


@dataclass
class CloudSupportData:
    plan_data: PlanData
    sponsorship_data: SponsorshipData


def get_realm_support_url(realm: Realm) -> str:
    support_realm_url = get_realm(settings.STAFF_SUBDOMAIN).url
    support_url = urljoin(
        support_realm_url,
        urlunsplit(("", "", reverse("support"), urlencode({"q": realm.string_id}), "")),
    )
    return support_url


def get_customer_sponsorship_data(customer: Customer) -> SponsorshipData:
    pending = customer.sponsorship_pending
    discount = customer.default_discount
    licenses = customer.minimum_licenses
    plan_tier = customer.required_plan_tier
    sponsorship_request = None
    if pending:
        last_sponsorship_request = (
            ZulipSponsorshipRequest.objects.filter(customer=customer).order_by("id").last()
        )
        if last_sponsorship_request is not None:
            org_type_name = get_org_type_display_name(last_sponsorship_request.org_type)
            if (
                last_sponsorship_request.org_website is None
                or last_sponsorship_request.org_website == ""
            ):
                website = "No website submitted"
            else:
                website = last_sponsorship_request.org_website
            sponsorship_request = SponsorshipRequestDict(
                org_type=org_type_name,
                org_website=website,
                org_description=last_sponsorship_request.org_description,
                total_users=last_sponsorship_request.expected_total_users,
                paid_users=last_sponsorship_request.paid_users_count,
                paid_users_description=last_sponsorship_request.paid_users_description,
                requested_plan=last_sponsorship_request.requested_plan,
            )

    return SponsorshipData(
        sponsorship_pending=pending,
        default_discount=discount,
        minimum_licenses=licenses,
        required_plan_tier=plan_tier,
        latest_sponsorship_request=sponsorship_request,
    )


def get_annual_invoice_count(billing_schedule: int) -> int:
    if billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
        return 12
    else:
        return 1


def get_next_plan_data(
    billing_session: BillingSession,
    customer: Customer,
    current_plan: Optional[CustomerPlan] = None,
) -> NextPlanData:
    plan_offer: Optional[CustomerPlanOffer] = None

    # A customer can have a CustomerPlanOffer with or without a current plan.
    if customer.required_plan_tier:
        plan_offer = get_configured_fixed_price_plan_offer(customer, customer.required_plan_tier)

    if plan_offer is not None:
        next_plan_data = NextPlanData(plan=plan_offer)
    elif current_plan is not None:
        next_plan_data = NextPlanData(plan=billing_session.get_next_plan(current_plan))
    else:
        next_plan_data = NextPlanData()

    if next_plan_data.plan is not None:
        if next_plan_data.plan.fixed_price is not None:
            next_plan_data.estimated_revenue = next_plan_data.plan.fixed_price
            return next_plan_data

        if current_plan is not None:
            licenses_at_next_renewal = current_plan.licenses_at_next_renewal()
            if licenses_at_next_renewal is not None:
                assert type(next_plan_data.plan) is CustomerPlan
                assert next_plan_data.plan.price_per_license is not None
                invoice_count = get_annual_invoice_count(next_plan_data.plan.billing_schedule)
                next_plan_data.estimated_revenue = (
                    next_plan_data.plan.price_per_license * licenses_at_next_renewal * invoice_count
                )
            else:
                next_plan_data.estimated_revenue = 0  # nocoverage
            return next_plan_data

    return next_plan_data


def get_plan_data_for_support_view(
    billing_session: BillingSession, user_count: Optional[int] = None, stale_user_data: bool = False
) -> PlanData:
    customer = billing_session.get_customer()
    plan = None
    if customer is not None:
        plan = get_current_plan_by_customer(customer)
    plan_data = PlanData(
        customer=customer,
        current_plan=plan,
    )

    if plan is not None:
        new_plan, last_ledger_entry = billing_session.make_end_of_cycle_updates_if_needed(
            plan, timezone_now()
        )
        if last_ledger_entry is not None:
            if new_plan is not None:
                plan_data.current_plan = new_plan  # nocoverage
            plan_data.licenses = last_ledger_entry.licenses
        assert plan_data.current_plan is not None  # for mypy

        # If we already have user count data, we use that
        # instead of querying the database again to get
        # the number of currently used licenses.
        if stale_user_data:
            plan_data.warning = USER_DATA_STALE_WARNING
        elif user_count is None:
            try:
                plan_data.licenses_used = billing_session.current_count_for_billed_licenses()
            except MissingDataError:  # nocoverage
                plan_data.warning = USER_DATA_STALE_WARNING
        else:  # nocoverage
            assert user_count is not None
            plan_data.licenses_used = user_count

        if plan_data.current_plan.status in (
            CustomerPlan.FREE_TRIAL,
            CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
        ):  # nocoverage
            assert plan_data.current_plan.next_invoice_date is not None
            plan_data.next_billing_cycle_start = plan_data.current_plan.next_invoice_date
        else:
            plan_data.next_billing_cycle_start = start_of_next_billing_cycle(
                plan_data.current_plan, timezone_now()
            )

        plan_data.is_legacy_plan = (
            plan_data.current_plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        )
        plan_data.has_fixed_price = plan_data.current_plan.fixed_price is not None
        plan_data.is_current_plan_billable = billing_session.check_plan_tier_is_billable(
            plan_tier=plan_data.current_plan.tier
        )
        annual_invoice_count = get_annual_invoice_count(plan_data.current_plan.billing_schedule)
        if last_ledger_entry is not None:
            plan_data.annual_recurring_revenue = (
                billing_session.get_customer_plan_renewal_amount(
                    plan_data.current_plan, last_ledger_entry
                )
                * annual_invoice_count
            )
        else:
            plan_data.annual_recurring_revenue = 0  # nocoverage

    # Check for a non-active/scheduled CustomerPlan or CustomerPlanOffer
    if customer is not None:
        next_plan_data = get_next_plan_data(billing_session, customer, plan_data.current_plan)
        plan_data.next_plan = next_plan_data.plan
        plan_data.estimated_next_plan_revenue = next_plan_data.estimated_revenue

    return plan_data


def get_mobile_push_data(remote_entity: Union[RemoteZulipServer, RemoteRealm]) -> MobilePushData:
    if isinstance(remote_entity, RemoteZulipServer):
        total_users = (
            RemotePushDeviceToken.objects.filter(server=remote_entity)
            .distinct("user_id", "user_uuid")
            .count()
        )
        uncategorized_users = (
            RemotePushDeviceToken.objects.filter(server=remote_entity, remote_realm__isnull=True)
            .distinct("user_id", "user_uuid")
            .count()
        )
        mobile_pushes = RemoteInstallationCount.objects.filter(
            server=remote_entity,
            property="mobile_pushes_forwarded::day",
            end_time__gte=timezone_now() - timedelta(days=7),
        ).aggregate(total_forwarded=Sum("value", default=0))
        latest_remote_server_push_forwarded_count = RemoteInstallationCount.objects.filter(
            server=remote_entity,
            property="mobile_pushes_forwarded::day",
        ).last()
        if latest_remote_server_push_forwarded_count is not None:  # nocoverage
            # mobile_pushes_forwarded is a CountStat with a day frequency,
            # so we want to show the start of the latest day interval.
            push_forwarded_interval_start = (
                latest_remote_server_push_forwarded_count.end_time - timedelta(days=1)
            ).strftime("%Y-%m-%d")
        else:
            push_forwarded_interval_start = "None"
        push_notification_status = get_push_status_for_remote_request(
            remote_server=remote_entity, remote_realm=None
        )
        return MobilePushData(
            total_mobile_users=total_users,
            push_notification_status=push_notification_status,
            uncategorized_mobile_users=uncategorized_users,
            mobile_pushes_forwarded=mobile_pushes["total_forwarded"],
            last_mobile_push_sent=push_forwarded_interval_start,
        )
    else:
        assert isinstance(remote_entity, RemoteRealm)
        mobile_users = (
            RemotePushDeviceToken.objects.filter(remote_realm=remote_entity)
            .distinct("user_id", "user_uuid")
            .count()
        )
        mobile_pushes = RemoteRealmCount.objects.filter(
            remote_realm=remote_entity,
            property="mobile_pushes_forwarded::day",
            end_time__gte=timezone_now() - timedelta(days=7),
        ).aggregate(total_forwarded=Sum("value", default=0))
        latest_remote_realm_push_forwarded_count = RemoteRealmCount.objects.filter(
            remote_realm=remote_entity,
            property="mobile_pushes_forwarded::day",
        ).last()
        if latest_remote_realm_push_forwarded_count is not None:  # nocoverage
            # mobile_pushes_forwarded is a CountStat with a day frequency,
            # so we want to show the start of the latest day interval.
            push_forwarded_interval_start = (
                latest_remote_realm_push_forwarded_count.end_time - timedelta(days=1)
            ).strftime("%Y-%m-%d")
        else:
            push_forwarded_interval_start = "None"
        push_notification_status = get_push_status_for_remote_request(
            remote_entity.server, remote_entity
        )
        return MobilePushData(
            total_mobile_users=mobile_users,
            push_notification_status=push_notification_status,
            uncategorized_mobile_users=None,
            mobile_pushes_forwarded=mobile_pushes["total_forwarded"],
            last_mobile_push_sent=push_forwarded_interval_start,
        )


def get_data_for_remote_support_view(billing_session: BillingSession) -> RemoteSupportData:
    if isinstance(billing_session, RemoteServerBillingSession):
        user_data = get_remote_server_guest_and_non_guest_count(billing_session.remote_server.id)
        stale_audit_log_data = has_stale_audit_log(billing_session.remote_server)
        date_created = RemoteZulipServerAuditLog.objects.get(
            event_type=RemoteZulipServerAuditLog.REMOTE_SERVER_CREATED,
            server__id=billing_session.remote_server.id,
        ).event_time
        mobile_data = get_mobile_push_data(billing_session.remote_server)
    else:
        assert isinstance(billing_session, RemoteRealmBillingSession)
        user_data = get_remote_realm_guest_and_non_guest_count(billing_session.remote_realm)
        stale_audit_log_data = has_stale_audit_log(billing_session.remote_realm.server)
        date_created = billing_session.remote_realm.realm_date_created
        mobile_data = get_mobile_push_data(billing_session.remote_realm)
    user_count = user_data.guest_user_count + user_data.non_guest_user_count
    plan_data = get_plan_data_for_support_view(billing_session, user_count, stale_audit_log_data)
    if plan_data.customer is not None:
        sponsorship_data = get_customer_sponsorship_data(plan_data.customer)
    else:
        sponsorship_data = SponsorshipData()

    return RemoteSupportData(
        date_created=date_created,
        has_stale_audit_log=stale_audit_log_data,
        plan_data=plan_data,
        sponsorship_data=sponsorship_data,
        user_data=user_data,
        mobile_push_data=mobile_data,
    )


def get_data_for_cloud_support_view(billing_session: BillingSession) -> CloudSupportData:
    assert isinstance(billing_session, RealmBillingSession)
    plan_data = get_plan_data_for_support_view(billing_session)
    if plan_data.customer is not None:
        sponsorship_data = get_customer_sponsorship_data(plan_data.customer)
    else:
        sponsorship_data = SponsorshipData()

    return CloudSupportData(
        plan_data=plan_data,
        sponsorship_data=sponsorship_data,
    )

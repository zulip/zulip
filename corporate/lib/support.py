from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, TypedDict, Union

from django.db.models import Sum
from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import (
    BillingSession,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    get_configured_fixed_price_plan_offer,
    get_guest_user_count,
    get_non_guest_user_count,
    get_price_per_license,
    get_push_status_for_remote_request,
    start_of_next_billing_cycle,
)
from corporate.models.customers import Customer
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan, CustomerPlanOffer, get_current_plan_by_customer
from corporate.models.sponsorships import ZulipSponsorshipRequest
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Realm
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog
from zerver.models.realms import get_org_type_display_name
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

USER_DATA_STALE_WARNING = "Recent audit log missing: No data for used licenses."


class SponsorshipRequestDict(TypedDict):
    org_type: str
    org_website: str
    org_description: str
    plan_to_use_zulip: str
    total_users: str
    paid_users: str
    paid_users_description: str
    requested_plan: str


@dataclass
class SponsorshipData:
    sponsorship_pending: bool = False
    has_discount: bool = False
    monthly_discounted_price: int | None = None
    annual_discounted_price: int | None = None
    original_monthly_plan_price: int | None = None
    original_annual_plan_price: int | None = None
    minimum_licenses: int | None = None
    required_plan_tier: int | None = None
    latest_sponsorship_request: SponsorshipRequestDict | None = None


@dataclass
class NextPlanData:
    plan: Union["CustomerPlan", "CustomerPlanOffer", None] = None
    estimated_revenue: int | None = None


@dataclass
class PlanData:
    customer: Optional["Customer"] = None
    current_plan: Optional["CustomerPlan"] = None
    next_plan: Union["CustomerPlan", "CustomerPlanOffer", None] = None
    licenses: int | None = None
    licenses_used: int | None = None
    next_billing_cycle_start: datetime | None = None
    is_complimentary_access_plan: bool = False
    has_fixed_price: bool = False
    is_current_plan_billable: bool = False
    stripe_customer_url: str | None = None
    warning: str = ""
    annual_recurring_revenue: int | None = None
    estimated_next_plan_revenue: int | None = None


@dataclass
class PushNotificationsStatus:
    can_push: bool
    expected_end: datetime | None
    message: str


@dataclass
class MobilePushData:
    total_mobile_users: int
    push_notification_status: PushNotificationsStatus
    uncategorized_mobile_users: int | None = None
    mobile_pushes_forwarded: int | None = None
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
class UserData:
    guest_user_count: int
    non_guest_user_count: int


@dataclass
class CloudSupportData:
    plan_data: PlanData
    sponsorship_data: SponsorshipData
    user_data: UserData
    file_upload_usage: str
    is_scrubbed: bool


def get_stripe_customer_url(stripe_id: str) -> str:
    return f"https://dashboard.stripe.com/customers/{stripe_id}"  # nocoverage


def get_formatted_realm_upload_space_used(realm: Realm) -> str:  # nocoverage
    realm_bytes_used = realm.currently_used_upload_space_bytes()
    files_uploaded = realm_bytes_used > 0

    realm_uploads = "No uploads"
    if files_uploaded:
        realm_uploads = str(round(realm_bytes_used / 1024 / 1024, 2))

    quota = realm.upload_quota_bytes()
    if quota is None:
        if files_uploaded:
            return f"{realm_uploads} MiB / No quota"
        return f"{realm_uploads} / No quota"
    if quota == 0:
        return f"{realm_uploads} / 0.0 MiB"
    quota_mb = round(quota / 1024 / 1024, 2)
    return f"{realm_uploads} / {quota_mb} MiB"


def get_realm_user_data(realm: Realm) -> UserData:
    non_guests = get_non_guest_user_count(realm)
    guests = get_guest_user_count(realm)
    return UserData(
        guest_user_count=guests,
        non_guest_user_count=non_guests,
    )


def get_customer_sponsorship_data(customer: Customer) -> SponsorshipData:
    pending = customer.sponsorship_pending
    licenses = customer.minimum_licenses
    plan_tier = customer.required_plan_tier
    has_discount = False
    sponsorship_request = None
    monthly_discounted_price = None
    annual_discounted_price = None
    original_monthly_plan_price = None
    original_annual_plan_price = None
    if customer.monthly_discounted_price:
        has_discount = True
        monthly_discounted_price = customer.monthly_discounted_price
    if customer.annual_discounted_price:
        has_discount = True
        annual_discounted_price = customer.annual_discounted_price
    if plan_tier is not None:
        original_monthly_plan_price = get_price_per_license(
            plan_tier, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        original_annual_plan_price = get_price_per_license(
            plan_tier, CustomerPlan.BILLING_SCHEDULE_ANNUAL
        )
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
                plan_to_use_zulip=last_sponsorship_request.plan_to_use_zulip,
                paid_users=last_sponsorship_request.paid_users_count,
                paid_users_description=last_sponsorship_request.paid_users_description,
                requested_plan=last_sponsorship_request.requested_plan,
            )

    return SponsorshipData(
        sponsorship_pending=pending,
        has_discount=has_discount,
        monthly_discounted_price=monthly_discounted_price,
        annual_discounted_price=annual_discounted_price,
        original_monthly_plan_price=original_monthly_plan_price,
        original_annual_plan_price=original_annual_plan_price,
        minimum_licenses=licenses,
        required_plan_tier=plan_tier,
        latest_sponsorship_request=sponsorship_request,
    )


def get_annual_invoice_count(billing_schedule: int) -> int:
    if billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
        return 12
    else:  # nocoverage
        return 1


def get_next_plan_data(
    billing_session: BillingSession,
    customer: Customer,
    current_plan: CustomerPlan | None = None,
) -> NextPlanData:
    plan_offer: CustomerPlanOffer | None = None

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
    billing_session: BillingSession, user_count: int | None = None, stale_user_data: bool = False
) -> PlanData:
    customer = billing_session.get_customer()
    plan = None
    if customer is not None:
        plan = get_current_plan_by_customer(customer)
    plan_data = PlanData(
        customer=customer,
        current_plan=plan,
    )

    if plan_data.current_plan is not None:
        last_ledger_entry = (
            LicenseLedger.objects.filter(
                plan=plan_data.current_plan, event_time__lte=timezone_now()
            )
            .order_by("-id")
            .first()
        )

        if last_ledger_entry is None:  # nocoverage
            # This shouldn't be possible because at least one
            # license ledger entry should exist when a plan's
            # status is less than CustomerPlan.LIVE_STATUS_THRESHOLD.
            # But since we have a warning feature in the support
            # view for plan data, we use that instead of raising
            # an assertion error so that support staff can debug
            # if this does ever occur.
            plan_data.warning += "License ledger missing: No data for total licenses and revenue. "
            plan_data.licenses = None
            plan_data.annual_recurring_revenue = 0
        else:
            plan_data.licenses = last_ledger_entry.licenses
            plan_data.annual_recurring_revenue = (
                billing_session.get_annual_recurring_revenue_for_support_data(
                    plan_data.current_plan, last_ledger_entry
                )
            )

        # If we already have user count data, we use that
        # instead of querying the database again to get
        # the number of currently used licenses.
        if stale_user_data:
            plan_data.warning += USER_DATA_STALE_WARNING
            plan_data.licenses_used = None
        elif user_count is None:
            try:
                plan_data.licenses_used = billing_session.current_count_for_billed_licenses()
            except MissingDataError:  # nocoverage
                plan_data.warning += USER_DATA_STALE_WARNING
                plan_data.licenses_used = None
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

        if isinstance(billing_session, RealmBillingSession):
            # TODO implement a complimentary access plan/tier for Zulip Cloud.
            plan_data.is_complimentary_access_plan = False
        else:
            plan_data.is_complimentary_access_plan = (
                plan_data.current_plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
            )
        plan_data.has_fixed_price = plan_data.current_plan.fixed_price is not None
        plan_data.is_current_plan_billable = billing_session.check_plan_tier_is_billable(
            plan_tier=plan_data.current_plan.tier
        )

    # Check for a non-active/scheduled CustomerPlan or CustomerPlanOffer
    if customer is not None:
        next_plan_data = get_next_plan_data(billing_session, customer, plan_data.current_plan)
        plan_data.next_plan = next_plan_data.plan
        plan_data.estimated_next_plan_revenue = next_plan_data.estimated_revenue

    # If customer has a stripe ID, add link to stripe customer dashboard
    if customer is not None and customer.stripe_customer_id is not None:
        plan_data.stripe_customer_url = get_stripe_customer_url(
            customer.stripe_customer_id
        )  # nocoverage

    return plan_data


def get_mobile_push_data(remote_entity: RemoteZulipServer | RemoteRealm) -> MobilePushData:
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
            subgroup=None,
            end_time__gte=timezone_now() - timedelta(days=7),
        ).aggregate(total_forwarded=Sum("value", default=0))
        latest_remote_server_push_forwarded_count = RemoteInstallationCount.objects.filter(
            server=remote_entity,
            subgroup=None,
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
        push_status = get_push_status_for_remote_request(
            remote_server=remote_entity, remote_realm=None
        )
        push_notification_status = PushNotificationsStatus(
            can_push=push_status.can_push,
            expected_end=timestamp_to_datetime(push_status.expected_end_timestamp)
            if push_status.expected_end_timestamp
            else None,
            message=push_status.message,
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
            subgroup=None,
            end_time__gte=timezone_now() - timedelta(days=7),
        ).aggregate(total_forwarded=Sum("value", default=0))
        latest_remote_realm_push_forwarded_count = RemoteRealmCount.objects.filter(
            remote_realm=remote_entity,
            subgroup=None,
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
        push_status = get_push_status_for_remote_request(remote_entity.server, remote_entity)
        push_notification_status = PushNotificationsStatus(
            can_push=push_status.can_push,
            expected_end=timestamp_to_datetime(push_status.expected_end_timestamp)
            if push_status.expected_end_timestamp
            else None,
            message=push_status.message,
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
            event_type=AuditLogEventType.REMOTE_SERVER_CREATED,
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
    user_data = get_realm_user_data(billing_session.realm)
    plan_data = get_plan_data_for_support_view(billing_session)
    if plan_data.customer is not None:
        sponsorship_data = get_customer_sponsorship_data(plan_data.customer)
    else:
        sponsorship_data = SponsorshipData()

    return CloudSupportData(
        plan_data=plan_data,
        sponsorship_data=sponsorship_data,
        user_data=user_data,
        file_upload_usage=get_formatted_realm_upload_space_used(billing_session.realm),
        is_scrubbed=RealmAuditLog.objects.filter(
            realm=billing_session.realm, event_type=AuditLogEventType.REALM_SCRUBBED
        ).exists(),
    )

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, TypedDict
from urllib.parse import urlencode, urljoin, urlunsplit

from django.conf import settings
from django.urls import reverse
from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import BillingSession
from corporate.models import (
    Customer,
    CustomerPlan,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
)
from zerver.models import Realm, get_org_type_display_name, get_realm
from zilencer.lib.remote_counts import MissingDataError


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
    latest_sponsorship_request: Optional[SponsorshipRequestDict] = None


@dataclass
class PlanData:
    customer: Optional["Customer"] = None
    current_plan: Optional["CustomerPlan"] = None
    licenses: Optional[int] = None
    licenses_used: Optional[int] = None
    is_legacy_plan: bool = False
    has_fixed_price: bool = False
    warning: Optional[str] = None


@dataclass
class SupportData:
    plan_data: PlanData
    sponsorship_data: SponsorshipData


def get_realm_support_url(realm: Realm) -> str:
    support_realm_uri = get_realm(settings.STAFF_SUBDOMAIN).uri
    support_url = urljoin(
        support_realm_uri,
        urlunsplit(("", "", reverse("support"), urlencode({"q": realm.string_id}), "")),
    )
    return support_url


def get_customer_discount_for_support_view(
    customer: Optional[Customer] = None,
) -> Optional[Decimal]:
    if customer is None:
        return None
    return customer.default_discount


def get_customer_sponsorship_data(customer: Customer) -> SponsorshipData:
    pending = customer.sponsorship_pending
    discount = customer.default_discount
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
        latest_sponsorship_request=sponsorship_request,
    )


def get_current_plan_data_for_support_view(billing_session: BillingSession) -> PlanData:
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
            try:
                plan_data.licenses_used = billing_session.current_count_for_billed_licenses()
            except MissingDataError:  # nocoverage
                plan_data.warning = "Recent data missing: No information for used licenses"
        assert plan_data.current_plan is not None  # for mypy
        plan_data.is_legacy_plan = (
            plan_data.current_plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        )
        plan_data.has_fixed_price = plan_data.current_plan.fixed_price is not None

    return plan_data


def get_data_for_support_view(billing_session: BillingSession) -> SupportData:
    plan_data = get_current_plan_data_for_support_view(billing_session)
    customer = billing_session.get_customer()
    if customer is not None:
        sponsorship_data = get_customer_sponsorship_data(customer)
    else:
        sponsorship_data = SponsorshipData()

    return SupportData(
        plan_data=plan_data,
        sponsorship_data=sponsorship_data,
    )

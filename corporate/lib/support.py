from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode, urljoin, urlunsplit

from django.conf import settings
from django.urls import reverse
from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import BillingSession
from corporate.models import Customer, CustomerPlan, get_current_plan_by_customer
from zerver.models import Realm, get_realm


@dataclass
class PlanData:
    customer: Optional["Customer"] = None
    current_plan: Optional["CustomerPlan"] = None
    licenses: Optional[int] = None
    licenses_used: Optional[int] = None
    is_legacy_plan: bool = False


def get_support_url(realm: Realm) -> str:
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
            plan_data.licenses_used = billing_session.current_count_for_billed_licenses()
        assert plan_data.current_plan is not None  # for mypy
        plan_data.is_legacy_plan = (
            plan_data.current_plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        )

    return plan_data
